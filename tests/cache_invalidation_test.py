import os
from copy import deepcopy

import pynini
import pytest

import yaml
from src.constants import PROJECT_ROOT
from src.grammar.acceptor_compilation import (
    filter_strings_by_pattern,
    fsa,
    fsm_strings,
    get_pattern_fsts,
    word_fsa,
)
from src.grammar.marker_resolution import get_markers_for_paradigm
from src.grammar.paradigm_compilation import _get_or_build, inflect, parse, search
from src.grammar.transducer_compilation import compile_marker, get_rule_fst
from src.lexicon import get_roots_with_gloss
from src.models import (
    Marker,
    OperationTypeSingleString,
    OperationTypeStringTuple,
    PrincipalPartMarker,
    Rule,
    RuleSequence,
    SimpleRule,
    SingleStringMarker,
    StringMapRule,
    StringTupleMarker,
    UnorderedMarker,
    UnorderedOperation,
)
from src.yaml.yaml_server import get_yaml_data_safe, get_yaml_path


@pytest.fixture
def restore_diphthongization_rule():
    yaml_basename = "vowel_alternations"
    yaml_data = get_yaml_data_safe("Rules", yaml_basename)
    yaml_path = get_yaml_path("Rules", yaml_basename)

    yield

    # ensure original YAML data restored at test completion
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)


@pytest.fixture
def restore_vowel_patterns():
    yaml_basename = "vowel_sequences"
    yaml_data = get_yaml_data_safe("Patterns", yaml_basename)
    yaml_path = get_yaml_path("Patterns", yaml_basename)

    yield

    # ensure original YAML data restored at test completion
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)


@pytest.fixture
def restore_domains_patterns():
    yaml_basename = "domains"
    yaml_data = get_yaml_data_safe("Patterns", yaml_basename)
    yaml_path = get_yaml_path("Patterns", yaml_basename)

    yield

    # ensure original YAML data restored at test completion
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)


@pytest.fixture
def restore_segments_inventory():
    yaml_basename = "segments"
    yaml_data = get_yaml_data_safe("Inventory", yaml_basename)
    yaml_path = get_yaml_path("Inventory", yaml_basename)

    yield

    # ensure original YAML data restored at test completion
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)


def test_rule_invalidation_from_rule_file(restore_diphthongization_rule):
    def rule_input():
        return word_fsa("pod")

    orig_rule_fst = get_rule_fst("diphthongization")
    orig_result = rule_input() @ orig_rule_fst
    orig_result = fsm_strings(orig_result, strip_all_tags=True)

    assert orig_result == ["pued"]

    # first test: touching file triggers recompilation
    # and rule results are the same before and after

    yaml_basename = "vowel_alternations"
    yaml_data = get_yaml_data_safe("Rules", yaml_basename)
    yaml_path = get_yaml_path("Rules", yaml_basename)

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input() @ new_rule_fst
    new_result = fsm_strings(new_result)

    # second test: edit the yaml data so rule output changes

    diphthongization_rule_index = next(
        [
            i
            for i, rule in enumerate(yaml_data["rules"])
            if rule["name"] == "diphthongization"
        ]
    )

    yaml_data["rules"][diphthongization_rule_index]["string_map"] = [
        ["e", "eee"],
        ["o", "ooo"],
    ]

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input() @ new_rule_fst
    new_result = fsm_strings(new_result, strip_all_tags=True)

    assert new_result == ["poood"]


def test_rule_invalidation_from_pattern_file(restore_domains_patterns):
    def rule_input():
        return word_fsa("pod")

    orig_rule_fst = get_rule_fst("diphthongization")
    orig_result = rule_input() @ orig_rule_fst
    orig_result = fsm_strings(orig_result, strip_all_tags=True)

    assert orig_result == ["pued"]

    # first test: touching file triggers recompilation
    # and rule results are the same before and after

    yaml_basename = "domains"
    yaml_data = get_yaml_data_safe("Patterns", yaml_basename)
    yaml_path = get_yaml_path("Patterns", yaml_basename)

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input() @ new_rule_fst
    new_result = fsm_strings(new_result)

    # second test: edit the yaml data so rule output changes

    coda_pattern_index = [
        i
        for i, pattern in enumerate(yaml_data["patterns"])
        if pattern["name"] == "word_final_coda"
    ][0]

    yaml_data["patterns"][coda_pattern_index]["pattern"] = "foo"

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input() @ new_rule_fst
    new_result = fsm_strings(new_result, strip_all_tags=True)

    assert new_result == ["pod"]

    foo_result = word_fsa("pofoo") @ new_rule_fst
    foo_result = fsm_strings(foo_result, strip_all_tags=True)

    assert foo_result == ["puefoo"]


