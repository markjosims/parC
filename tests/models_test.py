import json

import msgspec
from pytest import raises

from src.models import (
    Feature,
    FeatureCombinationFile,
    FeatureCombinationFileRef,
    FeatureDefinitionFile,
    FeatureMarker,
    FeatureMarkerFile,
    FeatureMarkerFileRef,
    GrammarFile,
    InventoryFile,
    InventoryNode,
    Marker,
    MultiFeatureMarker,
    MultiFeatureMarkerFile,
    MultiFeatureMarkerFileRef,
    NestedNode,
    ParadigmFile,
    ParadigmFilter,
    PartOfSpeechFile,
    PartOfSpeechFileRef,
    Pattern,
    PatternFile,
    PhonesNode,
    PrefixMarker,
    PrincipalPartMarker,
    ReplaceMarker,
    Rule,
    RuleFile,
    RuleMarker,
    RuleRef,
    RuleSequence,
    SimpleRule,
    StringMapRule,
    SuffixMarker,
    SuppletionMarker,
    TagsNode,
    Token,
    _reserved_symbols,
)

"""
## Phonology module tests

### Inventory tests
"""


def test_inventory_node_construction():
    """
    Test that the inventory nodes can be instantiated and serialized/deserialized
    """
    phones_node = PhonesNode(
        id="<T>",
        name="Test Phones Node",
        data=("p", "t", "k"),
    )
    phones_node_json_bytes = msgspec.json.encode(phones_node)
    phones_node_json = json.loads(phones_node_json_bytes.decode("utf-8"))
    phones_node_json_expected = {
        "id": "<T>",
        "id": "Test Phones Node",
        "kind": "phones",
        "data": ["p", "t", "k"],
    }
    assert phones_node_json == phones_node_json_expected

    tags_node = TagsNode(
        id="<ToneTags>",
        name="Test Tags Node",
        data=("[TBU]", "[FLOAT]"),
    )
    tags_node_json_bytes = msgspec.json.encode(tags_node)
    tags_node_json = json.loads(tags_node_json_bytes.decode("utf-8"))
    tags_node_json_expected = {
        "id": "<ToneTags>",
        "name": "Test Tags Node",
        "kind": "tags",
        "data": ["[TBU]", "[FLOAT]"],
    }
    assert tags_node_json == tags_node_json_expected

    nested_node = NestedNode(
        id="<C>",
        name="Test Nested Node",
        data=(phones_node, tags_node),
    )

    nested_node_json_bytes = msgspec.json.encode(nested_node)
    nested_node_json = json.loads(nested_node_json_bytes.decode("utf-8"))
    nested_node_json_expected = {
        "id": "<C>",
        "name": "Test Nested Node",
        "kind": "nested",
        "data": [phones_node_json_expected, tags_node_json_expected],
    }
    assert nested_node_json == nested_node_json_expected

    inventory_file = InventoryFile(
        data=(phones_node, tags_node, nested_node),
        id="inventory",
    )
    inventory_file_json_bytes = msgspec.json.encode(inventory_file)
    inventory_file_json = json.loads(inventory_file_json_bytes.decode("utf-8"))
    inventory_file_json_expected = {
        "kind": "Inventory",
        "data": [
            phones_node_json_expected,
            tags_node_json_expected,
            nested_node_json_expected,
        ],
        "id": "inventory",
    }
    assert inventory_file_json == inventory_file_json_expected


