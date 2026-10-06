"""
# models.py
Structs for grammar data objects. Each YAML file type has a
struct defining the schema for the entire file, which in turn
is comprised of structs for data objects defined by the file
(e.g. the PatternFile struct has Pattern as a sub-struct).
"""

from __future__ import annotations

import re
from typing import Annotated, Iterable, Literal, NamedTuple

import msgspec

from src.diagnostics import Diagnostic, build_diagnostic_error

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
- FeatureDefinitions
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
    stage: str | None = None


class RuleMarker(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="rule"
):
    """
    A marker that applies a contextual rule.
    """

    rule: str
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
    data: tuple[MultiFeatureMarker, ...]
    inherits: str | None = None


"""
## Morphotactics modules

Contains the following submodules:
- FeatureCombinations
- Paradigm
"""


class FeatureCombination(msgspec.Struct, kw_only=True, frozen=True):
    """
    Object mapping feature values to an array of strings indicating "
    possible values that feature may take on in the given combination, or a wildcard
    "*" to indicate the feature may take on any value, or "undefined" to indicate
    the feature must be undefined in this combination.
    """

    feature_vector: dict[str, tuple[str] | Literal["*", "undefined"]]
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


class ParadigmFilter(msgspec.Struct, kw_only=True, frozen=True):
    """
    A filter the selects lexical roots based on whether they possess
    certain lexical features or whether they match a given regex pattern.
    """

    lexical_feature_values: dict[str, str] | None = None
    pattern: PatternStr | None = None


class FeatureMarkerReference(
    msgspec.Struct,
    kw_only=True,
    frozen=True,
    tag_field="kind",
    tag="feature_marker_file",
):
    """A reference to a FeatureMarker file that expones the given feature"""

    feature: str
    feature_marker: str


class FixedFeatureValue(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="fixed_value"
):
    """A single feature value the current feature is fixed to for this paradigm"""

    feature: str
    feature_value: str


class MultiFeatureOnly(
    msgspec.Struct, kw_only=True, frozen=True, tag_field="kind", tag="multi_only"
):
    """Indicates the given feature is only exponed by MultiFeatureMarker files"""

    feature: str


InflectionalFeatureSpecification = (
    FeatureMarkerReference | FixedFeatureValue | MultiFeatureOnly
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
    feature_markers: tuple[InflectionalFeatureSpecification, ...]
    filter: ParadigmFilter | None = None
    stage_order: tuple[str, ...] | None = None
    global_markers: tuple[Marker, ...] | None = None
    feature_value_combinations: str | None = None
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


class StructId(NamedTuple):
    id: str
    kind: str

    def __str__(self):
        return f"{self.kind}:{self.id}"

    def __repr__(self):
        return str(self)


DependencyGraphType = dict[StructId, set[StructId]]
StructRegistryType = dict[str, dict[str, msgspec.Struct]]
SourcefileGraphType = dict[StructId, str]
MtimeGraphType = dict[StructId, float]
StructRegistryType = dict[StructId, msgspec.Struct]


class Project(NamedTuple):
    sourcefile_graph: SourcefileGraphType
    dependency_graph: DependencyGraphType
    struct_registry: StructRegistryType
    mtime_graph: MtimeGraphType
    diagnostic_errors: tuple[Diagnostic, ...]


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
