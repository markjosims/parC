"""
Functions for fetching config YAML data.
Intuitively, this model handles serving any YAML data
that requires no "interpretation" of grammar (e.g.
compilation of regex strings or rule definitions to FSAs,
dependency and inheritance relationships, or filtering of
lexemes by lexical features).

Includes functions for loading and validating entire YAML files
and for loading specific objects from YAML files, viz:
- rules (rules/*.yaml)
- patterns (patterns/*.yaml)
- inventory items (inventory/*.yaml)
- markers (feature_markers/*.yaml, multifeature_feature_markers/*.yaml)
- inflection stages (feature_markers/*.yaml, multifeature_feature_markers/*.yaml)
- features (feature_definitions/*.yaml)
"""

import msgspec
from graphlib import TopologicalSorter
from loguru import logger

from src.constants import get_yaml_dir
from src.models import (
    CONFIG_KIND_TO_PARDIR,
    CONFIG_KIND_TO_STRUCT,
    CONFIG_KINDS_ORDERED,
    DependencyGraphType,
    MtimeGraphType,
    SourcefileGraphType,
    StructErrorGraphType,
    StructIdType,
    StructRegistryType,
    resolve_struct_name_from_instance,
)
from src.relations import validate_struct_relations

"""
## Config serving functions
"""


def get_struct_id(struct: msgspec.Struct) -> StructIdType:
    return (struct.id, resolve_struct_name_from_instance(struct))


def read_configs_flat() -> tuple[
    StructRegistryType,
    SourcefileGraphType,
    MtimeGraphType,
    StructErrorGraphType,
]:
    struct_registry: StructRegistryType = {}
    sourcefile_graph: SourcefileGraphType = {}
    mtime_graph: MtimeGraphType = {}
    structerror_graph: StructErrorGraphType = {}

    for config_kind in CONFIG_KINDS_ORDERED:
        config_dir = kind_dir(config_kind)
        struct_type = CONFIG_KIND_TO_STRUCT[config_kind]
        for file in config_dir.iterdir():
            if file.suffix not in (".yaml", ".yml"):
                continue
            try:
                struct = msgspec.yaml.decode(file.read_bytes(), type=struct_type)
                struct_id = get_struct_id(struct)
                if struct_id in struct_registry:
                    other_file = sourcefile_graph[struct_id]
                    error_message = (
                        f"Duplicate struct id {struct_id} found in {file} and {other_file} "
                        + f"only the struct from {other_file} will be saved"
                    )

                    logger.error(error_message)
                    raise ValueError(error_message)
                struct_registry[struct_id] = struct
                mtime_graph[struct_id] = file.stat().st_mtime
                sourcefile_graph[struct_id] = str(file)
            except Exception as e:
                logger.error(f"Error decoding config at {file}")
                logger.exception(e)
                structerror_graph[file] = str(e)

    return struct_registry, sourcefile_graph, mtime_graph, structerror_graph


def walk_all_configs(
    struct_registry: StructRegistryType,
    sourcefile_graph: SourcefileGraphType,
    mtime_graph: MtimeGraphType,
) -> tuple[
    StructRegistryType,
    SourcefileGraphType,
    MtimeGraphType,
    DependencyGraphType,
]:
    parent_structs = list(struct_registry.items())
    dependency_graph: DependencyGraphType = {}
    for struct_id, struct in parent_structs:
        mtime = mtime_graph[struct_id]
        source_path = sourcefile_graph[struct_id]
        dependency_graph, struct_registry, children = walk_config(
            struct,
            upstream=[],
            struct_registry=struct_registry,
            dependency_graph=dependency_graph,
        )
        child_struct_ids = try_get_struct_ids(children)
        for child_struct_id in child_struct_ids:
            if child_struct_id in sourcefile_graph:
                existing_source = sourcefile_graph[child_struct_id]
                logger.error(
                    f"Duplicate struct with id {child_struct_id} "
                    f"found in file {source_path} and {existing_source}"
                )
            sourcefile_graph[child_struct_id] = source_path
            mtime_graph[child_struct_id] = mtime

    return (
        struct_registry,
        sourcefile_graph,
        mtime_graph,
        dependency_graph,
    )


