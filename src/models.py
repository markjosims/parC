"""
# models.py
Structs for grammar data objects. Each YAML file type has a
struct defining the schema for the entire file, which in turn
is comprised of structs for data objects defined by the file
(e.g. the PatternFile struct has Pattern as a sub-struct).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Iterable, Literal, NamedTuple

import msgspec
import pynini

from src.diagnostics import Diagnostic, build_diagnostic_error
from src.grammar.fst_utils import serialize_feature_str, stringify_features

"""
Shared models
"""

TokenId = Annotated[
    str,
    msgspec.Meta(
        pattern=r"^<[^>]+>$",
        description="A unique identifier for a token (i.e. inventory item or pattern), circumfixed with angle brackets.",
    ),
]


TokenRegex = re.compile("<[^>]+>")

ObjectId = Annotated[
    str,
    msgspec.Meta(
        description="A unique identifier for an object (grammar file or some data contained within a grammar file).",
    ),
]

PatternStr = Annotated[
    str, msgspec.Meta(description="A parC-flavored regex string indicating an FSA")
]


class TransitiveRelation(msgspec.Struct, kw_only=True, frozen=True):
    input_pattern: PatternStr
    output_pattern: PatternStr


"""
## Phonology modules

Contains the following sublcasses:
- Inventory
- Patterns
- Rules
"""

_reserved_symbols = r".+*?{}[]()<>"
_reserved_symbols_escaped = r"\.\+\*\?\{\}\[\]\(\)<>"


# tags must be circumfixed with square brackets
# no reserved symbols allowed inside square brackets
Tag = Annotated[
    str, msgspec.Meta(pattern=r"^\[[^" + _reserved_symbols_escaped + r"]+\]$")
]


# phones cannot contain any of the reserved symbols, viz: .+*?{}[]()<>
Phone = Annotated[
    str, msgspec.Meta(pattern=r"^[^" + _reserved_symbols_escaped + r"]+$")
]


class PhonesNode(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="phones"
):
    """
    A single inventory node containing an array of phones.
    Phones are strings of one or more characters excluding
    the reserved symbols: .+*?{}[]()<>.
    """

    id: TokenId
    data: tuple[Phone, ...]
    description: str | None = None


class TagsNode(msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="tags"):
    """
    A single inventory node containing an array of tags
    where each tag is a string circumfixed with [square brackets].
    No other reserved symbols are allowed inside the square brackets.
    """

    id: TokenId
    data: tuple[Tag, ...]
    description: str | None = None


class NestedNode(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="nested"
):
    """
    A single inventory node containing an array of nested
    inventory nodes.
    """

    id: TokenId
    data: tuple[Node, ...]
    description: str | None = None


Node = PhonesNode | TagsNode | NestedNode


class InventoryFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="Inventory"
):
    """
    A file containing an inventory of phones, tags, and nested nodes.
    """

    id: ObjectId
    data: tuple[Node, ...]


class Pattern(msgspec.Struct, kw_only=True, frozen=True):
    """
    A regular expression pattern and, optionally, 'include' and 'exclude'
    strings for unit testing.

    The pattern string must conform to the grammar of parC-flavored Regex,
    handled by `src.grammar.acceptor_compilation.py` and must only contain
    phones and tags described in the Inventory, or reserved symbols.

    No string validation is handled here, and is instead left to
    `acceptor_compilation.py`.
    """

    pattern: PatternStr
    test_includes: tuple[str] | None = None
    test_excludes: tuple[str] | None = None
    id: ObjectId


class PatternFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="Pattern"
):
    """
    A file containing a list of patterns.
    """

    id: ObjectId
    data: tuple[Pattern, ...]


class Token(NamedTuple):
    value: str
    kind: Literal[
        "phone",
        "tag",
        "id",
        "bow_eow",
        "edit_flag",
        "special_ref",
        "unary_operator",
        "pipe_operator",
        "caret_operator",
        "boundary",
        "left_delimiter",
        "right_delimiter",
    ]

    def __len__(self) -> int:
        return len(self.value)


"""
## Rules modules
"""


class SimpleRule(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="simple"
):
    """
    A context-sensitive rewrite rule.
    """

    id: ObjectId
    input_pattern: PatternStr = ""
    output_pattern: PatternStr = ""
    description: str = ""
    left_context: str = ""
    right_context: str = ""


class StringMapRule(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="string_map"
):
    """
    A rule for mapping strings.
    """

    id: ObjectId
    string_map: tuple[TransitiveRelation, ...]
    description: str = ""
    left_context: str = ""
    right_context: str = ""


class RuleSequence(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="rule_sequence"
):
    """
    A sequence of rules to be applied.
    Here just stored as a list of strings indicating rule names,
    which are resolved to rule data up in `fst_compilation.compile_rule`
    """

    id: ObjectId
    rules: tuple[str, ...]
    description: str = ""


Rule = SimpleRule | StringMapRule | RuleSequence


class RuleFile(msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="Rule"):
    id: ObjectId
    data: tuple[Rule, ...]


"""
## Exponence modules

    id: ObjectId
