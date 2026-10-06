from __future__ import annotations

from typing import Literal, NamedTuple

import msgspec
from loguru import logger

from src.diagnostics import DiagnosticError, Location, Stage, build_diagnostic_error
from src.models import (
    Feature,
    FeatureCombinationFile,
    FeatureMarkerFile,
    InflectionStage,
    MultiFeatureMarkerFile,
    ParadigmFile,
    PartOfSpeechFile,
    Rule,
    StructId,
    StructRegistryType,
    get_struct,
    get_struct_id,
    registry_ids,
    resolve_struct_name_from_instance,
    resolve_struct_name_from_type,
)

"""
# First-pass relations
Functions for validating struct relations applied immediately
after validating the dependency graph.
"""


SELF_RELATION_TYPE = "self"


class Reference(NamedTuple):
    """
    Indicates a struct field that references another
    struct, or an array of structs if `many=True`.
    """

    target: type[msgspec.Struct] | Literal[SELF_RELATION_TYPE]
    many: bool = False


StructFieldPair = tuple[type[msgspec.Struct], str]
ConstraintScopeType = str | StructFieldPair | list[str | StructFieldPair] | None


class Constraint(NamedTuple):
    """
    A constraint on the values a struct field may take,
    where the constrained set of allowed values is defined
    by an array of values defined in another struct.

    The `allowed` field indicates the type and field of the foreign
    struct that provides the set of valid values.

    The `scope` field describes how to retrieve the foreign struct.
    - If `scope` is a str, then the indicated field of the current
      struct bears the id of the foreign struct to validate against.
    - If `scope` is a tuple of struct type and str, the first element
      type of struct and the second indicates the field of that struct
      to pull the foreign id from. The validation function will then
      search the current structs parents for a struct of the expected
      type in order to retrieve the foreign id.
    - A list containing some combination of the two previous categories,
      indicating that at least one of the list must be satisfied.
    - If `scope` is `None`, then the list of allowed values is the
      union of all values across all structs of the indicated type,
      and so no particular foreign struct needs to be indexed.

    The `skip_if_no_scope` flag indicates whether an error will
    be thrown if the specified scope is not found. This is useful
    when a field may have special validation when child to some
    structs but not others, e.g. a reference to an inflectional
    feature in a Paradigm must belong to the corresponding
    PartOfSpeech's set of inflectional features, but inflectional
    features specified generally do not always have this constraint.
    """

    allowed: StructFieldPair
    scope: ConstraintScopeType
    skip_if_no_scope: bool = False


class FeatureMapping(NamedTuple):
    """
    Similar to a constraint except that it defines a
    valid set of keys and values, e.g. the possible
    set of feature vectors for a part of speech.

    `allowed_keys` defines how to retrieve the set of
    possible keys for the mapping, where each key is
    expected to be a struct id.
    - If `allowed_keys` is a Constraint, then the set
      of values returned by resolving the Constraint is
      the set of struct ids that represent valid keys.
    - If `allowed_keys` is a ConstraintScope, then the
      set of values contained by the scoped field is
      the set of struct ids that represent valid keys.

    `allowed_values` defines the type of substruct and field
    within the sub-struct that defines the set of values
    that struct licenses.

    `allow_wildcards` indicates whether the values
    "*" (any Feature) and "undefined" are allowed as
    values.
    """

    allowed_keys: Constraint | ConstraintScopeType
    allowed_values: str
    allow_wildcards: bool = False


RelationType = Constraint | Reference | FeatureMapping

_relations: dict[str, RelationType | tuple[RelationType, ...]] = {
    # Constraint specific to FeatureMarkerFiles, where features
    # are scoped to the whole file
    "marker_feature_value": Constraint(
        scope=(FeatureMarkerFile, "feature"),
        allowed=(Feature, "values"),
    ),
    # Generic feature_value fields expect a "feature" field
    # in the same struct
    "feature_value": Constraint(
        scope=["feature", (FeatureMarkerFile, "feature")],
        allowed=(Feature, "values"),
    ),
    # Inflectional features specified in a Paradigm must belong
    # to the corresponding set of inflectional features for the
    # specified part of speech
    "feature": (
        Constraint(
            scope=(ParadigmFile, "part_of_speech"),
            allowed=(PartOfSpeechFile, "inflectional_features"),
            skip_if_no_scope=True,
        ),
        # feature references in general must match an existing Feature struct
        Reference(
            target=Feature,
        ),
    ),
    # Lexical features validate against the respective
    # part of speech in their parent struct
    "lexical_feature": Constraint(
        scope=(ParadigmFile, "part_of_speech"),
        allowed=(PartOfSpeechFile, "lexical_features"),
    ),
    # lexical_feature_value fields expect a "lexical_feature" field
    # in the same struct
    "lexical_feature_value": Constraint(
        scope="lexical_feature",
        allowed=(Feature, "values"),
    ),
    # principal part markers must validate against the set of principal
    # parts from all parts of speech (FeatureMarkerFile configs do not
    # know which parts of speech they will associate with)
    "principal_part_value": Constraint(
        scope=None,
        allowed=(PartOfSpeechFile, "principal_parts"),
    ),
    # Feature mapping keys
    "feature_values": FeatureMapping(
        allowed_keys=(MultiFeatureMarkerFile, "features"),
        allowed_values=(Feature, "values"),
    ),
    "lexical_feature_values": FeatureMapping(
        allowed_keys=Constraint(
            scope=(ParadigmFile, "part_of_speech"),
            allowed=(PartOfSpeechFile, "lexical_features"),
        ),
        allowed_values=(Feature, "values"),
    ),
    "feature_vector": FeatureMapping(
        allowed_keys=Constraint(
            scope=(FeatureCombinationFile, "part_of_speech"),
            allowed=(PartOfSpeechFile, "inflectional_features"),
        ),
        allowed_values=(Feature, "values"),
        allow_wildcards=True,
    ),
    # Fields referencing other structs
    "rule": Reference(
        target=Rule,
    ),
    "rule_sequence": Reference(
        target=Rule,
        many=True,
    ),
    "feature_marker": Reference(
        target=FeatureMarkerFile,
    ),
    "stage": Reference(
        target=InflectionStage,
    ),
    "inherits": Reference(
        target=SELF_RELATION_TYPE,
    ),
}