def test_inventory_node_union_construction():
    """
    Test that the inventory nodes can be instantiated and serialized/deserialized
    """
    phones_node = PhonesNode(
        id="<T>",
        name="Test Phones Node",
        data=("p", "t", "k"),
    )
    phones_node_json = {
        "id": "<T>",
        "name": "Test Phones Node",
        "kind": "phones",
        "data": ["p", "t", "k"],
    }
    phones_node_from_union = msgspec.convert(phones_node_json, InventoryNode)
    assert phones_node == phones_node_from_union

    tags_node = TagsNode(
        id="<ToneTags>",
        name="Test Tags Node",
        data=("[TBU]", "[FLOAT]"),
    )
    tags_node_json = {
        "id": "<ToneTags>",
        "name": "Test Tags Node",
        "kind": "tags",
        "data": ["[TBU]", "[FLOAT]"],
    }
    tags_node_from_union = msgspec.convert(tags_node_json, InventoryNode)
    assert tags_node == tags_node_from_union

    nested_node = NestedNode(
        id="<C>",
        name="Test Nested Node",
        data=(phones_node, tags_node),
    )

    nested_node_json = {
        "id": "<C>",
        "name": "Test Nested Node",
        "kind": "nested",
        "data": [phones_node_json, tags_node_json],
    }
    nested_node_from_union = msgspec.convert(nested_node_json, InventoryNode)
    assert nested_node == nested_node_from_union

    inventory_file = InventoryFile(
        data=(phones_node, tags_node, nested_node),
        id="inventory",
    )
    inventory_file_json = {
        "kind": "Inventory",
        "data": [
            phones_node_json,
            tags_node_json,
            nested_node_json,
        ],
        "id": "inventory",
    }
    inventory_file_from_union = msgspec.convert(inventory_file_json, GrammarFile)
    assert inventory_file == inventory_file_from_union


def test_inventory_node_hashable():
    """
    Test that the inventory nodes are hashable and can be used as dictionary keys
    """
    phones_node1 = PhonesNode(
        id="<T>",
        name="Test Phones Node 1",
        data=("p", "t", "k"),
    )
    phones_node2 = PhonesNode(
        id="<T>",
        name="Test Phones Node 2",
        data=("p", "t", "k"),
    )
    tags_node = TagsNode(
        id="<ToneTags>",
        name="Test Tags Node",
        data=("[TBU]", "[FLOAT]"),
    )
    nested_node = NestedNode(
        id="<C>",
        name="Test Nested Node",
        data=(phones_node1, tags_node),
    )

    # Test that the nodes are hashable and can be used as dictionary keys
    node_dict = {
        phones_node1: "phones_node1",
        phones_node2: "phones_node2",
        tags_node: "tags_node",
        nested_node: "nested_node",
    }
    assert node_dict[phones_node1] == "phones_node1"
    assert node_dict[phones_node2] == "phones_node2"
    assert node_dict[tags_node] == "tags_node"
    assert node_dict[nested_node] == "nested_node"


def test_inventory_node_rejects_malformed_strings():
    """
    Test that the inventory nodes reject malformed strings
    """
    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "id": "<T>",
                "name": "Test Phones Node",
                "data": ("p", "t", "k", 123),  # Invalid: 123 is not a string
            },
            PhonesNode,
        )

    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "id": "<T",  # Invalid: missing closing angle bracket
                "name": "Test Phones Node",
                "data": ("p", "t", "k"),
            },
            PhonesNode,
        )

    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "id": "<T>>",
                "name": "Test Phones Node",
                "data": ("p", "t", "k"),
            },
            PhonesNode,
        )

    for symbol in _reserved_symbols:
        with raises(msgspec.ValidationError):
            msgspec.convert(
                {
                    "id": "<T>",
                    "name": "Test Phones Node",
                    "data": ("p", "t", "k", symbol),
                },
                PhonesNode,
            )

    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "id": "<ToneTags>",
                "name": "Test Tags Node",
                "data": ("[TBU]", "[FLOAT]", None),  # Invalid: None is not a string
            },
            TagsNode,
        )

    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "id": "<C>",
                "name": "Test Nested Node",
                "data": ("not_a_node",),  # Invalid: "not_a_node" is not a valid node
            },
            NestedNode,
        )


"""
### Pattern tests
"""


