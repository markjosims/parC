"""
Functional FST compilation for Rules and Markers.

Caches:
  rule FSTs   → in-memory only  (rules + inv + feat dirs)
  marker FSTs → in-memory only  (cleared on source changes)
"""

from __future__ import annotations

import pynini

from src.grammar.acceptor_compilation import (
    FstContext,
    build_fst_context_for_project,
    fsa,
)
from src.grammar.lexicon import convert_lexeme_table_to_lexemes, load_lexeme_table
from src.models import (
    Marker,
    ParadigmFile,
    PrefixMarker,
    PrincipalPartMarker,
    Project,
    ReplaceMarker,
    ReservedSymbols,
    Rule,
    RuleMarker,
    RuleSequence,
    SimpleRule,
    StringMapRule,
    SuffixMarker,
    SuppletionMarker,
    TransitiveRelation,
)
from src.yaml.yaml_server import kind_dir, load_project

"""
## Rule compilation
"""


def _compile_simple_rule(rule: SimpleRule, fst_context: FstContext) -> pynini.Fst:
    tau = pynini.cross(
        fsa(rule.input_pattern, fst_context),
        fsa(rule.output_pattern, fst_context),
    ).optimize()
    l = fsa(rule.left_context, fst_context) if rule.left_context else ""
    r = fsa(rule.right_context, fst_context) if rule.right_context else ""
    return pynini.cdrewrite(tau, l, r, fst_context.special_fsas["sigma_star"])


def _compile_string_map_rule(
    rule: StringMapRule,
    fst_context: FstContext,
) -> pynini.Fst:
    tau = pynini.union(
        *[
            pynini.cross(
                fsa(relation.input_pattern, fst_context),
                fsa(relation.output_pattern, fst_context),
            )
            for relation in rule.string_map
        ]
    ).optimize()
    l = fsa(rule.left_context, fst_context) if rule.left_context else ""
    r = fsa(rule.right_context, fst_context) if rule.right_context else ""
    return pynini.cdrewrite(
        tau,
        l,
        r,
        fst_context.special_fsas["sigma_star"],
    )


def compile_rule(
    rule: Rule,
    project: Project,
) -> Project:
    if rule.id in project.fst_context.compiled_rules:
        return
    if isinstance(rule, SimpleRule):
        result = _compile_simple_rule(rule, project.fst_context)
    elif isinstance(rule, StringMapRule):
        result = _compile_string_map_rule(rule, project.fst_context)
    elif isinstance(rule, RuleSequence):
        rules = project.struct_registry["Rule"]
        result: list[pynini.Fst] = []
        for rule_id in rule.rules:
            sub_fst = compile_rule(rules[rule_id], project)
            if isinstance(sub_fst, list):
                result.extend(sub_fst)
            else:
                result.append(sub_fst)
    else:
        raise ValueError(f"Unknown rule type: {type(rule)!r}")
    project.fst_context.compiled_rules[rule.id] = result
    return project


def compile_rules_for_project(project: Project) -> Project:
    compiled_rules: dict[str, pynini.Fst | list[pynini.Fst]]
    new_fst_context = project.fst_context._replace(compiled_rules={})
    new_project = project._replace(fst_context=new_fst_context)
    for rule in new_project.struct_registry["Rule"].values():
        new_project = compile_rule(rule, new_project)
    return new_project


"""
## Marker compilation
"""


def _compile_prefix(form: str, fst_context: FstContext) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    bow = pynini.accep(
        ReservedSymbols.bow,
        token_type=fst_context.sym_table,
    )
    tau = pynini.cross(bow, pynini.concat(bow, fsa(form, fst_context)))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_suffix(form: str, fst_context: FstContext) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    eow = pynini.accep(ReservedSymbols.eow, token_type=fst_context.sym_table)
    tau = pynini.cross(eow, pynini.concat(fsa(form, fst_context), eow))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_rule_marker(
    rule_id: str, fst_context: FstContext
) -> pynini.Fst | tuple[pynini.Fst, ...]:
    rules = fst_context.compiled_rules
    if rule_id not in rules:
        raise KeyError(
            f"Rule '{rule_id}' not found in set of compiled rules {list(rules.keys())}"
        )
    rule_fst = rules[rule_id]
    return rule_fst


def _compile_suppletion_marker(form: str, fst_context: FstContext) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    tau = pynini.cross(
        sigma_star,
        fsa(form, fst_context),
    )
    return pynini.cdrewrite(
        tau=tau,
        l=ReservedSymbols.bow,
        r=ReservedSymbols.eow,
        sigma_star=sigma_star,
    )


def _compile_replace_marker(
    relation: TransitiveRelation,
    fst_context: FstContext,
) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    tau = pynini.cross(
        fsa(relation.input_pattern, project.fst_context),
        fsa(relation.output_pattern, project.fst_context),
    )
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_principal_part_marker(
    principal_part: str,
    paradigm: ParadigmFile,
    project: Project,
) -> pynini.Fst:
    lexeme_table = load_lexeme_table(paradigm.part_of_speech)
    lexemes = convert_lexeme_table_to_lexemes(
        lexeme_table=lexeme_table,
        part_of_speech_id=paradigm.part_of_speech,
        project=project,
    )
    root_strs = [lexeme.lexeme_string for lexeme in lexemes]
    principal_part_strs = [
        lexeme.principal_part_string(principal_part=principal_part)
        for lexeme in lexemes
    ]
    return pynini.union(
        *[
            pynini.cross(
                fsa(root, project.fst_context),
                fsa(part, project.fst_context),
            )
            for root, part in zip(
                root_strs,
                principal_part_strs,
            )
        ]
    ).optimize()


def compile_marker(
    marker: Marker,
    paradigm: ParadigmFile,
    project: Project,
) -> tuple[pynini.Fst, ...]:
    if isinstance(marker, PrefixMarker):
        fst = _compile_prefix(marker.form, project.fst_context)
    elif isinstance(marker, SuffixMarker):
        fst = _compile_suffix(marker.form, project.fst_context)
    elif isinstance(marker, SuppletionMarker):
        fst = _compile_suppletion_marker(marker.form, project.fst_context)
    elif isinstance(marker, RuleMarker):
        fst = _compile_rule_marker(marker.rule, project.fst_context)
    elif isinstance(marker, ReplaceMarker):
        fst = _compile_replace_marker(marker.relation, project.fst_context)
    elif isinstance(marker, PrincipalPartMarker):
        fst = _compile_principal_part_marker(
            principal_part=marker.principal_part_value,
            project=project,
            paradigm=paradigm,
        )
    else:
        raise ValueError(f"Unrecognized marker type {type(marker)}")

    if isinstance(fst, tuple):
        return fst
    return (fst,)


if __name__ == "__main__":
    project = load_project()
    project = build_fst_context_for_project(project)
    project = compile_rules_for_project(project)
    breakpoint()