_validated_fields = set(_relations.keys())


def resolve_reference(
    struct: msgspec.Struct,
    field: str,
    struct_registry: StructRegistryType,
    reference: Reference,
) -> list[StructId]:
    struct_id = get_struct_id(struct, allow_anonymous=True)
    if reference.target == SELF_RELATION_TYPE:
        target_struct_name = resolve_struct_name_from_type(struct)
    else:
        target_struct_name = resolve_struct_name_from_type(reference.target)
    field_value = getattr(struct, field)
    if reference.many:
        for id_str in field_value:
            relation_list = []
            target_id = StructId(kind=target_struct_name, id=id_str)
            try:
                get_struct(struct_registry=struct_registry, id_tuple=target_id)
            except KeyError:
                raise build_diagnostic_error(
                    field=field,
                    struct=struct_id,
                    message=f"Reference to non-existant struct {target_id}",
                    stage="dependencies",
                )

            relation_list.append(target_id)
            logger.debug(
                f"Loaded reference to {relation_list} from field {field} in struct {struct}"
            )

            return relation_list
    else:
        target_id = StructId(kind=target_struct_name, id=field_value)
        try:
            get_struct(struct_registry=struct_registry, id_tuple=target_id)
        except KeyError:
            raise build_diagnostic_error(
                field=field,
                struct=get_struct_id(struct, allow_anonymous=True),
                message=f"Reference to non-existant struct {target_id}",
                stage="dependencies",
            )

        return [target_id]


def resolve_constraint_scope(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    scope: str | StructFieldPair,
) -> str | None:
    """
    Resolve foreign id from a constraint scope
    either from the current struct or one of its
    parents.
    """
    foreign_id = None
    if type(scope) is str:
        foreign_id = getattr(struct, scope, None)
        return foreign_id
    elif type(scope) is tuple:
        parent_type, parent_field = scope
        for parent in upstream:
            if isinstance(parent, parent_type):
                foreign_id = getattr(parent, parent_field)
                return foreign_id


def resolve_constraint(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    struct_registry: StructRegistryType,
    constraint: Constraint,
) -> tuple[list[StructId], list] | None:
    """
    Resolve the struct(s) referenced by a Constraint as well
    as the set of allowed values they define. Returns None if
    constraint resolution fails.
    """
    if type(constraint.scope) is list:
        for scope in constraint.scope:
            foreign_id = resolve_constraint_scope(
                struct,
                upstream,
                scope,
            )
            if foreign_id is not None:
                break
    else:
        foreign_id = resolve_constraint_scope(
            struct,
            upstream,
            constraint.scope,
        )
    if foreign_id is None:
        if constraint.skip_if_no_scope:
            return
        elif constraint.scope is None:
            pass
        else:
            raise ValueError(
                f"Could not satisfy scope {constraint.scope} for struct {struct} with upstream {upstream}"
            )
    foreign_type, foreign_field = constraint.allowed
    foreign_type_name = resolve_struct_name_from_type(foreign_type)
    if foreign_id is None:
        foreign_struct_id_list = registry_ids(struct_registry, kind=foreign_type_name)
        allowed_values = []
        for foreign_struct_id in foreign_struct_id_list:
            foreign_struct = get_struct(
                struct_registry=struct_registry,
                id_tuple=foreign_struct_id,
            )
            foreign_value = getattr(foreign_struct, foreign_field)
            if type(foreign_value) is tuple:
                allowed_values.extend(foreign_value)
            else:
                allowed_values.append(foreign_value)

        return foreign_struct_id_list, allowed_values
    foreign_key = StructId(kind=foreign_type_name, id=foreign_id)
    foreign_struct = get_struct(
        struct_registry=struct_registry,
        id_tuple=foreign_key,
    )
    allowed_values = getattr(foreign_struct, foreign_field)
    allowed_values = list(allowed_values)
    return [foreign_key], allowed_values


