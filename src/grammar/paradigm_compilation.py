"""
Paradigm inflect / parse / fuzzy-search graph compilation.

Caches:
  inflect + parse + search FSTs → YAML_DIR/.cache/Paradigm/{name}.{kind}.fst
  Invalidated when any of Paradigm, FeatureMarkers, ContingentFeatureMarkers,
  Inventory, FeatureDefinitions, or Rules dirs change.
"""

from __future__ import annotations

import itertools
import os
import re

import pynini
from loguru import logger
from pynini.lib import pynutil

from src.cache import is_fst_cache_valid, save_fst, load_fst
from src.fst_utils import ReservedSymbolMixin as R
from src.fst_utils import stringify_features
from src.launcher import YAML_DIR
from src.lexicon import get_gloss_for_root, get_roots
from src.yaml_utils.schema_validation import CONFIG_KIND_TO_PARDIR
from src.yaml_utils.yaml_server import (
    get_feature_map,
    get_yaml_kind,
    get_yaml_data_safe,
)
from src.grammar.acceptor_compilation import (
    fsa,
    fsm_strings,
    fsm_strings_and_weights,
    word_fsa,
    get_sigma_star,
    get_special_fsas,
    get_symbol_table,
)
from src.grammar.marker_resolution import get_markers_for_paradigm
from src.grammar.transducer_compilation import get_marker_fst

EDIT_BOUND = 5
EDIT_COST = 1.0


def _kind_dir(kind: str) -> str:
    return os.path.join(YAML_DIR, CONFIG_KIND_TO_PARDIR[kind], kind)


_SOURCE_DIRS = (
    _kind_dir("Paradigm"),
    _kind_dir("FeatureMarkers"),
    _kind_dir("ContingentFeatureMarkers"),
    _kind_dir("Inventory"),
    _kind_dir("FeatureDefinitions"),
    _kind_dir("Rules"),
)

"""
## Module-level cache state
"""

_paradigm_fsts: dict[str, pynini.Fst] | None = None


def invalidate_paradigm_fsts() -> None:
    global _paradigm_fsts
    _paradigm_fsts = None


"""
## Helpers
"""


def _feature_combinations(
    paradigm_data: dict,
    feature_map: dict,
) -> tuple[list[set[tuple[str, str]]], list[str], list[str]]:
    """
    Return (combos, marker_files, contingent_files) for a paradigm.
    Each combo is a set of (feature, value) pairs covering all free features
    plus any fixed feature values.
    """
    fixed: dict[str, str] = {}
    marker_files: list[str] = []
    free_feature_names: list[str] = []

    for feature_name, ref in paradigm_data.get("feature_markers", {}).items():
        if ref is None:
            continue
        if isinstance(ref, str) and ref.startswith("$"):
            free_feature_names.append(feature_name)
            marker_files.append(ref)
        else:
            fixed[feature_name] = ref

    contingent_files = list(paradigm_data.get("contingent_markers", []))

    free_value_lists = []
    for fname in free_feature_names:
        if fname not in feature_map:
            logger.warning(f"Feature '{fname}' not in feature map — skipping.")
            continue
        free_value_lists.append([(fname, v) for v in feature_map[fname]])

    if not free_value_lists:
        combos = [set(fixed.items())]
    else:
        combos = [
            set(fixed.items()) | set(combo_tuples)
            for combo_tuples in itertools.product(*free_value_lists)
        ]
    return combos, marker_files, contingent_files


def _apply_markers(stem_fst: pynini.Fst, markers: list) -> pynini.Fst:
    current = stem_fst
    for marker in markers:
        current = pynini.compose(current, get_marker_fst(marker))
    return current


def get_features_for_paradigm(name: str) -> set[str]:
    """
    Get the set of inflectional features for a given paradigm.
    """
    paradigm_data = get_yaml_data_safe("Paradigm", name)
    part_of_speech = paradigm_data["part_of_speech"]
    features = get_yaml_data_safe(
        yaml_basename=part_of_speech, kind="PartOfSpeech"
    ).get("features", [])
    return set(features)