def try_register_struct(
    struct: msgspec.Struct, struct_registry: StructRegistryType
) -> StructRegistryType:
    if not hasattr(struct, "id"):
        return struct_registry
    struct_id = get_struct_id(struct)
    if struct_id in struct_registry:
        logger.error(f"Duplicate struct with id {struct_id}")
        return struct_registry
    struct_registry[struct_id] = struct
    return struct_registry


def try_set_dependencies(
    struct: msgspec.Struct,
    upstream: list[msgspec.Struct],
    struct_registry: StructRegistryType,
    dependency_graph: DependencyGraphType,
) -> DependencyGraphType:
    """
    Validate all relations for the current struct and add
    referenced structs to the current's dependency graph.
    If the current struct is anonymous, add its dependencies
    to the nearest upstream named struct.
    """
    referenced = validate_struct_relations(
        struct=struct,
        upstream=upstream,
        registry=struct_registry,
    )
    if hasattr(struct, "id"):
        struct_id = get_struct_id(struct)
        if struct_id in dependency_graph:
            logger.error(f"Struct with id {get_struct_id(struct)} already referenced")
            return dependency_graph
        upstream_ids = try_get_struct_ids(upstream) + referenced
    else:
        upstream_ids = try_get_struct_ids(upstream) + referenced
        struct_id = upstream_ids.pop(0)

    existing_upstream = dependency_graph.get(struct_id, set())
    dependency_graph[struct_id] = existing_upstream | set(upstream_ids)
    return dependency_graph


def try_get_struct_ids(struct_array: list[msgspec.Struct]) -> list[StructIdType]:
    id_list = []
    for struct in struct_array:
        if hasattr(struct, "id"):
            id_list.append(get_struct_id(struct))
    return id_list


def walk_config(
    struct: msgspec.Struct,
    upstream: list[StructIdType],
    struct_registry: StructRegistryType,
    dependency_graph: DependencyGraphType,
) -> tuple[StructRegistryType, DependencyGraphType]:
    """
    Recursively add downstream structs to `dependency_graph`
    for current struct and
    """
    dependency_graph = try_set_dependencies(
        struct,
        upstream,
        struct_registry,
        dependency_graph,
    )
    upstream.append(struct)
    children: list[msgspec.Struct] = []

    downstream = resolve_downstream(struct)
    for child_struct in downstream:
        children.append(child_struct)
        struct_registry = try_register_struct(child_struct, struct_registry)
        dependency_graph, struct_registry, subchildren = walk_config(
            child_struct,
            upstream.copy(),
            struct_registry,
            dependency_graph,
        )
        children.extend(subchildren)
    return dependency_graph, struct_registry, children


def resolve_downstream(struct: msgspec.Struct) -> list[msgspec.Struct]:
    downstream: list[tuple[msgspec.Struct, str]] = []

    for field_name in struct.__struct_fields__:
        field_value = getattr(struct, field_name)
        if isinstance(field_value, msgspec.Struct):
            downstream.append(field_value)
        elif isinstance(field_value, tuple):
            for subvalue in field_value:
                if isinstance(subvalue, msgspec.Struct):
                    downstream.append(subvalue)
        elif isinstance(field_value, dict):
            for subvalue in field_value.values():
                if isinstance(subvalue, msgspec.Struct):
                    downstream.append(field_value)
    return downstream


def kind_dir(kind: str) -> str:
    return get_yaml_dir() / CONFIG_KIND_TO_PARDIR[kind] / kind


if __name__ == "__main__":
    struct_registry, sourcefile_graph, mtime_graph, structerror_graph = (
        read_configs_flat()
    )
    struct_registry, sourcefile_graph, mtime_graph, dependency_graph = walk_all_configs(
        struct_registry,
        sourcefile_graph,
        mtime_graph,
    )
    for key, value in struct_registry.items():
        print("Loaded struct:", key)
    for key, value in structerror_graph.items():
        print("Error at struct", key)
        print(value)

    for key, value in dependency_graph.items():
        if not value:
            print(f"{key} has no dependencies")
        else:
            print(key)
            for dependency in value:
                print(f"\tdepends on {dependency}")

    breakpoint()
