"""
Paradigm inflect / parse / fuzzy-search graph compilation.

Caches:
  inflect + parse + search FSTs → get_yaml_dir()/.cache/Paradigm/{name}.{kind}.fst
  Invalidated when any of Paradigm, FeatureMarkers, ContingentFeatureMarkers,
  Inventory, FeatureDefinition, or Rules dirs change.
"""

from __future__ import annotations

import pynini
from pynini.lib import pynutil

from src.grammar.acceptor_compilation import (
    build_fst_context_for_project,
    fsa,
    fsm_strings,
    fsm_strings_and_weights,
)
from src.grammar.lexicon import inflected_word_from_string
from src.grammar.marker_resolution import (
    build_all_paradigm_global_markers,
    build_all_paradigm_tries,
    resolve_inflected_words,
)
from src.grammar.transducer_compilation import (
    compile_rules_for_project,
    strip_special_symbols_rule,
)
from src.models import (
    PARADIGM_TAG,
    CompiledParadigm,
    InflectedWord,
    Project,
    ReservedSymbols,
)
from src.yaml.yaml_server import load_project_structs

EDIT_BOUND = 5
EDIT_COST = 1.0


"""
## Graph builders
"""


def build_inflect_graph(paradigm_id: str, project: Project) -> pynini.Fst:
    """root[features...] → surface form."""
    resolved = resolve_inflected_words(
        paradigm_id=paradigm_id,
        project=project,
    )
    inflect_fsts = []
    for word in resolved:
        for form in word.forms:
            inflect_fsts.append(
                pynini.cross(
                    fsa(word.tagged_root, project.fst_context),
                    fsa(form, project.fst_context),
                )
            )
    return pynini.union(*inflect_fsts).optimize()


def build_parse_graph(
    inflect_graph: pynini.Fst,
    project: Project,
) -> pynini.Fst:
    inflect_and_remove_symbols = inflect_graph @ strip_special_symbols_rule(
        project.fst_context
    )
    return pynini.invert(inflect_and_remove_symbols).optimize()


def build_search_lexicon_and_leftfactor(
    parse_graph: pynini.Fst,
    project: Project,
) -> tuple[pynini.Fst, pynini.Fst]:
    """Fuzzy-searchable form lattice via edit transducers."""
    sigma = project.fst_context.special_fsas["sigma"]
    sigma_star = project.fst_context.special_fsas["sigma_star"]
    syms = project.fst_context.sym_table

    insert_fst = pynutil.insert(
        pynini.accep(
            ReservedSymbols.insert,
            weight=EDIT_COST / 2,
            token_type=syms,
        )
    )
    delete_fst = pynini.cross(
        sigma,
        pynini.accep(
            ReservedSymbols.delete,
            weight=EDIT_COST / 2,
            token_type=syms,
        ),
    )
    substitute_fst = pynini.cross(
        sigma,
        pynini.accep(
            ReservedSymbols.substitute,
            weight=EDIT_COST / 2,
            token_type=syms,
        ),
    )
    edit_fst = pynini.union(
        insert_fst,
        delete_fst,
        substitute_fst,
    ).optimize()

    left_factor = sigma_star.copy()
    for _ in range(EDIT_BOUND):
        left_factor = pynini.concat(
            left_factor, pynini.concat(edit_fst.ques, sigma_star)
        )
    left_factor.optimize()

    right_factor = pynini.invert(left_factor)
    insert_label = syms.find(ReservedSymbols.insert)
    delete_label = syms.find(ReservedSymbols.delete)
    right_factor = right_factor.relabel_pairs(
        ipairs=[
            (insert_label, delete_label),
            (delete_label, insert_label),
        ]
    )

    form_lattice = pynini.project(parse_graph, project_type="input").optimize()
    search_lexicon = pynini.compose(right_factor, form_lattice).optimize()
    return search_lexicon, left_factor


