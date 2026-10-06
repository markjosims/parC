import os

import pynini
import pytest

from src.constants import PROJECT_ROOT
from src.grammar.acceptor_compilation import (
    filter_strings_by_pattern,
    fsa,
    fsm_strings,
    word_fsa,
)
from src.grammar.marker_resolution import get_markers_for_paradigm
from src.grammar.paradigm_compilation import _get_or_build, inflect, parse, search
from src.grammar.transducer_compilation import compile_marker
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
from src.yaml.yaml_server import get_yaml_data_safe


def test_suffix():
    marker = SingleStringMarker(kind="suffix", value="-sufijo")
    fst = compile_marker(marker)
    assert isinstance(fst, pynini.Fst)

    root = word_fsa("rama")
    result = pynini.compose(root, fst)
    assert result.num_states() > 0
    result_strings = fsm_strings(result, strip_all_tags=True)
    assert "rama-sufijo" in result_strings


def test_prefix():
    marker = SingleStringMarker(kind="prefix", value="antes-")
    fst = compile_marker(marker)
    assert isinstance(fst, pynini.Fst)

    root = word_fsa("historia")
    result = pynini.compose(root, fst)
    assert result.num_states() > 0
    result_strings = fsm_strings(result, strip_all_tags=True)
    assert "antes-historia" in result_strings


def test_rule():
    diphthongization_rule = "$diphthongization"
    marker = SingleStringMarker(kind="rule", value=diphthongization_rule)
    fst = compile_marker(marker)
    assert isinstance(fst, pynini.Fst)

    root = word_fsa("pod")
    result = pynini.compose(root, fst)
    assert result.num_states() > 0
    result_strings = fsm_strings(result, strip_all_tags=True)
    assert "pued" in result_strings


def test_2sg_a_class():

    # test fetching and applying markers manually

    feature_values = {
        "person_number": "2sg",
        "tense": "present",
        "mood": "indicative",
    }

    markers_2sg_a_class = get_markers_for_paradigm(
        feature_values=feature_values,
        paradigm_name="verb_a_stem",
    )

    assert len(markers_2sg_a_class) == 1
    marker = markers_2sg_a_class[0]
    assert isinstance(marker, SingleStringMarker)
    assert marker.kind == "suffix"
    assert marker.value == "-as"

    fst = compile_marker(marker)
    assert isinstance(fst, pynini.Fst)

    part_of_speech = get_yaml_data_safe(kind="Paradigm", yaml_basename="$verb_a_stem")[
        "part_of_speech"
    ]
    roots = get_roots_with_gloss(lexicon_basename=part_of_speech, gloss="speak")
    assert roots == ["habl"]

    root = roots[0]
    root_fsa = word_fsa(root)
    result = pynini.compose(root_fsa, fst)
    assert result.num_states() > 0
    result_strings = fsm_strings(result, strip_all_tags=True)
    expected_form = "habl-as"
    assert expected_form in result_strings

    # test inflection graph

    # here we invalidate the cache whenever the test is run
    # TODO: directly test automatic cache invalidation when source files are changed
    _get_or_build(graph_type="inflect", paradigm_name="verb_a_stem", force_rebuild=True)

    inflect_result = inflect(
        root=root, feature_values=feature_values, name="verb_a_stem"
    )
    assert inflect_result == result_strings

    _get_or_build(graph_type="parse", paradigm_name="verb_a_stem", force_rebuild=True)

    parse_result = parse(expected_form, kind="Paradigm", name="verb_a_stem")
    expected_parse = {
        "root": "habl",
        "gloss": "speak",
        "features": {"mood": "indicative", "tense": "present", "person_number": "2sg"},
    }
    assert len(parse_result) == 1
    assert parse_result[0] == expected_parse

    search_query = "habl-os"
    search_result = search(
        form=search_query, name="verb_a_stem", kind="Paradigm", nshortest=5
    )
    form_hits = [hit["form"] for hit in search_result]
    assert "habl-as" in form_hits
    assert "habl-o" in form_hits