"""
## Graph builders
"""


def build_inflect_graph(paradigm_name: str) -> pynini.Fst:
    """root[features...] → surface form."""
    paradigm_data = get_yaml_data_safe("Paradigm", paradigm_name)
    if paradigm_data is None:
        raise ValueError(f"Paradigm '{paradigm_name}' not found or invalid.")

    part_of_speech = paradigm_data["part_of_speech"]
    feature_map = get_feature_map()
    roots = get_roots(part_of_speech)
    combos, marker_files, contingent_files = _feature_combinations(
        paradigm_data, feature_map
    )

    inflect_fsts: list[pynini.Fst] = []
    for root in roots:
        root_fsa = word_fsa(root)
        for feature_values in combos:
            try:
                markers = get_markers_for_paradigm(feature_values, paradigm_name)
                inflected_output = pynini.project(
                    _apply_markers(root_fsa, markers), project_type="output"
                )
            except Exception as e:
                logger.warning(
                    f"Skipping {paradigm_name} root={root} fv={feature_values}: {e}"
                )
                continue

            feature_str = stringify_features(feature_values)
            inflect_input = (
                pynini.concat(root_fsa, fsa(feature_str)) if feature_str else root_fsa
            )
            inflect_fsts.append(
                pynini.cross(inflect_input, inflected_output).optimize()
            )
            breakpoint()

    if not inflect_fsts:
        return pynini.Fst()
    return pynini.union(*inflect_fsts).optimize()


def build_parse_graph(inflect_graph: pynini.Fst) -> pynini.Fst:
    return pynini.invert(inflect_graph).optimize()


def build_search_graph(inflect_graph: pynini.Fst) -> pynini.Fst:
    """Fuzzy-searchable form lattice via edit transducers."""
    sigma = get_special_fsas()["sigma"]
    sigma_star = get_sigma_star()
    syms = get_symbol_table()

    insert_fst = pynutil.insert(
        pynini.accep(R.insert, weight=EDIT_COST / 2, token_type=syms)
    )
    delete_fst = pynini.cross(
        sigma,
        pynini.accep(R.delete, weight=EDIT_COST / 2, token_type=syms),
    )
    substitute_fst = pynini.cross(
        sigma,
        pynini.accep(R.substitute, weight=EDIT_COST / 2, token_type=syms),
    )
    edit_fst = pynini.union(insert_fst, delete_fst, substitute_fst).optimize()

    left_factor = sigma_star.copy()
    for _ in range(EDIT_BOUND):
        left_factor = pynini.concat(
            left_factor, pynini.concat(edit_fst.ques, sigma_star)
        )
    left_factor.optimize()

    right_factor = pynini.invert(left_factor)
    insert_label = syms.find(R.insert)
    delete_label = syms.find(R.delete)
    right_factor = right_factor.relabel_pairs(
        ipairs=[(insert_label, delete_label), (delete_label, insert_label)]
    )

    form_lattice = pynini.project(inflect_graph, project_type="output")
    return pynini.compose(right_factor, form_lattice).optimize()


"""
## Cache warming and public entry points
"""

_FST_KINDS = ("inflect", "parse", "search")


def _paradigm_cache_valid(name: str) -> bool:
    return all(
        is_fst_cache_valid("Paradigm", name, k, *_SOURCE_DIRS) for k in _FST_KINDS
    )


def _load_paradigm(name: str) -> tuple[pynini.Fst, pynini.Fst, pynini.Fst] | None:
    fsts = [load_fst("Paradigm", name, k) for k in _FST_KINDS]
    return tuple(fsts) if all(f is not None for f in fsts) else None


def _save_paradigm(
    name: str, inflect: pynini.Fst, parse: pynini.Fst, search: pynini.Fst
) -> None:
    for k, f in zip(_FST_KINDS, (inflect, parse, search)):
        save_fst("Paradigm", name, k, f)