def test_pattern_file_construction():
    """
    Test that the pattern file can be instantiated and serialized/deserialized
    """
    pattern1 = Pattern(pattern="<C><V><C>?", id="Syllable")
    pattern2 = Pattern(pattern="<V><TBU><N>o", id="Some suffix")
    pattern3 = Pattern(pattern="(<C>|s{^<Fricative>})", id="Onset")
    pattern_file = PatternFile(
        data=(pattern1, pattern2, pattern3),
        id="patterns",
    )
    pattern_file_json_bytes = msgspec.json.encode(pattern_file)
    pattern_file_json = json.loads(pattern_file_json_bytes.decode("utf-8"))
    pattern_file_json_expected = {
        "kind": "Pattern",
        "data": [
            {
                "pattern": "<C><V><C>?",
                "id": "Syllable",
                "test_includes": None,
                "test_excludes": None,
            },
            {
                "pattern": "<V><TBU><N>o",
                "id": "Some suffix",
                "test_includes": None,
                "test_excludes": None,
            },
            {
                "pattern": "(<C>|s{^<Fricative>})",
                "id": "Onset",
                "test_includes": None,
                "test_excludes": None,
            },
        ],
        "id": "patterns",
    }
    assert pattern_file_json == pattern_file_json_expected


def test_pattern_doesnt_reject_ungrammatical_strings():
    """
    Pattern parsing is not handled at construction time,
    so we test that ungrammatical strings are accepted here.
    """

    for symbol in _reserved_symbols:
        pattern = Pattern(pattern=symbol, id="Symbol")

    nonsense_braces_pattern = Pattern(pattern="}]{)")


"""
### Rules tests
"""


def test_rule_construction():
    """
    Test that the rules can be instantiated and serialized/deserialized
    """
    simple_rule = SimpleRule(
        id="Test Simple Rule",
        input_pattern="<C><V>",
        output_pattern="<V><C>",
        description="A simple rule that swaps consonants and vowels.",
        left_context="<S>",
        right_context="<E>",
    )
    simple_rule_json_bytes = msgspec.json.encode(simple_rule)
    simple_rule_json = json.loads(simple_rule_json_bytes.decode("utf-8"))
    simple_rule_json_expected = {
        "kind": "simple",
        "id": "Test Simple Rule",
        "input_pattern": "<C><V>",
        "output_pattern": "<V><C>",
        "description": "A simple rule that swaps consonants and vowels.",
        "left_context": "<S>",
        "right_context": "<E>",
    }
    assert simple_rule_json == simple_rule_json_expected

    string_map_rule = StringMapRule(
        id="Test String Map Rule",
        string_map=(("a", "b"), ("c", "d")),
        description="A rule that maps strings.",
        left_context="<S>",
        right_context="<E>",
    )
    string_map_rule_json_bytes = msgspec.json.encode(string_map_rule)
    string_map_rule_json = json.loads(string_map_rule_json_bytes.decode("utf-8"))
    string_map_rule_json_expected = {
        "kind": "string_map",
        "id": "Test String Map Rule",
        "string_map": [["a", "b"], ["c", "d"]],
        "description": "A rule that maps strings.",
        "left_context": "<S>",
        "right_context": "<E>",
    }
    assert string_map_rule_json == string_map_rule_json_expected

    rule_sequence = RuleSequence(
        id="Test Rule Sequence",
        rules=("rule1", "rule2", "rule3"),
        description="A sequence of rules.",
    )
    rule_sequence_json_bytes = msgspec.json.encode(rule_sequence)
    rule_sequence_json = json.loads(rule_sequence_json_bytes.decode("utf-8"))
    rule_sequence_json_expected = {
        "kind": "rule_sequence",
        "id": "Test Rule Sequence",
        "rules": ["rule1", "rule2", "rule3"],
        "description": "A sequence of rules.",
    }
    assert rule_sequence_json == rule_sequence_json_expected