Contains the following submodules:
- FeatureDefinition
- InflectionStages
- FeatureMarkers
- MultiFeatureMarkers
"""


class Feature(msgspec.Struct, kw_only=True, frozen=True):
    """
    A feature with a name and a list of possible values.
    """

    id: ObjectId
    values: tuple[str, ...]


class FeatureDefinitionFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="FeatureDefinition"
):
    """
    A file containing a list of feature definitions.
    """

    id: ObjectId
    data: tuple[Feature, ...]


class InflectionStage(msgspec.Struct, kw_only=True, frozen=True):
    """
    A named stage for ordering inflectional operations.
    """

    id: ObjectId
    description: str | None = None


class InflectionStageFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="InflectionStage"
):
    """
    A file containing a list of inflection stages.
    """

    id: ObjectId
    data: tuple[InflectionStage, ...]


class PrefixMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="prefix"
):
    """
    A marker for a prefix operation.
    """

    form: PatternStr
    stage: str | None = None


class SuffixMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="suffix"
):
    """
    A marker for a suffix operation.
    """

    form: PatternStr
    stage: str | None = None


class SuppletionMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="suppletion"
):
    """
    A marker for a suppletion operation.
    """

    form: PatternStr
    stage: Literal["stem_selection"] = "stem_selection"


class RuleMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="rule"
):
    """
    A marker that applies a contextual rule.
    """

    rule: ObjectId
    stage: str | None = None


class ReplaceMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="replace"
):
    """
    A marker that applies a context-insensitive A->B replace rule.
    """

    relation: TransitiveRelation
    stage: str | None = None


class PrincipalPartMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="principal_part"
):
    """
    A marker that selects a principal part for the given lexeme.
    """

    principal_part_value: str
    stage: Literal["stem_selection"] = "stem_selection"


Marker = (
    PrefixMarker
    | SuffixMarker
    | ReplaceMarker
    | PrincipalPartMarker
    | RuleMarker
    | SuppletionMarker
)


class FeatureMarker(msgspec.Struct, kw_only=True, frozen=True):
    """
    A feature value paired with a tuple of markers which expone the feature value.
    """

    feature_value: str
    markers: tuple[Marker, ...]


class MultiFeatureMarker(msgspec.Struct, kw_only=True, frozen=True):
    """
    A collection of feature, value pairs exponed by a single tuple of Markers.
    """

    feature_values: dict[str, str]
    markers: tuple[Marker, ...]


class FeatureMarkerFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="FeatureMarker"
):
    """
    A file containing a list of feature markers.
    """

    id: ObjectId
    data: tuple[FeatureMarker, ...]
    feature: str
    global_stage: ObjectId | None = None
    inherits: str | None = None


class MultiFeatureMarkerFile(
    msgspec.Struct,
    kw_only=True,
    frozen=True,
    tag_field="kind",
    tag="MultiFeatureMarker",
):
    """
    A file containing a list of multi-feature markers.
    """

    id: ObjectId
    features: tuple[ObjectId, ...]
    data: tuple[MultiFeatureMarker, ...]
    global_stage: ObjectId | None = None
    inherits: str | None = None


"""
## Morphotactics modules