def _store(
    name: str, inflect: pynini.Fst, parse: pynini.Fst, search: pynini.Fst
) -> None:
    _paradigm_fsts[f"{name}:inflect"] = inflect
    _paradigm_fsts[f"{name}:parse"] = parse
    _paradigm_fsts[f"{name}:search"] = search


def _warm_cache() -> None:
    global _paradigm_fsts
    _paradigm_fsts = {}
    for basename, _ in get_yaml_kind("Paradigm")["valid"]:
        name = basename.removesuffix(".yaml")
        if _paradigm_cache_valid(name):
            loaded = _load_paradigm(name)
            if loaded is not None:
                _store(name, *loaded)
                continue
        try:
            inflect = build_inflect_graph(name)
            parse = build_parse_graph(inflect)
            search = build_search_graph(inflect)
            _save_paradigm(name, inflect, parse, search)
            _store(name, inflect, parse, search)
        except Exception as e:
            logger.warning(f"Failed to build graphs for paradigm '{name}': {e}")


def _get_or_build(
    paradigm_name: str, graph_type: str, force_rebuild: bool = False
) -> pynini.Fst:
    global _paradigm_fsts
    if _paradigm_fsts is None:
        _warm_cache()
    key = f"{paradigm_name}:{graph_type}"
    if key not in _paradigm_fsts or force_rebuild:
        if not force_rebuild and _paradigm_cache_valid(paradigm_name):
            loaded = _load_paradigm(paradigm_name)
            if loaded is not None:
                _store(paradigm_name, *loaded)
                return _paradigm_fsts[key]
        inflect = build_inflect_graph(paradigm_name)
        parse = build_parse_graph(inflect)
        search = build_search_graph(inflect)
        _save_paradigm(paradigm_name, inflect, parse, search)
        _store(paradigm_name, inflect, parse, search)
    return _paradigm_fsts[key]


def get_inflect_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "inflect")


def get_parse_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "parse")


def get_search_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "search")


"""
Public API
"""


def parse(form: str, kind: str = "Paradigm", name: str = "") -> list[dict]:
    form_fsa = word_fsa(form)
    parse_graph = get_parse_graph(name)
    paradigm_data = get_yaml_data_safe(yaml_basename=name, kind=kind)
    lexicon_basename = paradigm_data.get("part_of_speech", "")

    parse_lattice = (form_fsa @ parse_graph).optimize()
    parse_strs = fsm_strings(parse_lattice)
    parses = []
    for s in parse_strs:
        feat_matches = re.findall(r"\[([^=\]]+)=([^\]]+)\]", s)
        root = re.sub(r"\[[^\]]+\]", "", s).strip()
        gloss = get_gloss_for_root(lexicon_basename, root)
        parses.append({"root": root, "features": dict(feat_matches), "gloss": gloss})

    return parses


def inflect(
    root: list[str] | str,
    feature_values: set[tuple[str, str]] | dict[str, str],
    name: str,
) -> list[str]:

    if isinstance(feature_values, dict):
        feature_values = set(feature_values.items())

    features = set(feature for feature, _ in feature_values)
    expected_features = get_features_for_paradigm(name)
    if not features == expected_features:
        raise ValueError(
            f"Feature set {features} does not match expected features {expected_features} for paradigm '{name}'."
        )

    inflect_graph = get_inflect_graph(name)
    feature_str = stringify_features(feature_values)
    input_fsa = (
        pynini.concat(word_fsa(root), fsa(feature_str))
        if feature_str
        else word_fsa(root)
    )
    output_lattice = pynini.compose(input_fsa, inflect_graph).optimize()
    output_lattice = pynini.project(output_lattice, project_type="output")
    surface_forms = fsm_strings(output_lattice, strip_all_tags=True)

    return surface_forms


def search(name: str, form: str, nshortest: int):
    search_graph = get_search_graph(name)
    form_fsa = word_fsa(form)
    left_factor_lattice = pynini.compose(form_fsa, search_graph).optimize()
    hits = fsm_strings_and_weights(
        left_factor_lattice, strip_all_tags=True, nshortest=nshortest
    )

    return hits
