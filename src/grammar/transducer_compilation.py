"""
Functional FST compilation for Rules and Markers.

Caches:
  rule FSTs   → in-memory only  (rules + inv + feat dirs)
  marker FSTs → in-memory only  (cleared on source changes)
"""

from __future__ import annotations

import pynini

from src.fst_utils import ReservedSymbols as ReservedSymbols
from src.grammar.acceptor_compilation import (
    fsa,
    get_sigma_star,
    get_symbol_table,
    word_fsa,
)
from src.models import (
    Marker,
    PrincipalPartMarker,
    Rule,
    RuleSequence,
    SimpleRule,
    StringMapRule,
    StructRegistryType,
)
from src.yaml.yaml_server import kind_dir

INVENTORY_DIR = kind_dir("Inventory")
FEATURES_DIR = kind_dir("FeatureDefinitions")
RULES_DIR = kind_dir("Rules")

"""
## Rule compilation
"""


def _compile_simple_rule(rule: SimpleRule) -> pynini.Fst:
    sigma_star = get_sigma_star()
    tau = pynini.cross(fsa(rule.input_pattern), fsa(rule.output_pattern)).optimize()
    l = fsa(rule.left_context) if rule.left_context else ""
    r = fsa(rule.right_context) if rule.right_context else ""
    return pynini.cdrewrite(tau, l, r, sigma_star)


def _compile_string_map_rule(rule: StringMapRule) -> pynini.Fst:
    sigma_star = get_sigma_star()
    tau = pynini.union(
        *[pynini.cross(fsa(i), fsa(o)) for i, o in rule.string_map]
    ).optimize()
    l = fsa(rule.left_context) if rule.left_context else ""
    r = fsa(rule.right_context) if rule.right_context else ""
    return pynini.cdrewrite(tau, l, r, sigma_star)


def compile_rule(rule: Rule) -> pynini.Fst | list[pynini.Fst]:
    if isinstance(rule, SimpleRule):
        return _compile_simple_rule(rule)
    if isinstance(rule, StringMapRule):
        return _compile_string_map_rule(rule)
    if isinstance(rule, RuleSequence):
        rules = get_rules()
        result: list[pynini.Fst] = []
        for name in rule.rules:
            sub_fst = compile_rule(rules[name])
            if isinstance(sub_fst, list):
                result.extend(sub_fst)
            else:
                result.append(sub_fst)
        return result
    raise ValueError(f"Unknown rule type: {type(rule)!r}")


"""
## Marker compilation
"""


def _compile_prefix(value: str) -> pynini.Fst:
    sigma_star = get_sigma_star()
    syms = get_symbol_table()
    bow = pynini.accep(ReservedSymbols.bow, token_type=syms)
    tau = pynini.cross(bow, pynini.concat(bow, fsa(value)))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_suffix(value: str) -> pynini.Fst:
    sigma_star = get_sigma_star()
    syms = get_symbol_table()
    eow = pynini.accep(ReservedSymbols.eow, token_type=syms)
    tau = pynini.cross(eow, pynini.concat(fsa(value), eow))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_string_map(string_map: tuple[tuple[str, str], ...]) -> pynini.Fst:
    # word-level substitution: cross(word_fsa(root), word_fsa(pp)) per entry
    return pynini.union(
        *[pynini.cross(word_fsa(i), word_fsa(o)) for i, o in string_map]
    ).optimize()


def compile_marker(marker: Marker) -> pynini.Fst:
    if isinstance(marker, SingleStringMarker):
        if marker.kind == "prefix":
            return _compile_prefix(marker.value)
        if marker.kind == "suffix":
            return _compile_suffix(marker.value)
        if marker.kind == "suppletion":
            sigma_star = get_sigma_star()
            tau = pynini.cross(sigma_star, fsa(marker.value))
            return pynini.cdrewrite(tau, "", "", sigma_star)
        if marker.kind == "rule":
            rules = get_rules()
            rule_name = marker.value.removeprefix("$")
            if rule_name not in rules:
                raise KeyError(
                    f"Rule '{marker.value}' not found in set of rules {list(rules.keys())}"
                )
            result = compile_rule(rules[rule_name])
            if isinstance(result, list):
                composed = result[0]
                for f in result[1:]:
                    composed = pynini.compose(composed, f)
                return composed
            return result
    if isinstance(marker, StringTupleMarker) and marker.kind == "replace":
        sigma_star = get_sigma_star()
        tau = pynini.cross(fsa(marker.value[0]), fsa(marker.value[1]))
        return pynini.cdrewrite(tau, "", "", sigma_star)
    if isinstance(marker, PrincipalPartMarker) and marker.kind == "string_map":
        return _compile_string_map(marker.value)
    if isinstance(marker, UnorderedMarker) and marker.kind == "principal_part":
        raise ValueError(
            "UnorderedMarker(principal_part) must be resolved to StringMapMarker "
            "via get_markers_for_paradigm before compilation"
        )
    raise ValueError(f"Unknown marker: {marker!r}")


"""
Public API
"""


def get_rule_fst(rule_name: str) -> pynini.Fst | list[pynini.Fst]:
    rule_name = rule_name.removeprefix("$")
    rules = get_rules()
    if rule_name not in rules:
        raise KeyError(
            f"Rule '{rule_name}' not found in set of rules {list(rules.keys())}"
        )
    rule = rules[rule_name]

    if isinstance(rule, RuleSequence):
        return [get_rule_fst(name) for name in rule.rules]

    return compile_rule(rule)


def get_marker_fst(marker: Marker) -> pynini.Fst:
    return compile_marker(marker)
