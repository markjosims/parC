"""
Resolves marker lists for a paradigm+feature-value combination.

Separated from yaml_server to avoid a circular import:
  yaml_server ← lexicon ← yaml_server (get_yaml_data_safe)
"""

from __future__ import annotations

from typing import Literal, Sequence

import msgspec
import pandas as pd
import pynini
from loguru import logger

from src.diagnostics import build_diagnostic_error
from src.grammar.acceptor_compilation import (
    build_fst_context_for_project,
    filter_strings_by_pattern,
    fsa,
    fsm_strings,
    word_fsa,
)
from src.grammar.fst_utils import feature_dict_to_tuple, stringify_features
from src.grammar.lexicon import (
    convert_lexeme_table_to_lexemes,
    filter_lexicon_by_features,
    retrieve_lexeme,
)
from src.grammar.transducer_compilation import compile_marker, compile_rules_for_project
from src.models import (
    CompiledMarker,
    Feature,
    FeatureCombination,
    FeatureMarkerFile,
    FeatureMarkerReference,
    FeatureSet,
    FeatureSetType,
    FixedFeatureValue,
    FixedLexicalFeatureValue,
    InflectionalFeatureSpecification,
    InflectTrie,
    Lexeme,
    LexicalFeatureMarkerReference,
    LexicalFeatureSpecification,
    LexicalMultiFeatureOnly,
    LexicalTrie,
    MultiFeatureMarkerFile,
    ParadigmFile,
    PartOfSpeechFile,
    Project,
    UnrealizedLexicalFeature,
)
from src.yaml.yaml_server import load_project


def get_paradigm_tries(
    paradigm_id: str, project: Project
) -> tuple[InflectTrie, LexicalTrie]:
    paradigm: ParadigmFile = project.struct_registry["ParadigmFile"][paradigm_id]
    part_of_speech: PartOfSpeechFile = project.struct_registry["PartOfSpeechFile"][
        paradigm.part_of_speech
    ]
    inflectional_features: list[Feature] = sorted(
        [
            project.struct_registry["Feature"].get(feature)
            for feature in part_of_speech.inflectional_features
        ],
        key=lambda f: f.id,
    )
    lexical_features: list[Feature] = sorted(
        [
            project.struct_registry["Feature"].get(feature)
            for feature in part_of_speech.lexical_features
        ],
        key=lambda f: f.id,
    )

    inflectional_feature_marker_files = [
        project.struct_registry["FeatureMarkerFile"].get(spec.feature_marker)
        for spec in paradigm.inflectional_feature_specs
        if isinstance(spec, FeatureMarkerReference)
    ]
    lexical_feature_marker_files = [
        project.struct_registry["FeatureMarkerFile"].get(spec.feature_marker)
        for spec in paradigm.lexical_feature_specs
        if isinstance(spec, FeatureMarkerReference)
    ]

    multi_feature_marker_files = [
        project.struct_registry["MultiFeatureMarkerFile"].get(file_id)
        for file_id in paradigm.multifeature_markers or tuple()
    ]
    if paradigm.feature_value_combinations is None:
        inflect_trie = cartesian_product_feature_trie(
            paradigm=paradigm,
            remaining_features=inflectional_features,
            project=project,
            feature_marker_files=inflectional_feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
        )

    else:
        inflect_trie = feature_combo_to_trie(
            feature_combo=paradigm.feature_value_combinations,
            remaining_features=inflectional_features,
            paradigm=paradigm,
            project=project,
            feature_marker_files=inflectional_feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
        )

    lexical_trie = cartesian_product_feature_trie(
        paradigm=paradigm,
        remaining_features=lexical_features,
        project=project,
        feature_marker_files=lexical_feature_marker_files,
        multi_feature_marker_files=multi_feature_marker_files,
        feature_type="lexical",
    )
    return inflect_trie, lexical_trie