def resolve_mapping(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    struct_registry: StructRegistryType,
    feature_mapping: FeatureMapping,
) -> tuple[list[StructId], dict[str, list[str]]]:
    allowed_mappings: dict[str, list[str]] = {}
    if type(feature_mapping.allowed_keys) is Constraint:
        referenced_ids, substruct_ids = resolve_constraint(
            struct=struct,
            upstream=upstream,
            struct_registry=struct_registry,
            constraint=feature_mapping.allowed_keys,
        )
    else:
        referenced_ids = []
        substruct_ids = resolve_constraint_scope(
            struct=struct,
            upstream=upstream,
            scope=feature_mapping.allowed_keys,
        )
    substruct_kind, substruct_field = feature_mapping.allowed_values
    allowed_structs = [
        get_struct(
            kind=substruct_kind,
            id=substruct_id,
            struct_registry=struct_registry,
        )
        for substruct_id in substruct_ids
    ]
    for curr_struct in allowed_structs:
        curr_value = getattr(curr_struct, substruct_field)
        if not isinstance(curr_value, tuple):
            raise ValueError(
                f"Expected struct field {substruct_field} to contain tuple but got {type(curr_value)} "
                + f"with value {curr_value} in struct {get_struct_id(struct, allow_anonymous=True)}."
            )
        allowed_mappings[curr_struct.id] = curr_value
        if feature_mapping.allow_wildcards:
            allowed_mappings[curr_struct.id] += ("*", "undefined")
        referenced_ids.append(get_struct_id(curr_struct))

    return referenced_ids, allowed_mappings


def validate_relation(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    field: str,
    struct_registry: StructRegistryType,
    relation: RelationType,
) -> list[StructId]:
    """
    Validates a relation (i.e. any referenced structs exist,
    all constraint values are in the valid set, any key->value
    mappings are in the valid sets) and returns list of ids touched
    by the relation.
    """
    struct_id = get_struct_id(struct, allow_anonymous=True)
    if type(relation) is Reference:
        foreign_id = resolve_reference(
            struct,
            field,
            struct_registry,
            relation,
        )
        logger.debug(f"Struct {struct_id} references {foreign_id} at field {field}")
        return foreign_id
    elif type(relation) is Constraint:
        resolved = resolve_constraint(
            struct,
            upstream,
            struct_registry,
            relation,
        )
        if resolved is None:
            return []
        foreign_id_list, allowed_values = resolved
        struct_field_value = getattr(struct, field)
        if not struct_field_value in allowed_values:
            message = (
                f"Struct {struct_id} with value {struct_field_value} at field {field} not in allowed "
                + f"values {allowed_values}"
            )
            raise build_diagnostic_error(
                message=message,
                struct=struct_id,
                field=field,
                stage="dependencies",
            )
        logger.debug(
            f"Field value {struct_field_value} at field {field} in struct {struct_id} in allowed values "
            + f"{allowed_values} from target {foreign_id_list}"
        )
        return foreign_id_list
    else:  # type(relation) is FeatureMapping
        foreign_id_list, allowed_mappings = resolve_mapping(
            struct=struct,
            upstream=upstream,
            struct_registry=struct_registry,
            feature_mapping=relation,
        )
        referenced_location = Location(
            struct=foreign_id_list[0],
            field=relation.allowed_keys[1],
        )
        field_mapping: dict[str, str] = getattr(struct, field)
        if not isinstance(field_mapping, dict):
            raise ValueError(
                f"Expected field {field} in struct {struct_id} to have value of type "
                + f"dict but got {type(field_mapping)} with value {field_mapping}"
            )
        for key, value in field_mapping.items():
            if not key in allowed_mappings:
                raise build_diagnostic_error(
                    message=f"Key {key} at field {field} in struct {struct_id} not in allowed keys {allowed_mappings.keys()}",
                    struct=struct_id,
                    field=field,
                    related=(referenced_location,),
                )
            if not value in allowed_mappings[key]:
                raise build_diagnostic_error(
                    message=f"Value {value} at key {key} at field {field} in struct {struct_id} not in allowed "
                    + f"values {allowed_mappings[key]}",
                    struct=struct_id,
                    field=field,
                    related=(referenced_location,),
                )
        logger.debug(
            f"Validated mapping at struct {struct_id} against structs {foreign_id_list}"
        )
        return foreign_id_list


def validate_struct_relations(
    struct: msgspec.Struct,
    struct_registry: StructRegistryType,
    upstream: list[msgspec.Struct],
) -> list[StructId]:
    fields_to_validate = _validated_fields & set(struct.__struct_fields__)
    relations = []
    target_ids = []
    for field in fields_to_validate:
        field_value = getattr(struct, field)
        if field_value is None:
            continue
        field_relation = _relations[field]
        if type(field_relation) is tuple:
            for subrelation in field_relation:
                relations.append((field, subrelation))
        else:
            relations.append((field, field_relation))
    if relations:
        for field, relation in relations:
            current_targets = validate_relation(
                struct,
                upstream,
                field,
                struct_registry,
                relation,
            )
            target_ids.extend(current_targets)
    return target_ids