def test_rule_union_constructor():
    """
    Test that the generic Rule class can construct various Rule kinds.
    """
    simple_rule = SimpleRule(
        id="Test Simple Rule",
        input_pattern="<C><V>",
        output_pattern="<V><C>",
        description="A simple rule that swaps consonants and vowels.",
        left_context="<S>",
        right_context="<E>",
    )
    simple_rule_json = {
        "kind": "simple",
        "id": "Test Simple Rule",
        "input_pattern": "<C><V>",
        "output_pattern": "<V><C>",
        "description": "A simple rule that swaps consonants and vowels.",
        "left_context": "<S>",
        "right_context": "<E>",
    }
    simple_rule_from_union = msgspec.convert(simple_rule_json, Rule)
    assert simple_rule == simple_rule_from_union

    string_map_rule = StringMapRule(
        id="Test String Map Rule",
        string_map=(("a", "b"), ("c", "d")),
        description="A rule that maps strings.",
        left_context="<S>",
        right_context="<E>",
    )
    string_map_rule_json = {
        "kind": "string_map",
        "id": "Test String Map Rule",
        "string_map": [["a", "b"], ["c", "d"]],
        "description": "A rule that maps strings.",
        "left_context": "<S>",
        "right_context": "<E>",
    }
    string_map_rule_from_union = msgspec.convert(string_map_rule_json, Rule)
    assert string_map_rule == string_map_rule_from_union

    rule1_ref = RuleRef(ref="rule1")
    rule2_ref = RuleRef(ref="rule2")
    rule3_ref = RuleRef(ref="rule3")
    rule_sequence = RuleSequence(
        id="Test Rule Sequence",
        rules=(rule1_ref, rule2_ref, rule3_ref),
        description="A sequence of rules.",
    )

    rule_sequence_json = {
        "kind": "rule_sequence",
        "id": "Test Rule Sequence",
        "rules": [
            {"kind": "Rule", "ref": "rule1"},
            {"kind": "Rule", "ref": "rule2"},
            {"kind": "Rule", "ref": "rule3"},
        ],
        "description": "A sequence of rules.",
    }
    rule_sequence_from_union = msgspec.convert(rule_sequence_json, Rule)
    assert rule_sequence == rule_sequence_from_union


def test_rule_sequence_rejects_malformed_string():
    """
    Test that the RuleSequence rejects strings missing the '' prefix
    """
    with raises(msgspec.ValidationError):
        msgspec.convert(
            {
                "kind": "rule_sequence",
                "id": "Test Rule Sequence",
                "rules": (
                    "rule1",
                    "rule2",
                    "rule3",
                ),  # Invalid: "rule1" is missing the '' prefix
                "description": "A sequence of rules.",
            },
            RuleSequence,
        )


"""
Morphology tests
"""


def test_feature_construction():
    tense_feature = Feature(
        id="Tense",
        values=("past", "present", "future"),
    )
    tense_feature_json_bytes = msgspec.json.encode(tense_feature)
    tense_feature_json = json.loads(tense_feature_json_bytes.decode("utf-8"))
    tense_feature_json_expected = {
        "id": "Tense",
        "values": ["past", "present", "future"],
    }
    assert tense_feature_json == tense_feature_json_expected

    mood_feature = Feature(
        id="Mood",
        values=("indicative", "subjunctive", "imperative"),
    )
    mood_feature_json_bytes = msgspec.json.encode(mood_feature)
    mood_feature_json = json.loads(mood_feature_json_bytes.decode("utf-8"))
    mood_feature_json_expected = {
        "id": "Mood",
        "values": ["indicative", "subjunctive", "imperative"],
    }
    assert mood_feature_json == mood_feature_json_expected

    feature_definitions_file = FeatureDefinitionFile(
        data=(tense_feature, mood_feature),
        id="verb_features",
    )
    feature_definitions_file_json_bytes = msgspec.json.encode(feature_definitions_file)
    feature_definitions_file_json = json.loads(
        feature_definitions_file_json_bytes.decode("utf-8")
    )
    feature_definitions_file_json_expected = {
        "kind": "FeatureDefinition",
        "data": [
            tense_feature_json_expected,
            mood_feature_json_expected,
        ],
        "id": "verb_features",
    }
    assert feature_definitions_file_json == feature_definitions_file_json_expected


def test_marker_construction():
    suffix = SuffixMarker(value="-ed", stage="tense_suffix")
    suffix_json_bytes = msgspec.json.encode(suffix)
    suffix_json = json.loads(suffix_json_bytes.decode("utf-8"))
    suffix_json_expected = {
        "kind": "suffix",
        "value": "-ed",
        "stage": "tense_suffix",
    }
    assert suffix_json == suffix_json_expected

    prefix = PrefixMarker(value="un-", stage="negation_prefix")
    prefix_json_bytes = msgspec.json.encode(prefix)
    prefix_json = json.loads(prefix_json_bytes.decode("utf-8"))
    prefix_json_expected = {
        "kind": "prefix",
        "value": "un-",
        "stage": "negation_prefix",
    }
    assert prefix_json == prefix_json_expected

    stop_devoicing = ReplaceMarker(value=("<D>", "<T>"), stage="consonant_mutation")
    stop_devoicing_json_bytes = msgspec.json.encode(stop_devoicing)
    stop_devoicing_json = json.loads(stop_devoicing_json_bytes.decode("utf-8"))
    stop_devoicing_json_expected = {
        "kind": "replace",
        "value": ["<D>", "<T>"],
        "stage": "consonant_mutation",
    }
    assert stop_devoicing_json == stop_devoicing_json_expected


