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

from copy import deepcopy
from typing import Literal

import msgspec
from frozendict import frozendict
from graphlib import TopologicalSorter
from loguru import logger

from src.constants import get_yaml_dir
from src.diagnostics import (
    Diagnostic,
    DiagnosticError,
    Location,
    build_diagnostic_error,
)
from src.models import (
    CONFIG_KIND_TO_PARDIR,
    CONFIG_KIND_TO_STRUCT,
    CONFIG_KINDS_ORDERED,
    DependencyGraphType,
    MtimeGraphType,
    ParadigmFile,
    ParadigmFilter,
    Project,
    SourcefileGraphType,
    StructId,
    StructRegistryType,
    get_struct_id,
    iter_registry,
    registry_ids,
    set_struct,
)
from src.yaml.relations import validate_struct_relations

"""
## Config serving functions
"""


def read_configs_flat() -> tuple[
    StructRegistryType,
    SourcefileGraphType,
    MtimeGraphType,
    list[Diagnostic],
]:
    struct_registry: StructRegistryType = {}
    sourcefile_graph: SourcefileGraphType = {}
    mtime_graph: MtimeGraphType = {}
    diagnostic_errors: list[Diagnostic] = []

    for config_kind in CONFIG_KINDS_ORDERED:
        config_dir = kind_dir(config_kind)
        struct_type = CONFIG_KIND_TO_STRUCT[config_kind]
        for file in config_dir.iterdir():
            if file.suffix not in (".yaml", ".yml"):
                continue
            try:
                struct = msgspec.yaml.decode(file.read_bytes(), type=struct_type)
                struct_id = get_struct_id(struct)
                if struct_id in list(registry_ids(struct_registry)):
                    existing_file = sourcefile_graph[struct_id]
                    existing_location = Location(file=existing_file, struct=struct_id)
                    raise build_diagnostic_error(
                        message=f"Duplicate struct id {struct_id} found in {file} and {existing_file} "
                        + f"only the struct from {existing_file} will be saved",
                        file=file,
                        struct=struct_id,
                        related=(existing_location,),
                    )

                set_struct(struct_id, struct, struct_registry)
                mtime_graph[struct_id] = file.stat().st_mtime
                sourcefile_graph[struct_id] = str(file)
            except DiagnosticError as e:
                new_error = build_diagnostic_error(
                    file=sourcefile_graph[struct_id],
                    existing=e.diagnostic,
                    message=e.diagnostic.message + f" at file {file}",
                )
                logger.bind(diagnostic=new_error.diagnostic).exception(new_error)
                diagnostic_errors.append(new_error.diagnostic)

    return struct_registry, sourcefile_graph, mtime_graph, diagnostic_errors


def walk_all_configs(
    struct_registry: StructRegistryType,
    sourcefile_graph: SourcefileGraphType,
    mtime_graph: MtimeGraphType,
    diagnostic_errors: list[Diagnostic],
) -> tuple[
    StructRegistryType,
    SourcefileGraphType,
    MtimeGraphType,
    DependencyGraphType,
]:
    parent_ids_and_structs = list(iter_registry(struct_registry))
    dependency_graph: DependencyGraphType = {}
    for struct_id, struct in parent_ids_and_structs:
        try:
            mtime = mtime_graph[struct_id]
            source_path = sourcefile_graph[struct_id]
            dependency_graph, struct_registry, children = walk_config(
                struct,
                upstream=[],
                struct_registry=deepcopy(struct_registry),
                dependency_graph=deepcopy(dependency_graph),
                stage="register_structs",
            )
            child_struct_ids = try_get_struct_ids(children)
            for child_struct_id in child_struct_ids:
                if child_struct_id in sourcefile_graph:
                    existing_source = sourcefile_graph[child_struct_id]
                    existing_location = Location(
                        file=existing_source, struct=child_struct_id
                    )
                    raise build_diagnostic_error(
                        message=f"Duplicate struct with id {child_struct_id} "
                        f"found in file {source_path} and {existing_source}",
                        file=source_path,
                        struct=child_struct_id,
                        related=(existing_location,),
                    )
                sourcefile_graph[child_struct_id] = source_path
                mtime_graph[child_struct_id] = mtime
        except DiagnosticError as e:
            logger.bind(diagnostic=e.diagnostic).exception(e)
            diagnostic_errors.append(e.diagnostic)

    for struct_id, struct in iter_registry(struct_registry):
        try:
            dependency_graph, struct_registry, children = walk_config(
                struct,
                upstream=[],
                struct_registry=deepcopy(struct_registry),
                dependency_graph=deepcopy(dependency_graph),
                stage="validate_relations",
            )
        except DiagnosticError as e:
            file = sourcefile_graph[struct_id]
            new_error = build_diagnostic_error(
                file=file,
                existing=e.diagnostic,
                message=e.diagnostic.message + f" at file {file}",
            )
            logger.bind(diagnostic=new_error.diagnostic).exception(new_error)
            diagnostic_errors.append(new_error.diagnostic)

    return (
        struct_registry,
        sourcefile_graph,
        mtime_graph,
        dependency_graph,
        diagnostic_errors,
    )