def cartesian_product_feature_trie(
    paradigm: ParadigmFile,
    remaining_features: list[Feature],
    project: Project,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    exponed_features: list[tuple[str, str]] | None = None,
    feature_type: Literal["lexical", "inflectional"] = "inflectional",
) -> InflectTrie | LexicalTrie | None:
    if not remaining_features:
        return None
    if exponed_features is None:
        exponed_features = []
    remaining_features = remaining_features.copy()
    current_feature = remaining_features.pop(0)
    spec_array_field = f"{feature_type}_feature_specs"
    feature_spec_array = getattr(paradigm, spec_array_field)
    feature_spec_field = f"{feature_type}_feature"

    current_feature_spec: (
        InflectionalFeatureSpecification | LexicalFeatureSpecification
    ) = next(
        feature_spec
        for feature_spec in feature_spec_array
        if getattr(feature_spec, feature_spec_field) == current_feature.id
    )
    marker_map = compile_markers_for_node(
        paradigm=paradigm,
        current_feature=current_feature,
        current_feature_spec=current_feature_spec,
        exponed_features=exponed_features,
        feature_marker_files=feature_marker_files,
        multi_feature_marker_files=multi_feature_marker_files,
    )
    subtree = {}
    for feature_value in marker_map.keys():
        current_exponed = exponed_features + [(current_feature.id, feature_value)]
        subtree[feature_value] = cartesian_product_feature_trie(
            paradigm=paradigm,
            remaining_features=remaining_features,
            project=project,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
            exponed_features=current_exponed,
            feature_type=feature_type,
        )

    if feature_type == "inflectional":
        return InflectTrie(
            feature_id=current_feature.id,
            feature_values=subtree,
            marker_map=marker_map,
        )
    lexeme_map = {}
    for feature_value in marker_map.keys():
        current_exponed = exponed_features + [(current_feature.id, feature_value)]

        lexemes = filter_lexicon_by_features(
            lexicon_basename=paradigm.part_of_speech,
            lexical_features=current_exponed,
        )
        lexemes = lexemes.to_dict(orient="records")
        lexeme_map[feature_value] = lexemes
    return LexicalTrie(
        feature_id=current_feature.id,
        feature_set=subtree,
        marker_map=marker_map,
        lexeme_map=lexeme_map,
    )


def feature_combo_to_trie(
    feature_combo: FeatureCombination,
    paradigm: ParadigmFile,
    remaining_features: list[Feature],
    project: Project,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    exponed_features: list[tuple[str, str]] | None = None,
) -> InflectTrie:
    if not remaining_features:
        return None
    remaining_features = remaining_features.copy()
    current_feature = remaining_features.pop(0)
    current_feature_spec: InflectionalFeatureSpecification = next(
        feature_spec
        for feature_spec in paradigm.inflectional_feature_specs
        if feature_spec.inflectional_feature == current_feature.id
    )

    subtree = {}
    combo_value = feature_combo.feature_vector[current_feature.id]
    if combo_value == "*":
        marker_map = compile_markers_for_node(
            paradigm=paradigm,
            current_feature=current_feature,
            current_feature_spec=current_feature_spec,
            exponed_features=exponed_features,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
        )
        for feature_value in marker_map.keys():
            subtree[feature_value] = feature_combo_to_trie(
                feature_combo=feature_combo,
                paradigm=paradigm,
                remaining_features=remaining_features,
                project=project,
                feature_marker_files=feature_marker_files,
                multi_feature_marker_files=multi_feature_marker_files,
                exponed_features=exponed_features
                + [(current_feature.id, feature_value)],
            )

    elif combo_value == "undefined":
        marker_map = compile_markers_for_node(
            paradigm=paradigm,
            current_feature=current_feature,
            current_feature_spec=current_feature_spec,
            exponed_features=exponed_features,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
            allowed_features=["undefined"],
        )
        subtree[feature_value] = feature_combo_to_trie(
            feature_combo=feature_combo,
            paradigm=paradigm,
            remaining_features=remaining_features,
            project=project,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
            exponed_features=exponed_features + [(current_feature.id, feature_value)],
        )
    else:  # combo_value is a tuple of feature value strs
        marker_map = compile_markers_for_node(
            paradigm=paradigm,
            current_feature=current_feature,
            current_feature_spec=current_feature_spec,
            exponed_features=exponed_features,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
            allowed_features=combo_value,
        )
        for feature_value in marker_map.keys():
            subtree[feature_value] = feature_combo_to_trie(
                feature_combo=feature_combo,
                paradigm=paradigm,
                remaining_features=remaining_features,
                project=project,
                feature_marker_files=feature_marker_files,
                multi_feature_marker_files=multi_feature_marker_files,
                exponed_features=exponed_features
                + [(current_feature.id, feature_value)],
            )

    return InflectTrie(
        feature_id=current_feature.id,
        feature_values=subtree,
        marker_map=marker_map,
    )