def compile_paradigm(
    paradigm_id: str,
    project: Project,
) -> CompiledParadigm:
    inflect_graph = build_inflect_graph(
        paradigm_id=paradigm_id,
        project=project,
    )
    parse_graph = build_parse_graph(
        inflect_graph=inflect_graph,
        project=project,
    )
    search_lexicon, search_left_factor = build_search_lexicon_and_leftfactor(
        parse_graph=parse_graph,
        project=project,
    )
    return CompiledParadigm(
        inflect_graph=inflect_graph,
        parse_graph=parse_graph,
        search_lexicon=search_lexicon,
        search_left_factor=search_left_factor,
    )


def compile_global_parser(project: Project) -> CompiledParadigm:
    compiled_paradigms: dict[str, CompiledParadigm] = {}
    inflect_graphs = []
    for paradigm_id in project.struct_registry["ParadigmFile"]:
        compiled = compile_paradigm(
            paradigm_id=paradigm_id,
            project=project,
        )
        compiled_paradigms[paradigm_id] = compiled
        tagged_inflect_graph = (
            fsa(
                f"[{PARADIGM_TAG}={paradigm_id}]",
                fst_context=project.fst_context,
            )
            + compiled.inflect_graph
        )
        inflect_graphs.append(tagged_inflect_graph)
    global_inflect_graph = pynini.union(*inflect_graphs).optimize()
    global_parse_graph = build_parse_graph(
        inflect_graph=global_inflect_graph,
        project=project,
    )
    global_search_lexicon, global_search_left_factor = (
        build_search_lexicon_and_leftfactor(
            parse_graph=global_parse_graph,
            project=project,
        )
    )
    return CompiledParadigm(
        inflect_graph=global_inflect_graph,
        parse_graph=global_parse_graph,
        search_lexicon=global_search_lexicon,
        search_left_factor=global_search_left_factor,
    )


"""
Public API
"""


def search(
    form: str,
    parser: CompiledParadigm,
    project: Project,
    nshortest: int = 5,
) -> list[InflectedWord]:
    form_fsa = fsa(form, project.fst_context)
    left_factor_lattice = pynini.compose(form_fsa, parser.search_left_factor).optimize()
    edit_graph = pynini.compose(left_factor_lattice, parser.search_lexicon)
    hits = fsm_strings_and_weights(
        edit_graph,
        strip_all_tags=True,
        nshortest=nshortest,
        fst_context=project.fst_context,
    )
    parsed = []
    for hit, weight in hits:
        hit_fsa = fsa(hit, project.fst_context)
        parsed_strings = fsm_strings(
            fst=hit_fsa @ parser.parse_graph,
            fst_context=project.fst_context,
        )
        for parsed_string in parsed_strings:
            parsed_word = inflected_word_from_string(
                parsed_string,
                project,
            )
            parsed_word = parsed_word.update_word(
                forms=(hit,),
                edit_distance=weight,
            )
            parsed.append(parsed_word)

    return parsed


if __name__ == "__main__":
    project = load_project_structs()
    project = build_fst_context_for_project(project)
    project = compile_rules_for_project(project)
    project = build_all_paradigm_tries(project)
    project = build_all_paradigm_global_markers(project)
    paradigm = compile_paradigm(
        paradigm_id="verb_a_stem",
        project=project,
    )
    form = "hablas"
    form_fsa = fsa(form, project.fst_context)
    result = form_fsa @ paradigm.parse_graph
    result_strs = fsm_strings_and_weights(
        result,
        project.fst_context,
    )

    parser = compile_global_parser(project)
    global_result = form_fsa @ parser.parse_graph
    global_result_strs = fsm_strings_and_weights(
        global_result,
        project.fst_context,
    )

    fuzzy_form = "hablos"
    fuzzy_form_fsa = fsa(
        fuzzy_form,
        project.fst_context,
    )
    fuzzy_result = (
        fuzzy_form_fsa @ parser.search_left_factor
    ).optimize() @ parser.search_lexicon
    fuzzy_result = fuzzy_result.optimize()
    fuzzy_result_strs = fsm_strings_and_weights(
        fuzzy_result,
        project.fst_context,
        nshortest=10,
    )

    search_result = search(
        fuzzy_form,
        parser,
        project,
    )

    breakpoint()