def test_marker_union_construction():
    suffix_json = {
        "kind": "suffix",
        "value": "-ed",
        "stage": "tense_suffix",
    }
    suffix_from_union = msgspec.convert(suffix_json, Marker)
    assert isinstance(suffix_from_union, SuffixMarker)
    assert suffix_from_union.value == "-ed"
    assert suffix_from_union.stage == "tense_suffix"

    prefix_json = {
        "kind": "prefix",
        "value": "un-",
        "stage": "negation_prefix",
    }
    prefix_from_union = msgspec.convert(prefix_json, Marker)
    assert isinstance(prefix_from_union, PrefixMarker)
    assert prefix_from_union.value == "un-"
    assert prefix_from_union.stage == "negation_prefix"

    stop_devoicing_json = {
        "kind": "replace",
        "value": ("<D>", "<T>"),
        "stage": "consonant_mutation",
    }
    stop_devoicing_from_union = msgspec.convert(stop_devoicing_json, Marker)
    assert isinstance(stop_devoicing_from_union, ReplaceMarker)
    assert stop_devoicing_from_union.value == ("<D>", "<T>")
    assert stop_devoicing_from_union.stage == "consonant_mutation"


def test_feature_marker_construction():
    """
    Test FeatureMarker and FeatureMarkerFile serialization and union behavior
    """
    fm = FeatureMarker(
        feature_value="past",
        markers=(
            SuffixMarker(value="-ed", stage="tense_suffix"),
            ReplaceMarker(value=("<D>", "<T>"), stage="consonant_mutation"),
        ),
    )
    fm_json_bytes = msgspec.json.encode(fm)
    fm_json = json.loads(fm_json_bytes.decode("utf-8"))
    fm_json_expected = {
        "feature_value": "past",
        "markers": [
            {"kind": "suffix", "value": "-ed", "stage": "tense_suffix"},
            {"kind": "replace", "value": ["<D>", "<T>"], "stage": "consonant_mutation"},
        ],
    }
    assert fm_json == fm_json_expected

    fm_file = FeatureMarkerFile(data=(fm,), feature="Tense", id="tense_markers")
    fm_file_json_bytes = msgspec.json.encode(fm_file)
    fm_file_json = json.loads(fm_file_json_bytes.decode("utf-8"))
    fm_file_json_expected = {
        "kind": "FeatureMarkers",
        "data": [fm_json_expected],
        "feature": "Tense",
        "id": "tense_markers",
    }
    assert fm_file_json == fm_file_json_expected


def test_multifeature_marker_construction():
    """
    Test MultiFeatureMarker and MultiFeatureMarkerFile serialization
    """
    mfm = MultiFeatureMarker(
        feature_values={"Tense": "past", "Mood": "indicative"},
        markers=(PrefixMarker(value="un-", stage="negation_prefix"),),
    )
    mfm_json_bytes = msgspec.json.encode(mfm)
    mfm_json = json.loads(mfm_json_bytes.decode("utf-8"))
    mfm_json_expected = {
        "feature_values": {"Tense": "past", "Mood": "indicative"},
        "markers": [{"kind": "prefix", "value": "un-", "stage": "negation_prefix"}],
    }
    assert mfm_json == mfm_json_expected

    mfm_file = MultiFeatureMarkerFile(data=(mfm,), id="mf_markers")
    mfm_file_json_bytes = msgspec.json.encode(mfm_file)
    mfm_file_json = json.loads(mfm_file_json_bytes.decode("utf-8"))
    mfm_file_json_expected = {
        "kind": "MultiFeatureMarkers",
        "data": [mfm_json_expected],
        "id": "mf_markers",
    }
    assert mfm_file_json == mfm_file_json_expected