def test_rule_invalidation_from_inventory_file(restore_segments_inventory):
    def rule_input():
        return word_fsa("pod")

    orig_rule_fst = get_rule_fst("diphthongization")
    orig_result = rule_input() @ orig_rule_fst
    orig_result = fsm_strings(orig_result, strip_all_tags=True)

    assert orig_result == ["pued"]

    # first test: touching file triggers recompilation
    # and rule results are the same before and after

    yaml_basename = "segments"
    yaml_data = get_yaml_data_safe("Inventory", yaml_basename)
    yaml_path = get_yaml_path("Inventory", yaml_basename)

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    new_result = rule_input() @ new_rule_fst
    new_result = fsm_strings(new_result)

    # second test: edit the yaml data so rule output changes

    consonant_index = [
        i for i, nodes in enumerate(yaml_data["data"]) if nodes["ref"] == "<C>"
    ][0]
    stop_index = [
        i
        for i, nodes in enumerate(yaml_data["data"][consonant_index]["children"])
        if nodes["ref"] == "<Stp>"
    ][0]

    yaml_data["data"][consonant_index]["children"][stop_index]["children"] = []

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_rule_fst = get_rule_fst("diphthongization")

    assert new_rule_fst is not orig_rule_fst

    with pytest.raises(ValueError):
        new_result = rule_input() @ new_rule_fst
        new_result = fsm_strings(new_result, strip_all_tags=True)
        breakpoint()


def test_pattern_invalidation_from_pattern_file(restore_vowel_patterns):
    pattern_str = "<diphthong>"
    orig_pattern = get_pattern_fsts()[pattern_str]
    orig_fsa = fsa(pattern_str)

    def pattern_input():
        return fsa("ie")

    pattern_intersect = filter_strings_by_pattern(pattern_input(), orig_pattern)
    fsa_intersect = filter_strings_by_pattern(pattern_input(), orig_fsa)

    assert pattern_intersect == ["ie"]
    assert fsa_intersect == ["ie"]

    # first test: touching file triggers recompilation
    # and rule results are the same before and after

    yaml_basename = "vowel_sequences"
    yaml_data = get_yaml_data_safe("Patterns", yaml_basename)
    yaml_path = get_yaml_path("Patterns", yaml_basename)

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_pattern = get_pattern_fsts()[pattern_str]
    new_fsa = fsa(pattern_str)

    pattern_intersect = filter_strings_by_pattern(pattern_input(), new_pattern)
    fsa_intersect = filter_strings_by_pattern(pattern_input(), new_fsa)

    assert pattern_intersect == ["ie"]
    assert fsa_intersect == ["ie"]

    assert new_pattern is not orig_pattern
    assert new_fsa is not orig_fsa

    # second test: edit the yaml data so pattern output changes

    diphthong_pattern_idnex = [
        i
        for i, pattern in enumerate(yaml_data["patterns"])
        if pattern["ref"] == "<diphthong>"
    ][0]

    yaml_data["patterns"][diphthong_pattern_idnex]["pattern"] = "foo"

    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f)

    new_pattern = get_pattern_fsts()[pattern_str]
    new_fsa = fsa(pattern_str)

    pattern_intersect = filter_strings_by_pattern(pattern_input(), new_pattern)
    fsa_intersect = filter_strings_by_pattern(pattern_input(), new_fsa)

    assert pattern_intersect == []
    assert fsa_intersect == []

    assert new_pattern is not orig_pattern
    assert new_fsa is not orig_fsa

    pattern_intersect = filter_strings_by_pattern(fsa("foo"), new_pattern)
    fsa_intersect = filter_strings_by_pattern(fsa("foo"), new_fsa)

    assert pattern_intersect == ["foo"]
    assert fsa_intersect == ["foo"]
