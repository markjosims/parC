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
    # TODO: add fst compilation online with feature space
    # resolution. will need to track set of available MultiFeatureMarkerFiles
    # at each node in traversal
    if paradigm.feature_value_combinations is None:
        return cartesian_product_feature_trie(
            paradigm,
            inflectional_features,
            project,
        )

    return feature_combo_to_trie(
        paradigm.feature_value_combinations,
        inflectional_features,
    )


def cartesian_product_feature_trie(
    paradigm: ParadigmFile,
    remaining_features: list[Feature],
    project: Project,
    exponed_features: list[tuple[str, str]] | None = None,
) -> FeatureTrie | None:
    if not remaining_features:
        return None
    remaining_features = remaining_features.copy()
    current = remaining_features.pop(0)
    current_feature_specification: InflectionalFeatureSpecification = next(
        feature_spec
        for feature_spec in paradigm.feature_markers
        if feature_spec.feature == current_feature.id
    )
    subtree = {}
    for value in current.values:
        subtree[value] = cartesian_product_feature_trie(remaining_features)
    return FeatureTrie(feature_id=current.id, feature_values=subtree)


def feature_combo_to_trie(
    feature_combo: FeatureCombination,
    remaining_features: list[Feature],
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
    feature_markers_files: list[FeatureMarkerFile],
    multifeature_marker_files: list[MultiFeatureMarkerFile],
):
    """
    Assign markers to each child of the current node.
    """
    marker_map: dict[str, tuple[CompiledMarker, ...]] = {}
    if isinstance(current_feature_spec, FixedFeatureValue):
        markers = get_multifeature_markers_for_current(
            current_feature=current_feature,
            current_feature_value=current_feature_spec.feature_value,
            exponed_features=exponed_features,
            multi_feature_marker_files=multifeature_marker_files,
        )
        marker_map[current_feature_spec.feature_value] = tuple(markers)

    elif isinstance(current_feature_spec, FeatureMarkerReference):
        feature_marker_file = next(
            file for file in feature_markers_files if file.feature == current_feature
        )
        for value in current_feature.values():
            feature_marker = next(
                marker
                for marker in feature_marker_file.data
                if marker.feature_value == value
            )
            markers = get_multifeature_markers_for_current(
                current_feature=current_feature,
                current_feature_value=value,
                exponed_features=exponed_features,
                multi_feature_marker_files=multifeature_marker_files,
            )
            marker_map[current_feature_spec.feature_value] = tuple(
                markers + [feature_marker]
            )
    else:  # MultiFeatureMarkerOnly
        for value in current_feature.values():
            markers = get_multifeature_markers_for_current(
                current_feature=current_feature,
                current_feature_value=value,
                exponed_features=exponed_features,
                multi_feature_marker_files=multifeature_marker_files,
            )
            marker_map[current_feature_spec.feature_value] = tuple(markers)
    for value, marker_array in marker_map.items():
        compiled_markers=[]
        for feature_marker in marker_array:
            if isinstance(feature_marker, FeatureMarker):
                for marker in feature_marker.markers:
                    compiled_markers.append(CompiledMarker(marker=marker,feature_set=tuple((current_feature,value))


def get_multifeature_markers_for_current(
    current_feature: Feature,
    current_feature_value: str,
    exponed_features: list[tuple[str, str]],
    multi_feature_marker_files: list[MultiFeatureMarkerFile],
) -> list[MultiFeatureMarker]:
    features_at_current = set(
        [current_feature.id] + [feature for feature, _ in exponed_features]
    )
    current_markers: list[MultiFeatureMarker] = []
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
        for marker in marker_file.data:
            if (
                not marker.feature_values.get(current_feature.id, None)
                == current_feature_value
            ):
                continue
            if not all(
                marker.feature_values[feature] == value
                for feature, value in exponed_features
            ):
                continue
            current_markers.append(marker)
            break
    return current_markers


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