def compile_markers_for_node(
    current_feature: Feature,
    current_feature_spec: InflectionalFeatureSpecification
    | LexicalFeatureSpecification,
    exponed_features: list[tuple[str, str]],
    paradigm: ParadigmFile,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    allowed_features: list[str] | None = None,
):
    """
    Assign markers to each child of the current node.
    """
    marker_map: dict[str, tuple[CompiledMarker, ...]] = {}
    if allowed_features is None:
        allowed_features = current_feature.values
    if isinstance(current_feature_spec, (FixedFeatureValue, FixedLexicalFeatureValue)):
        if current_feature_spec.feature_value not in allowed_features:
            raise ValueError(
                "Fixed feature not in set of allowed features from feature combo "
                + "(TODO: this should be verified during schema validation."
            )
        multifeat_markers = get_multifeature_markers_for_current(
            current_feature=current_feature,
            current_feature_value=current_feature_spec.feature_value,
            exponed_features=exponed_features,
            multi_feature_marker_files=multi_feature_marker_files,
            paradigm=paradigm,
            project=project,
        )
        marker_map[current_feature_spec.feature_value] = multifeat_markers

    elif isinstance(
        current_feature_spec,
        (
            FeatureMarkerReference,
            LexicalFeatureMarkerReference,
        ),
    ):
        for value in allowed_features:
            feat_markers = get_feature_marker_for_current(
                current_feature=current_feature,
                current_feature_value=value,
                feature_marker_files=feature_marker_files,
                paradigm=paradigm,
                project=project,
            )
            multifeat_markers = get_multifeature_markers_for_current(
                current_feature=current_feature,
                current_feature_value=value,
                exponed_features=exponed_features,
                multi_feature_marker_files=multi_feature_marker_files,
                paradigm=paradigm,
                project=project,
            )
            marker_map[value] = feat_markers + multifeat_markers
    elif isinstance(current_feature_spec, UnrealizedLexicalFeature):
        return None
    else:  # MultiFeatureMarkerOnly
        for value in allowed_features:
            multifeat_markers = get_multifeature_markers_for_current(
                current_feature=current_feature,
                current_feature_value=value,
                exponed_features=exponed_features,
                multi_feature_marker_files=multi_feature_marker_files,
                paradigm=paradigm,
                project=project,
            )
            marker_map[current_feature_spec.feature_value] = multifeat_markers
    return marker_map


def get_multifeature_markers_for_current(
    current_feature: Feature,
    current_feature_value: str,
    exponed_features: list[tuple[str, str]],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    paradigm: ParadigmFile,
    project: Project,
) -> tuple[CompiledMarker, ...]:
    features_at_current = set(
        [current_feature.id] + [feature for feature, _ in exponed_features]
    )
    current_markers: list[CompiledMarker] = []
    for marker_file in multi_feature_marker_files:
        # first test that all features in marker file are covered
        # at current node
        file_features = set(marker_file.features)
        if not (current_feature.id in marker_file.features) or not (
            file_features.issubset(features_at_current)
        ):
            continue
        # now check if a particular marker within the file matches the
        # specific feature values at the current node
        for multifeat_marker in marker_file.data:
            if (
                not multifeat_marker.feature_values.get(current_feature.id, None)
                == current_feature_value
            ):
                continue
            if not all(
                multifeat_marker.feature_values[feature] == value
                for feature, value in exponed_features
            ):
                continue
            for marker in multifeat_marker.markers:
                if not marker.stage and marker_file.global_stage:
                    marker = msgspec.structs.replace(stage=marker_file.global_stage)

                fst_array = compile_marker(marker, paradigm, project)
                compiled = CompiledMarker(
                    marker=marker,
                    fst_array=fst_array,
                    sourcefile_kind="MultiFeatureMarkerFile",
                    sourcefile_id=multifeat_marker.id,
                    feature_set=FeatureSet(multifeat_marker.feature_values),
                )
                current_markers.append(compiled)
    return tuple(current_markers)


