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
)
from src.relations import validate_all_struct_relations

"""
## Config serving functions
"""


def get_struct_id(struct: msgspec.Struct) -> StructIdType:
    return (struct.id, type(struct).__name__)


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
        current_dependency_tree, current_registry = walk_config(
            struct,
            set(),
            {},
        )
        struct_registry |= current_registry
        for child_struct_id, upstream in current_dependency_tree.items():
            if child_struct_id == struct_id:
                continue
            if child_struct_id in sourcefile_graph:
                existing_source = sourcefile_graph[child_struct_id]
                logger.error(
                    f"Duplicate struct with id {child_struct_id} "
                    f"found in file {source_path} and {existing_source}"
                )
            sourcefile_graph[child_struct_id] = source_path
            mtime_graph[child_struct_id] = mtime
            dependency_graph[child_struct_id] = upstream

    return (
        struct_registry,
        sourcefile_graph,
        mtime_graph,
        dependency_graph,
    )


def walk_config(
    struct: msgspec.Struct,
    upstream: set[StructIdType],
    dependency_graph: DependencyGraphType,
) -> tuple[StructRegistryType, DependencyGraphType]:
    """
    Determines all structs upstream of the current
    additional to those passed in `upstream` and
    populates `dependency_graph` accordingly, then
    recurses into any downstream structs.
    """
    struct_id = get_struct_id(struct)
    dependency_graph[struct_id] = upstream.copy()
    upstream.add(struct_id)

    downstream = resolve_downstream(struct)
    registry: StructRegistryType = {}
    for child_struct in downstream:
        child_struct_id = get_struct_id(child_struct)
        registry[child_struct_id] = child_struct
        dependency_graph, child_registry = walk_config(
            child_struct,
            upstream,
            dependency_graph,
        )
        registry |= child_registry
    return dependency_graph, registry


def resolve_downstream(struct: msgspec.Struct) -> list[msgspec.Struct]:
    downstream: list[msgspec.Struct] = []
    for field_name in struct.__struct_fields__:
        field_value = getattr(struct, field_name)
        if isinstance(field_value, msgspec.Struct) and hasattr(field_value, "id"):
            downstream.append(field_value)
        elif isinstance(field_value, tuple):
            for subvalue in field_value:
                if isinstance(subvalue, msgspec.Struct) and hasattr(subvalue, "id"):
                    downstream.append(subvalue)
        elif isinstance(field_value, dict):
            for subvalue in field_value.values():
                if isinstance(subvalue, msgspec.Struct) and hasattr(field_value, "id"):
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

    validate_all_struct_relations(struct_registry)
    breakpoint()