Contains the following submodules:
- FeatureCombinations
- Paradigm
"""

FeatureVectorType = dict[str, tuple[str] | Literal["*", "undefined"]]


class FeatureCombination(msgspec.Struct, kw_only=True, frozen=True):
    """
    Object mapping feature values to an array of strings indicating "
    possible values that feature may take on in the given combination, or a wildcard
    "*" to indicate the feature may take on any value, or "undefined" to indicate
    the feature must be undefined in this combination.
    """

    feature_vector: FeatureVectorType
    description: str | None = None


class FeatureCombinationFile(
    msgspec.Struct,
    kw_only=True,
    frozen=True,
    tag_field="kind",
    tag="FeatureCombination",
):
    """
    A file specifying a set of licit feature vectors for a given
    feature set.
    """

    id: ObjectId
    part_of_speech: str
    data: tuple[FeatureCombination, ...]


class FeatureMarkerReference(
    msgspec.Struct,
    kw_only=True,
    frozen=True,
    tag_field="kind",
    tag="feature_marker_file",
):
    """A reference to a FeatureMarker file that expones the given feature"""

    inflectional_feature: str
    feature_marker: str
    multifeature_behavior: Literal[
        "multifeature_overrides",
        "both_marked",
    ] = "multifeature_overrides"


class FixedFeatureValue(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="fixed_value"
):
    """A single feature value the current feature is fixed to for this paradigm"""

    inflectional_feature: str
    feature_value: str


class MultiFeatureOnly(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="multi_only"
):
    """Indicates the given feature is only exponed by MultiFeatureMarker files"""

    inflectional_feature: str


InflectionalFeatureSpecification = (
    FeatureMarkerReference | FixedFeatureValue | MultiFeatureOnly
)


class LexicalFeatureMarkerReference(
    msgspec.Struct,
    kw_only=True,
    frozen=True,
    tag_field="kind",
    tag="feature_marker_file",
):
    """A reference to a FeatureMarker file that expones the given feature"""

    lexical_feature: str
    feature_marker: str
    multifeature_behavior: Literal[
        "multifeature_overrides",
        "both_marked",
    ] = "multifeature_overrides"


class FixedLexicalFeatureValue(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="fixed_value"
):
    """A single feature value the current feature is fixed to for this paradigm"""

    lexical_feature: str
    feature_value: str


class LexicalMultiFeatureOnly(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="multi_only"
):
    """Indicates the given feature is only exponed by MultiFeatureMarker files"""

    lexical_feature: str


class UnrealizedLexicalFeature(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="unrealized"
):
    """
    (Only applies to lexical features) Indicates the given feature is not associated
    with any morphological process
    """

    lexical_feature: str


LexicalFeatureSpecification = (
    LexicalFeatureMarkerReference
    | FixedLexicalFeatureValue
    | LexicalMultiFeatureOnly
    | UnrealizedLexicalFeature
)


class ParadigmFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="Paradigm"
):
    """
    A file defining a paradigm (or partial paradigm) for a given part of speech.
    The `part_of_speech` and `feature_markers` fields are obligatory. `part_of_speech`
    must contain a reference to a PartOfSpeech config file, and `feature_markers` is a
    dictionary which must map every inflectional feature for the given part of speech to
    either (1) a reference to a `FeatureMarkers` config, (2) a str indicating a fixed
    feature value or (3) `None`, indicating that the feature is only exponed by
    `MultiFeatureMarkers` configs.

    Optional attributes include:
    - `stage_order`:    An array of names that defines the order staged operations are
                        applied in.
    - `global_markers`: An array of `Marker` objects that apply to all paradigm cells
                        (regardless of feature values)
    - `feature_value_combinations`: An object reference to a `FeatureValueCombinations`
                                    config that constrains what feature vectors are licit
                                    for the given paradigm.
    - `multifeature_markers`:       An array of object references pointing to a set of
                                    `MultiFeatureMarker` configs which expone inflection
                                    features for the current paradigm.
    """

    id: ObjectId
    part_of_speech: str
    inflectional_feature_specs: tuple[InflectionalFeatureSpecification, ...]
    lexical_feature_specs: tuple[LexicalFeatureSpecification, ...]
    filter_pattern: PatternStr | None = None
    stage_order: tuple[str, ...] | None = None
    global_markers: tuple[Marker, ...] | None = None
    feature_value_combinations: ObjectId | None = None
    multifeature_markers: tuple[str, ...] | None = None

    inherits: str | None = None


"""
## Lexicon modules

