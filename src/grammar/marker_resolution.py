"""
Resolves marker lists for a paradigm+feature-value combination.

Separated from yaml_server to avoid a circular import:
  yaml_server ← lexicon ← yaml_server (get_yaml_data_safe)
"""

from __future__ import annotations

from ssl import RAND_pseudo_bytes

from loguru import logger

from src.grammar.acceptor_compilation import build_fst_context_for_project
from src.grammar.lexicon import stringify_lexemes
from src.grammar.transducer_compilation import compile_marker, compile_rules_for_project
from src.models import (
    CompiledMarker,
    Feature,
    FeatureCombination,
    FeatureMarker,
    FeatureMarkerFile,
    FeatureMarkerReference,
    FeatureTrie,
    FeatureVectorType,
    FixedFeatureValue,
    InflectionalFeatureSpecification,
    Marker,
    MultiFeatureMarker,
    MultiFeatureMarkerFile,
    MultiFeatureOnly,
    ParadigmFile,
    PartOfSpeechFile,
    Project,
)
from src.yaml.yaml_server import load_project


def get_paradigm_feature_trie(paradigm_id: str, project: Project) -> FeatureTrie:
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
    feature_marker_files = [
        project.struct_registry["FeatureMarkerFile"].get(spec.feature_marker)
        for spec in paradigm.feature_markers
        if isinstance(spec, FeatureMarkerReference)
    ]
    multi_feature_marker_files = [
        project.struct_registry["MultiFeatureMarkerFile"].get(file_id)
        for file_id in paradigm.multifeature_markers or tuple()
    ]
    if paradigm.feature_value_combinations is None:
        return cartesian_product_feature_trie(
            paradigm=paradigm,
            remaining_features=inflectional_features,
            project=project,
            feature_marker_files=feature_marker_files,
            multi_feature_marker_files=multi_feature_marker_files,
        )

    return feature_combo_to_trie(
        paradigm.feature_value_combinations,
        inflectional_features,
    )


def cartesian_product_feature_trie(
    paradigm: ParadigmFile,
    remaining_features: list[Feature],
    project: Project,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    exponed_features: list[tuple[str, str]] | None = None,
) -> FeatureTrie | None:
    if not remaining_features:
        return None
    if exponed_features is None:
        exponed_features = []
    remaining_features = remaining_features.copy()
    current_feature = remaining_features.pop(0)
    current_feature_spec: InflectionalFeatureSpecification = next(
        feature_spec
        for feature_spec in paradigm.feature_markers
        if feature_spec.feature == current_feature.id
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
        )

    return FeatureTrie(
        feature_id=current_feature.id,
        feature_values=subtree,
        markers=marker_map,
    )


def feature_combo_to_trie(
    feature_combo: FeatureCombination,
    paradigm: ParadigmFile,
    remaining_features: list[Feature],
    project: Project,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
    exponed_features: list[tuple[str, str]] | None = None,
) -> FeatureTrie:
    if not remaining_features:
        return None
    remaining_features = remaining_features.copy()
    current = remaining_features.pop(0)
    subtree = {}
    combo_value = feature_combo.feature_vector[current.id]
    if combo_value == "*":
        for value in current.values:
            subtree[value] = feature_combo_to_trie(
                feature_combo,
                remaining_features,
            )
    elif combo_value == "undefined":
        subtree["undefined"] = feature_combo_to_trie(
            feature_combo,
            remaining_features,
        )
    else:
        for value in combo_value:
            subtree[value] = feature_combo_to_trie(
                feature_combo,
                remaining_features,
            )
    return FeatureTrie(feature_id=current.id, feature_values=subtree)


def compile_markers_for_node(
    current_feature: Feature,
    current_feature_spec: InflectionalFeatureSpecification,
    exponed_features: list[tuple[str, str]],
    paradigm: ParadigmFile,
    feature_marker_files: list[FeatureMarkerFile],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
):
    """
    Assign markers to each child of the current node.
    """
    marker_map: dict[str, tuple[CompiledMarker, ...]] = {}
    if isinstance(current_feature_spec, FixedFeatureValue):
        multifeat_markers = get_multifeature_markers_for_current(
            current_feature=current_feature,
            current_feature_value=current_feature_spec.feature_value,
            exponed_features=exponed_features,
            multi_feature_marker_files=multi_feature_marker_files,
            paradigm=paradigm,
            project=project,
        )
        marker_map[current_feature_spec.feature_value] = multifeat_markers

    elif isinstance(current_feature_spec, FeatureMarkerReference):
        for value in current_feature.values:
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

    else:  # MultiFeatureMarkerOnly
        for value in current_feature.values:
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
                fst_array = compile_marker(marker, paradigm, project)
                compiled = CompiledMarker(
                    marker=marker,
                    fst=fst_array,
                    sourcefile_kind="MultiFeatureMarkerFile",
                    sourcefile_id=multifeat_marker.id,
                    feature_set=tuple(multifeat_marker.feature_values.items()),
                )
                current_markers.append(compiled)
            break
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
        fst_array = compile_marker(marker, paradigm, project)
        compiled = CompiledMarker(
            marker=marker,
            fst=fst_array,
            sourcefile_kind="FeatureMarkerFile",
            sourcefile_id=feature_marker_file.id,
            feature_set=tuple(
                (
                    current_feature,
                    current_feature_value,
                )
            ),
        )
        current_markers.append(compiled)
    return tuple(current_markers)


def get_fixed_features_for_paradigm(
    paradigm: ParadigmFile,
) -> set[FixedFeatureValue]:
    fixed_features = set(
        feature_spec
        for feature_spec in paradigm.feature_markers
        if isinstance(feature_spec, FixedFeatureValue)
    )

    return fixed_features


if __name__ == "__main__":
    project = load_project()
    project = build_fst_context_for_project(project)
    project = compile_rules_for_project(project)

    for paradigm_id in project.struct_registry["ParadigmFile"].keys():
        feature_space = get_paradigm_feature_trie(paradigm_id, project)
        breakpoint()