def get_feature_marker_for_current(
    current_feature: Feature,
    current_feature_value: str,
    feature_marker_files: list[FeatureMarkerFile],
    paradigm: ParadigmFile,
    project: Project,
) -> tuple[CompiledMarker, ...]:
    feature_marker_file = next(
        file for file in feature_marker_files if file.feature == current_feature.id
    )
    feature_marker = next(
        feature_marker
        for feature_marker in feature_marker_file.data
        if feature_marker.feature_value == current_feature_value
    )
    current_markers = []
    for marker in feature_marker.markers:
        if not marker.stage and feature_marker_file.global_stage:
            marker = msgspec.structs.replace(stage=feature_marker_file.global_stage)
        fst_array = compile_marker(marker, paradigm, project)
        compiled = CompiledMarker(
            marker=marker,
            fst_array=fst_array,
            sourcefile_kind="FeatureMarkerFile",
            sourcefile_id=feature_marker_file.id,
            feature_set=FeatureSet({current_feature: current_feature_value}),
        )
        current_markers.append(compiled)
    return tuple(current_markers)


def build_all_paradigm_tries(project: Project) -> Project:
    inflect_tries: dict[str, InflectTrie] = {}
    lexical_tries: dict[str, LexicalTrie] = {}
    for paradigm_id in project.struct_registry["ParadigmFile"].keys():
        inflect_trie, lexical_trie = get_paradigm_tries(paradigm_id, project)
        inflect_tries[paradigm_id] = inflect_trie
        lexical_tries[paradigm_id] = lexical_trie
    project = project._replace(
        inflect_tries=inflect_tries,
        lexical_tries=lexical_tries,
    )
    return project


def _compile_global_markers(
    paradigm: ParadigmFile,
) -> tuple[CompiledMarker, ...] | None:
    global_markers = []
    if paradigm.global_markers is None:
        return None
    for marker in paradigm.global_markers:
        marker_fst = compile_marker(marker)
        global_markers.append(
            CompiledMarker(
                marker=marker,
                feature_set=FeatureSet(),
                fst_array=marker_fst,
                sourcefile_kind="ParadigmFile",
                sourcefile_id=paradigm.id,
            )
        )
    return tuple(global_markers)


def build_all_paradigm_global_markers(project: Project) -> Project:
    global_marker_map = {}
    for paradigm_id, paradigm in project.struct_registry["ParadigmFile"].items():
        global_markers = _compile_global_markers(paradigm=paradigm)
        global_marker_map[paradigm_id] = global_markers
    new_project = project._replace(global_marker_map=global_marker_map)
    return new_project


def _get_multi_overrides(
    paradigm: ParadigmFile,
    feature_type: Literal["inflectional", "lexical"],
) -> list[str]:
    spec_array_field = f"{feature_type}_feature_specs"
    feature_spec_field = f"{feature_type}_feature"
    multi_override_features = [
        getattr(spec, feature_spec_field)
        for spec in getattr(paradigm, spec_array_field)
        if isinstance(
            spec,
            (
                FeatureMarkerReference,
                LexicalFeatureMarkerReference,
            ),
        )
    ]
    return multi_override_features


def _filter_out_overridden_markers(
    current_node: InflectTrie | LexicalTrie,
    multi_overrides: list[str],
    current_markers: Sequence[CompiledMarker],
    current_feature_value: str,
) -> tuple[CompiledMarker, ...]:
    if current_node.feature_id in multi_overrides and any(
        (
            current_node.feature_id,
            current_feature_value,
        )
        in marker.feature_set
        for marker in current_markers
        if marker.sourcefile_kind == "MultiFeatureMarkerFile"
    ):
        # filter out FeatureMarker files
        current_markers = [
            marker
            for marker in current_markers
            if marker.sourcefile_kind != "FeatureMarkerFile"
        ]
    return current_markers