def try_register_struct(
    struct: msgspec.Struct, struct_registry: StructRegistryType
) -> StructRegistryType:
    if not hasattr(struct, "id"):
        return struct_registry
    struct_id = get_struct_id(struct)
    set_struct(struct_id, struct, struct_registry)
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
        struct_registry=struct_registry,
    )
    if hasattr(struct, "id"):
        # named structs depend on all parent and referenced structs
        struct_id = get_struct_id(struct)
        upstream_ids = try_get_struct_ids(upstream) + referenced
    else:
        # anonymous structs add any referenced dependencies to the
        # nearest upstream struct
        upstream_ids = referenced
        struct_id = try_get_struct_ids(upstream)[-1]

    existing_upstream = dependency_graph.get(struct_id, set())
    dependency_graph[struct_id] = existing_upstream | set(upstream_ids)
    return dependency_graph


def try_get_struct_ids(struct_array: list[msgspec.Struct]) -> list[StructId]:
    id_list = []
    for struct in struct_array:
        if hasattr(struct, "id"):
            id_list.append(get_struct_id(struct))
    return id_list


def walk_config(
    struct: msgspec.Struct,
    upstream: list[StructId],
    struct_registry: StructRegistryType,
    dependency_graph: DependencyGraphType,
    stage: Literal["register_structs", "validate_relations"],
) -> tuple[StructRegistryType, DependencyGraphType]:
    """
    Recursively add downstream structs to `dependency_graph`
    for current struct and
    """
    if stage == "validate_relations":
        dependency_graph = try_set_dependencies(
            struct=struct,
            upstream=upstream,
            struct_registry=struct_registry,
            dependency_graph=dependency_graph,
        )
    upstream.append(struct)
    downstream = resolve_downstream(struct)
    # if type(struct) is ParadigmFilter and stage == "validate_relations":
    # breakpoint()
    children: list[msgspec.Struct] = []
    for child_struct in downstream:
        children.append(child_struct)
        if stage == "register_structs":
            struct_registry = try_register_struct(child_struct, struct_registry)
        dependency_graph, struct_registry, subchildren = walk_config(
            child_struct,
            upstream.copy(),
            struct_registry,
            dependency_graph,
            stage=stage,
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


"""
## Main lifecycle entrypoints
"""


def _nested_freeze(obj: object) -> frozendict | object:
    if type(obj) is list:
        return tuple(_nested_freeze(element) for element in obj)
    elif type(obj) is not dict:
        return obj
    new_dict = {}
    for key, value in obj.items():
        new_dict[key] = _nested_freeze(value)
    return frozendict(new_dict)


def load_project():
    """
    Reads and walks all config files then checks for cycles.
    """
    struct_registry, sourcefile_graph, mtime_graph, diagnostic_errors = (
        read_configs_flat()
    )
    (
        struct_registry,
        sourcefile_graph,
        mtime_graph,
        dependency_graph,
        diagnostic_errors,
    ) = walk_all_configs(
        struct_registry,
        sourcefile_graph,
        mtime_graph,
        diagnostic_errors,
    )
    topo_sort = TopologicalSorter(dependency_graph)
    sorted_structs = list(topo_sort.static_order())
    # TODO: handle cycle errors by raising a DiagnosticError
    # and popping offending structs

    new_project = Project(
        struct_registry=_nested_freeze(struct_registry),
        sourcefile_graph=_nested_freeze(sourcefile_graph),
        mtime_graph=_nested_freeze(mtime_graph),
        dependency_graph=_nested_freeze(dependency_graph),
        diagnostic_errors=tuple(diagnostic_errors),
    )
    return new_project


if __name__ == "__main__":
    project = load_project()
    for struct_id in registry_ids(project.struct_registry):
        print("Loaded struct:", struct_id)
    for diagnostic in project.diagnostic_errors:
        print(diagnostic)

    for key, value in project.dependency_graph.items():
        if not value:
            print(f"{key} has no dependencies")
        else:
            print(key)
            for dependency in value:
                print(f"\tdepends on {dependency}")

    breakpoint()