Contains the following submodules:
- WordList (no struct defined here, just a CSV file)
- PartOfSpeech
"""


class PartOfSpeechFile(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="PartOfSpeech"
):
    """
    A file defining a part of speech and its associated inflectional features.
    The `id` and `inflectional_features` fields are obligatory.
    Contains the following optional attributes:
    - `lexical_features`:   An array of strings indicating the lexical features
                            associated with the part of speech.
    - `principal_parts`:    Column names in the lexicon CSV that specify alternate stems
                            for a root (e.g., present_stem, past_stem)
    """

    id: ObjectId
    inflectional_features: tuple[str, ...]
    lexical_features: tuple[str, ...] | None = None
    principal_parts: tuple[str, ...] | None = None


"""
## Global union over grammar files
"""

GrammarFile = (
    InventoryFile
    | PatternFile
    | PartOfSpeechFile
    | RuleFile
    | FeatureDefinitionFile
    | InflectionStageFile
    | FeatureMarkerFile
    | MultiFeatureMarkerFile
    | FeatureCombinationFile
    | ParadigmFile
)

"""
## Map structs to names and directory locations
"""

UNION_TO_NAME = {
    Rule: "Rule",
    Marker: "Marker",
    Node: "Node",
    InflectionalFeatureSpecification: "InflectionalFeatureSpecification",
}


CONFIG_KIND_TO_STRUCT: dict[str, msgspec.Struct] = {
    "MultiFeatureMarker": MultiFeatureMarkerFile,
    "FeatureCombination": FeatureCombinationFile,
    "FeatureDefinition": FeatureDefinitionFile,
    "FeatureMarker": FeatureMarkerFile,
    "Inventory": InventoryFile,
    "Paradigm": ParadigmFile,
    "PartOfSpeech": PartOfSpeechFile,
    "Pattern": PatternFile,
    "Rule": RuleFile,
    "InflectionStage": InflectionStageFile,
}

CONFIG_KIND_TYPE = Literal[
    "MultiFeatureMarker",
    "FeatureCombination",
    "FeatureDefinition",
    "FeatureMarker",
    "Inventory",
    "Paradigm",
    "PartOfSpeech",
    "Pattern",
    "Rule",
]

# order to load configs so that later kinds
# depend on previous
CONFIG_KINDS_ORDERED = [
    "Inventory",
    "Pattern",
    "Rule",
    "InflectionStage",
    "FeatureDefinition",
    "PartOfSpeech",
    "FeatureMarker",
    "MultiFeatureMarker",
    "FeatureCombination",
    "Paradigm",
]

CONFIG_KIND_TO_PARDIR = {
    "ContingentFeatureMarker": "Exponence",
    "FeatureDefinition": "Exponence",
    "FeatureMarker": "Exponence",
    "InflectionStage": "Exponence",
    "MultiFeatureMarker": "Exponence",
    "Inventory": "Phonology",
    "Rule": "Phonology",
    "Pattern": "Phonology",
    "Paradigm": "Morphotactics",
    "FeatureCombination": "Morphotactics",
    "PartOfSpeech": "Lexicon",
    "Wordlist": "Lexicon",
}


"""
# Internal models
Data models and structs not directly related to
YAML config objects.
"""


class ReservedSymbols:
    bow = "[BOW]"
    eow = "[EOW]"
    insert = "[INSERT]"
    substitute = "[SUBSTITUTE]"
    delete = "[DELETE]"

    lexical_feature_start_tag = "[START_LEX_FEAT]"
    lexical_feature_end_tag = "[END_LEX_FEAT]"

    inflectional_feature_start_tag = "[START_INFLECT_FEAT]"
    inflectional_feature_end_tag = "[END_INFLECT_FEAT]"

    word_edge = "#"
    phone_ref = "<Phone>"
    flag_ref = "<tag>"
    sigma_ref = "<Sigma>"
    dot = "."
    epsilon_ref = "<Empty>"
    boundary_ref = "<Boundary>"

    affix_boundary = "-"
    clitic_boundary = "="
    periphrasis_break = "_"

    star = "*"
    plus = "+"
    optional = "?"
    union = "|"
    caret = "^"
    left_paren = "("
    right_paren = ")"
    # curly braces indicate union of tokens, e.g. {A B} matches either A or B
    # similar to square brackets in regex
    left_brace = "{"
    right_brace = "}"

    left_delimiters = (left_paren, left_brace)
    right_delimiters = (right_paren, right_brace)
    unary_operators = (star, plus, optional)
    pipe_operator = union  # (for now) pipe operator is only binary operator
    caret_operator = caret  # for negation in braced expressions
    reserved_refs = (phone_ref, flag_ref, epsilon_ref, dot, sigma_ref, boundary_ref)
    bow_eow_tags = (bow, eow)
    edit_tags = (insert, substitute, delete)
    feature_brackets = (
        lexical_feature_start_tag,
        lexical_feature_end_tag,
        inflectional_feature_start_tag,
        inflectional_feature_end_tag,
    )
    boundary_symbols = (affix_boundary, clitic_boundary, periphrasis_break)

    reserved_symbols = (
        left_delimiters
        + right_delimiters
        + unary_operators
        + (pipe_operator, caret_operator)
        + reserved_refs
        + bow_eow_tags
        + edit_tags
        + boundary_symbols
        + (word_edge,)
        + feature_brackets
    )


class StructId(NamedTuple):
    id: str
    kind: str

    def __str__(self):
        return f"{self.kind}:{self.id}"

    def __repr__(self):
        return str(self)


@dataclass
class Lexeme:
    root: str
    homophone_index: int
    lexical_features: FeatureSet
    principal_parts: dict[str, str]

    def _tagged_string(
        self,
        root: str,
        feature_set: FeatureSet,
    ) -> str:
        tagged_string = (
            ReservedSymbols.lexical_feature_start_tag
            + str(feature_set)
            + ReservedSymbols.lexical_feature_end_tag
            + ReservedSymbols.bow
            + root
            + ReservedSymbols.eow
        )
        return tagged_string

    @property
    def lexeme_string(self) -> str:
        lexical_feature_tags = self.lexical_features + {
            "homophone_index": self.homophone_index
        }
        return self._tagged_string(
            root=self.root,
            feature_set=lexical_feature_tags,
        )

    def principal_part_string(
        self,
        principal_part: str,
        fallback_to_root: bool = True,
    ) -> str:
        principal_part_str = self.principal_parts[principal_part]
        if not principal_part_str and fallback_to_root:
            principal_part_str = self.root
        elif not principal_part_str:
            raise build_diagnostic_error(
                message=f"Requested principal part {principal_part} for lexeme {self.root} when none is present and {fallback_to_root=}",
            )
        lexical_feature_tags = self.lexical_features + {
            "homophone_index": self.homophone_index
        }

        return self._tagged_string(
            feature_set=lexical_feature_tags,
            root=principal_part_str,
        )


@dataclass
class InflectedWord:
    forms: tuple[str, ...]
    inflectional_features: FeatureSet
    paradigm_id: str
    lexeme: Lexeme

    @property
    def tagged_root(self) -> str:
        tagged_root = self.lexeme.lexeme_string.replace(
            ReservedSymbols.bow,
            ReservedSymbols.inflectional_feature_start_tag
            + str(self.inflectional_features)
            + ReservedSymbols.inflectional_feature_end_tag,
        )
        return tagged_root


DependencyGraphType = dict[StructId, set[StructId]]
StructRegistryType = dict[str, dict[str, msgspec.Struct]]
SourcefileGraphType = dict[StructId, str]
MtimeGraphType = dict[StructId, float]


class FstContext(NamedTuple):
    token_map: dict[str, Token]
    phone_starts: set[str]
    sym_table: pynini.SymbolTable
    sigma: pynini.Fst
    special_fsas: dict[str, pynini.Fst]
    compiled_patterns: dict[str, pynini.Fst] | None = None
    compiled_rules: dict[str, pynini.Fst] | None = None
    compiled_markers: dict[str, pynini.Fst] | None = None


class Project(NamedTuple):
    sourcefile_graph: SourcefileGraphType
    dependency_graph: DependencyGraphType
    struct_registry: StructRegistryType
    mtime_graph: MtimeGraphType
    diagnostic_errors: tuple[Diagnostic, ...]
    fst_context: FstContext | None = None
    inflect_tries: dict[str, InflectTrie] | None = None
    lexical_tries: dict[str, LexicalTrie] | None = None
    global_marker_map: dict[str, tuple[CompiledMarker]] | None = None


class CompiledMarker(NamedTuple):
    """
    A struct containing the interpreted FST for a marker
    list alongside metadata indicating provenance and
    features exponed.
    """

    marker: Marker
    feature_set: FeatureSet
    fst_array: tuple[pynini.Fst, ...]
    sourcefile_kind: Literal[
        "FeatureMarkerFile",
        "MultiFeatureMarkerFile",
        "ParadigmFile",
    ]
    sourcefile_id: ObjectId


class FeatureSet(Mapping):
    def __init__(self, *feature_tuples, **feature_values: str):
        feature_tuples += tuple(feature_values.items())
        for feat_tuple in feature_tuples:
            if len(feat_tuple) != 2:
                raise ValueError(
                    f"Feature tuples must have two elements (feature name and value), got {len(feat_tuple)}"
                )
            if not type(feat_tuple[0]) is str:
                raise ValueError(
                    f"Feature name should be str but got type {type(feat_tuple[0])}"
                )
            if not isinstance(feat_tuple[1], (str, int)):
                raise ValueError(
                    f"Feature value should be str or int but got type {type(feat_tuple[1])}"
                )

        # sort by feature name
        _data = sorted(feature_tuples, key=lambda t: t[0])
        # cast any integer values to str
        _data = ((t[0], str(t[1])) for t in _data)
        # freeze as tuple for hashing purposes
        _data = tuple(_data)
        self._data = _data

    def __getitem__(self, key):
        return next(value for curr_key, value in self._data if key == curr_key)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __hash__(self):
        return hash(self._data)

    def __repr__(self):
        return f"<FeatureSet {stringify_features(self._data)}>"

    def __str__(self):
        return stringify_features(self._data)

    def to_dict(self):
        return {key: value for key, value in self._data}

    @classmethod
    def from_str(cls, feature_str: str):
        return cls(**serialize_feature_str(feature_str))

    def __add__(self, other):
        if isinstance(other, FeatureSet):
            other_data = other.to_dict()
        elif isinstance(other, tuple):
            if len(other) == 2 and type(other[0]) is str:
                other_data = {other[0]: other[1]}
            else:
                other_data = {key: value for key, value in other}
        elif isinstance(other, dict):
            other_data = other
        else:
            return NotImplemented
        new_data = self.to_dict()
        for key, value in other_data.items():
            if key in new_data:
                raise ValueError(f"Cannot overwrite {key} in FeatureSet {self}")
            new_data[key] = value

        return FeatureSet(**new_data)


class InflectTrie(NamedTuple):
    """
    A trie mapping values for the current features to subtrees
    denoting other features, with None marking leaf nodes. Each
    node also bears a list of CompiledMarkers indicating the
    relevant formatives.
    """

    feature_id: str
    sub_trees: dict[str, InflectTrie | None]
    marker_map: dict[str, tuple[CompiledMarker, ...]] | None = None


class LexicalTrie(NamedTuple):
    """
    A trie mapping values for the current features to subtrees
    denoting other features, with None marking leaf nodes. Each
    node also bears a list of CompiledMarkers indicating the
    relevant formatives, and a list of dicts indicating relevant
    lexemes that bear the given set of features.
    """

    feature_id: str
    sub_trees: dict[str, InflectTrie | None]
    lexeme_map: dict[str, tuple[dict, ...]]
    marker_map: dict[str, tuple[CompiledMarker, ...]] | None = None


"""
## Struct registry helpers
"""


def resolve_struct_name_from_instance(struct: msgspec.Struct) -> str:
    for union_struct, name in UNION_TO_NAME.items():
        if isinstance(struct, union_struct):
            return name
    if hasattr(type(struct), "__name__"):
        return type(struct).__name__

    raise ValueError(f"Unnamed struct types must be registered as a union type.")


def resolve_struct_name_from_type(struct_type: type[msgspec.Struct]) -> str:
    for union_struct, name in UNION_TO_NAME.items():
        if struct_type == union_struct or struct_type in union_struct.__args__:
            return name
    if hasattr(struct_type, "__name__"):
        return struct_type.__name__
    raise ValueError(f"Unnamed struct types must be registered as a union type.")


def get_struct_id(struct: msgspec.Struct, allow_anonymous: bool = False) -> StructId:
    if not allow_anonymous:
        struct_id = getattr(struct, "id")
    else:
        struct_id = getattr(struct, "id", "[ANONYMOUS]")
    return StructId(
        kind=resolve_struct_name_from_instance(struct),
        id=struct_id,
    )


def iter_registry(struct_registry: StructRegistryType) -> Iterable[StructId]:
    for struct_kind, kind_registry in struct_registry.items():
        for struct_id, struct in kind_registry.items():
            yield StructId(id=struct_id, kind=struct_kind), struct


def registry_ids(
    struct_registry: StructRegistryType, kind: str | None = None
) -> Iterable[StructId]:
    if kind:
        for struct_id in struct_registry.get(kind, {}).keys():
            yield StructId(id=struct_id, kind=kind)
    else:
        for struct_kind, kind_registry in struct_registry.items():
            for struct_id, struct in kind_registry.items():
                yield StructId(id=struct_id, kind=struct_kind)


def get_struct(
    struct_registry: StructRegistryType,
    id: str | None = None,
    kind: str | type(msgspec.Struct) | None = None,
    id_tuple: StructId = None,
) -> msgspec.Struct:
    if id_tuple is not None:
        return struct_registry[id_tuple.kind][id_tuple.id]
    if id is None or kind is None:
        raise ValueError("Must pass either id_tuple or id and kind kwargs")
    if type(kind) is not str:
        kind = resolve_struct_name_from_type(kind)
    return struct_registry[kind][id]


def set_struct(
    struct_id: StructId,
    struct: msgspec.Struct,
    struct_registry: StructRegistryType,
    allow_overwrite: bool = False,
):
    if (
        not allow_overwrite
        and struct_id.kind in struct_registry
        and struct_id.id in struct_registry[struct_id.kind]
    ):
        raise build_diagnostic_error(
            message=f"Duplicate struct {struct_id} found in registry",
            struct=str(struct_id),
        )
    struct_registry.setdefault(struct_id.kind, {})[struct_id.id] = struct
