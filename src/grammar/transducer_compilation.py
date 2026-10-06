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
    FstContext,
    build_fst_context_for_project,
    fsa,
    word_fsa,
)
from src.models import (
    Marker,
    PrincipalPartMarker,
    Project,
    Rule,
    RuleSequence,
    SimpleRule,
    StringMapRule,
    StructRegistryType,
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


def _compile_prefix(value: str, fst_context: FstContext) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    bow = pynini.accep(
        ReservedSymbols.bow,
        token_type=fst_context.sym_table,
    )
    tau = pynini.cross(bow, pynini.concat(bow, fsa(value)))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_suffix(value: str, fst_context: FstContext) -> pynini.Fst:
    sigma_star = fst_context.special_fsas["sigma_star"]
    eow = pynini.accep(ReservedSymbols.eow, token_type=fst_context.sym_table)
    tau = pynini.cross(eow, pynini.concat(fsa(value, fst_context), eow))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_string_map(
    string_map: tuple[tuple[str, str], ...],
    fst_context: FstContext,
) -> pynini.Fst:
    # word-level substitution: cross(word_fsa(root), word_fsa(pp)) per entry
    return pynini.union(
        *[
            pynini.cross(
                word_fsa(i, fst_context),
                word_fsa(o, fst_context),
            )
            for i, o in string_map
        ]
    ).optimize()


def compile_marker(marker: Marker, project: Project) -> pynini.Fst:
    if isinstance(marker, SingleStringMarker):
        if marker.kind == "prefix":
            return _compile_prefix(marker.value, project.fst_context)
        if marker.kind == "suffix":
            return _compile_suffix(marker.value, project.fst_context)
        if marker.kind == "suppletion":
            sigma_star = project.special_fsas["sigma_star"]
            tau = pynini.cross(sigma_star, fsa(marker.value, fst_context))
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
        sigma_star = project.special_fsas["sigma_star"]
        tau = pynini.cross(
            fsa(marker.value[0], fst_context),
            fsa(marker.value[1], fst_context),
        )
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


if __name__ == "__main__":
    project = load_project()
    project = build_fst_context_for_project(project)
    project = compile_rules_for_project(project)
    breakpoint()