def _resolve_markers_from_trie(
    feature_set: dict[str, str],
    trie: InflectTrie | LexicalTrie,
    multi_overrides: list[str],
) -> list[CompiledMarker]:
    current_node = trie
    markers = []
    while current_node is not None:
        current_feature_value = feature_set[current_node.feature_id]
        if current_node.marker_map:
            current_markers = current_node.marker_map[current_feature_value]
            current_markers = _filter_out_overridden_markers(
                current_node=current_node,
                current_markers=current_markers,
                current_feature_value=current_feature_value,
                multi_overrides=multi_overrides,
            )
            current_node = current_node.feature_set[current_feature_value]
    return markers


def _flatten_trie(
    trie: InflectTrie | LexicalTrie,
    multi_overrides: list[str],
) -> dict[FeatureSet, tuple[CompiledMarker, ...]]:
    if trie is None:
        return {tuple(): tuple()}
    feature_set_to_markers = {}
    marker_map = trie.marker_map or {}
    for feature_value, subtree in trie.feature_set.items():
        current_feature_tuple = FeatureSet({trie.feature_id: feature_value})
        current_marker_array: tuple[CompiledMarker, ...] = marker_map.get(feature_value)

        flat = _flatten_trie(
            trie=subtree,
            multi_overrides=multi_overrides,
        )
        for child_feature_set, child_marker_array in flat.items():
            new_feature_set = child_feature_set + current_feature_tuple
            new_marker_array = current_marker_array + child_marker_array
            new_marker_array = _filter_out_overridden_markers(
                current_node=trie,
                multi_overrides=multi_overrides,
                current_markers=new_marker_array,
                current_feature_value=feature_value,
            )

            feature_set_to_markers[new_feature_set] = new_marker_array
    return feature_set_to_markers


def resolve_markers_for_feature_set(
    inflectional_features: dict[str, str],
    lexical_features: dict[str, str],
    paradigm_id: str,
    project: Project,
) -> list[CompiledMarker]:
    paradigm: ParadigmFile = project.struct_registry["ParadigmFile"][paradigm_id]
    inflect_trie = project.inflect_tries[paradigm_id]
    inflect_multi_overrides = _get_multi_overrides(
        paradigm,
        feature_type="inflectional",
    )
    lexical_trie = project.lexical_tries[paradigm_id]
    lexical_multi_overrides = _get_multi_overrides(
        paradigm,
        feature_type="lexical",
    )
    inflectional_markers = _resolve_markers_from_trie(
        inflectional_features,
        inflect_trie,
        inflect_multi_overrides,
    )
    lexical_markers = _resolve_markers_from_trie(
        lexical_features,
        lexical_trie,
        lexical_multi_overrides,
    )
    sorted_markers = insert_global_markers_and_sort(
        inflectional_markers + lexical_markers,
        paradigm,
        project,
    )
    return sorted_markers


def insert_global_markers_and_sort(
    marker_array: tuple[CompiledMarker, ...],
    paradigm: ParadigmFile,
    project: Project,
) -> tuple[CompiledMarker, ...]:
    global_markers = project.global_marker_map[paradigm.id]

    stage_order = ("stem_selection",) + (paradigm.stage_order or tuple())

    sorted_markers = tuple(
        sorted(
            [
                compiled_marker
                for compiled_marker in marker_array + (global_markers or [])
            ],
            key=lambda compiled_marker: (
                stage_order.index(compiled_marker.marker.stage)
                if compiled_marker.marker.stage
                else float("inf")
            ),
        )
    )

    return sorted_markers