def test_feature_combinations_file_and_validation():
    """
    Test FeatureCombinationFile serialization and validation for ObjectRef
    """
    fc1 = {"Tense": ("past", "present")}
    fc2 = {"Mood": "*"}
    fc_file = FeatureCombinationFile(
        part_of_speech=PartOfSpeechFileRef(ref="pos"), data=(fc1, fc2)
    )
    fc_file_json_bytes = msgspec.json.encode(fc_file)
    fc_file_json = json.loads(fc_file_json_bytes.decode("utf-8"))
    fc_file_json_expected = {
        "kind": "FeatureCombinations",
        "part_of_speech": {"kind": "PartOfSpeech", "ref": "pos"},
        "data": [{"Tense": ["past", "present"]}, {"Mood": "*"}],
    }
    assert fc_file_json == fc_file_json_expected

    # Validation: part_of_speech must be an ObjectRef (start with )
    with raises(msgspec.ValidationError):
        msgspec.convert({"part_of_speech": "pos", "data": []}, FeatureCombinationFile)


def test_paradigm_and_part_of_speech_file_construction_and_union():
    """
    Test ParadigmFile and PartOfSpeechFile serialization and GrammarFile union conversion
    """
    pfilt = ParadigmFilter(lexical_features={"lemma": "run"}, pattern="^r")
    paradigm = ParadigmFile(
        part_of_speech=PartOfSpeechFileRef(ref="pos"),
        filter=pfilt,
        feature_markers={
            "Tense": FeatureMarkerFileRef(ref="tense_markers"),
            "Mood": "present",
            "X": None,
        },
        stage_order=("stage1", "stage2"),
        global_markers=(PrefixMarker(value="pre-", stage=None),),
        feature_value_combinations=FeatureCombinationFileRef(ref="verb_features"),
        multifeature_markers=(
            MultiFeatureMarkerFileRef(
                ref="m1",
            ),
        ),
        id="paradigm",
    )
    paradigm_json_bytes = msgspec.json.encode(paradigm)
    paradigm_json = json.loads(paradigm_json_bytes.decode("utf-8"))
    paradigm_json_expected = {
        "kind": "Paradigm",
        "part_of_speech": {"kind": "PartOfSpeech", "ref": "pos"},
        "filter": {"lexical_features": {"lemma": "run"}, "pattern": "^r"},
        "feature_markers": {
            "Tense": {"kind": "FeatureMarkers", "ref": "tense_markers"},
            "Mood": "present",
            "X": None,
        },
        "stage_order": ["stage1", "stage2"],
        "global_markers": [{"kind": "prefix", "value": "pre-", "stage": None}],
        "feature_value_combinations": {
            "kind": "FeatureCombinations",
            "ref": "verb_features",
        },
        "multifeature_markers": [{"kind": "MultiFeatureMarkers", "ref": "m1"}],
        "id": "paradigm",
    }
    assert paradigm_json == paradigm_json_expected

    pos = PartOfSpeechFile(
        inflectional_features=("Tense", "Mood"),
        lexical_features=("lemma",),
        principal_parts=("present_stem", "past_stem"),
        id="verb",
    )
    pos_json_bytes = msgspec.json.encode(pos)
    pos_json = json.loads(pos_json_bytes.decode("utf-8"))
    pos_json_expected = {
        "kind": "PartOfSpeech",
        "inflectional_features": ["Tense", "Mood"],
        "lexical_features": ["lemma"],
        "principal_parts": ["present_stem", "past_stem"],
        "id": "verb",
    }
    assert pos_json == pos_json_expected

    # Test union conversion via GrammarFile
    pos_from_union = msgspec.convert(pos_json, GrammarFile)
    assert pos_from_union == pos
    paradigm_from_union = msgspec.convert(paradigm_json, GrammarFile)
    assert paradigm_from_union == paradigm


def test_token_len():
    """
    Test Token length helper
    """
    tok = Token("abc", "phone")
    assert len(tok) == 3
