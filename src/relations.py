from __future__ import annotations

from typing import Literal, NamedTuple
from venv import logger

import msgspec

from src.models import (
    Feature,
    FeatureMarkerFile,
    ParadigmFile,
    PartOfSpeechFile,
    Rule,
    StructIdType,
    StructRegistryType,
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


class Constraint(NamedTuple):
    # TODO: may wish to specify for some constraints that at least one of a set is covered
    # either by specifying multiple scopes w/in single constraint
    # or defining some logic over multiple constraints
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
    scope: str | StructFieldPair | None
    skip_if_no_scope: bool = False


class Mapping(NamedTuple):
    """
    Similar to a constraint except that it defines a
    valid set of keys and values, e.g. the possible
    set of feature vectors for a part of speech.
    """

    key: Constraint | Reference
    value: Constraint


RelationType = Constraint | Reference | Mapping

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
        scope="feature",
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
    "inherits": Reference(
        target=SELF_RELATION_TYPE,
    ),
}

_validated_fields = set(_relations.keys())


def resolve_reference(
    struct: msgspec.Struct,
    field: str,
    registry: StructRegistryType,
    reference: Reference,
) -> StructIdType | list[StructIdType] | None:
    target_struct_name = resolve_struct_name_from_type(reference.target)
    field_value = getattr(struct, field)
    if reference.many:
        for id_str in field_value:
            relation_list = []
            try:
                target_id = (id_str, target_struct_name)
                target = registry[target_id]
                relation_list.append(target_id)
            except Exception as e:
                logger.exception(e)
            logger.debug(
                f"Loaded reference to {relation_list} from field {field} in struct {struct}"
            )
            return relation_list or None
    else:
        target_id = (field_value, target_struct_name)
        registry[target_id]
        try:
            target_id = (field_value, target_struct_name)
            target = registry[target_id]
            logger.debug(
                f"Loaded reference to {reference} from field {field} in struct {struct}"
            )
            return target_id
        except Exception as e:
            logger.exception(e)


def resolve_constraint(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    registry: StructRegistryType,
    constraint: Constraint,
) -> tuple[StructIdType | list[StructIdType], list] | None:
    foreign_id = None
    if type(constraint.scope) is str:
        foreign_id = getattr(struct, constraint.scope, None)
    elif type(constraint.scope) is tuple:
        parent_type, parent_field = constraint.allowed
        for parent in upstream:
            current_parent_type = resolve_struct_name_from_instance(parent)
            if current_parent_type == parent_type:
                foreign_id = getattr(parent, parent_field)

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
    if foreign_id is None:
        foreign_struct_list = [
            struct_id for struct_id in registry.keys() if struct_id[1] == foreign_type
        ]
        allowed_values = []
        for foreign_struct_id in foreign_struct_list:
            foreign_struct = registry[foreign_struct_id]
            foreign_value = getattr(foreign_struct, foreign_field)
            if type(foreign_value) is tuple:
                allowed_values.extend(foreign_value)
            else:
                allowed_values.append(foreign_value)

        return foreign_struct_list, allowed_values

    foreign_struct = registry[(foreign_id, foreign_type)]
    allowed_values = getattr(foreign_struct, foreign_field)
    allowed_values = list(allowed_values)
    return foreign_id, allowed_values


def validate_relation(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    field: str,
    registry: StructRegistryType,
    relation: RelationType,
) -> StructIdType | list[StructIdType] | None:
    if type(relation) is Reference:
        return resolve_reference(
            struct,
            field,
            registry,
            relation,
        )
    elif type(relation) is Constraint:
        resolved = resolve_constraint(
            struct,
            upstream,
            registry,
            relation,
        )
        if resolved is None:
            return
        foreign_id, allowed_values = resolved
        struct_field_value = getattr(struct, field)
        if not struct_field_value in allowed_values:
            raise ValueError(
                f"Struct with value {struct_field_value} at field {field} not in allowed values {allowed_values}"
            )
        return foreign_id


def validate_struct_relations(
    struct: msgspec.Struct,
    registry: StructRegistryType,
    upstream: list[msgspec.Struct],
):
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
            target = validate_relation(
                struct,
                upstream,
                field,
                registry,
                relation,
            )
            if type(target) is list:
                target_ids.extend(target)
            elif target is None:
                pass
            else:
                target_ids.append(target)
    return target_ids