def resolve_markers_for_paradigm(
    paradigm_id: str,
    project: Project,
) -> list[tuple[Lexeme, str, tuple[CompiledMarker, ...]]]:
    lexeme_marker_triples = []
    paradigm: ParadigmFile = project.struct_registry["ParadigmFile"][paradigm_id]
    inflectional_multi_overrides = _get_multi_overrides(
        paradigm=paradigm,
        feature_type="inflectional",
    )
    lexical_multi_overrides = _get_multi_overrides(
        paradigm=paradigm,
        feature_type="lexical",
    )
    inflectional_marker_map = _flatten_trie(
        project.inflect_tries[paradigm_id],
        multi_overrides=inflectional_multi_overrides,
    )
    lexeme_table = get_roots_for_paradigm(paradigm_id, project)
    lexeme_array = convert_lexeme_table_to_lexemes(
        lexeme_table=lexeme_table,
        part_of_speech_id=paradigm.part_of_speech,
        project=project,
    )
    lexical_marker_memo = {}
    for lexeme in lexeme_array:
        lexical_markers = lexical_marker_memo.setdefault(
            lexeme.lexical_features,
            _resolve_markers_from_trie(
                lexeme.lexical_features,
                project.lexical_tries[paradigm_id],
                lexical_multi_overrides,
            ),
        )
        for (
            inflectional_feature_set,
            inflectional_markers,
        ) in inflectional_marker_map.items():
            current_feature_set = lexeme.lexical_features + inflectional_feature_set
            inflected_string = stringify_features(current_feature_set) + lexeme.root
            sorted_markers = insert_global_markers_and_sort(
                marker_array=lexical_markers + inflectional_markers,
                paradigm=paradigm,
                project=project,
            )
            # TODO: use InflectedWord struct?
            lexeme_marker_triples.append(lexeme, inflected_string, sorted_markers)
        return lexeme_marker_triples


def get_roots_for_paradigm(paradigm_id: str, project: Project) -> pd.DataFrame:
    """
    Get the roots associated with a given paradigm.
    Paradigms may further filter roots from their associated
    part of speech using either a set of lexical feature values
    or a regex pattern filter.
    """
    paradigm: ParadigmFile = project.struct_registry["ParadigmFile"][paradigm_id]
    fixed_lexical_features = {
        spec.lexical_feature: spec.feature_value
        for spec in paradigm.lexical_feature_specs
        if isinstance(spec, FixedLexicalFeatureValue)
    }
    lexeme_table = filter_lexicon_by_features(
        lexicon_basename=paradigm.part_of_speech,
        lexical_features=fixed_lexical_features,
    )
    root_acceptor = pynini.union(
        *lexeme_table.root.apply(lambda root: fsa(root, project.fst_context))
    )
    if paradigm.filter_pattern:
        pattern_fsa = fsa(paradigm.filter_pattern, project.fst_context)
        filtered_roots = filter_strings_by_pattern(
            root_acceptor,
            pattern_fsa,
            project.fst_context,
        )
        root_in_filtered = lexeme_table.root.isin(filtered_roots)
        lexeme_table = lexeme_table[root_in_filtered]

    return lexeme_table


def inflect_lexeme(
    lexeme: Lexeme,
    paradigm_id: str,
    project: Project,
    homophone_index: int | None = None,
    **inflectional_features: str,
) -> pynini.Fst:
    markers = resolve_markers_for_feature_set(
        inflectional_features=inflectional_features,
        lexical_features=lexeme.lexical_features,
        paradigm_id=paradigm_id,
        project=project,
    )
    word_input = word_fsa(
        word_str=lexeme.root,
        fst_context=project.fst_context,
    )
    result: pynini.Fst = word_input
    for marker in markers:
        for fst in marker.fst_array:
            result @= fst
    return result


if __name__ == "__main__":
    project = load_project()
    project = build_fst_context_for_project(project)
    project = compile_rules_for_project(project)
    project = build_all_paradigm_tries(project)
    project = build_all_paradigm_global_markers(project)
    sorted_markers = resolve_markers_for_feature_set(
        inflectional_features={
            "tense": "present",
            "mood": "indicative",
            "person_number": "2sg",
        },
        lexical_features={"conjugation_class": "a_class"},
        paradigm_id="verb_a_stem",
        project=project,
    )
    lexeme = retrieve_lexeme(
        root="habl",
        part_of_speech_id="verb",
        project=project,
    )
    result_fst = inflect_lexeme(
        lexeme=lexeme,
        paradigm_id="verb_a_stem",
        project=project,
        **{
            "tense": "present",
            "mood": "indicative",
            "person_number": "2sg",
        },
    )
    strings = fsm_strings(result_fst, project.fst_context)
    resolved = resolve_markers_for_paradigm(paradigm_id="verb_a_stem", project=project)

    breakpoint()
