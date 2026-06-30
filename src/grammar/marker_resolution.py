"""
Resolves marker lists for a paradigm+feature-value combination.

Separated from yaml_server to avoid a circular import:
  yaml_server ← lexicon ← yaml_server (get_yaml_data_safe)
"""

from __future__ import annotations

from src.lexicon import get_roots, get_principle_part_for_all_roots
from src.yaml_utils.models import (
    Marker,
    UnorderedMarker,
    StringMapMarker,
    resolve_marker,
)
from src.yaml_utils.yaml_server import get_markers, get_yaml_data_safe


def get_markers_for_paradigm(
    feature_values: set[tuple[str, str]] | dict[str, str],
    paradigm_name: str,
) -> list[Marker]:
    """
    Get all markers for a requested feature set for a given paradigm.
    Resolves principal_part markers into StringMapMarker using the paradigm's lexicon.
    """
    if isinstance(feature_values, dict):
        feature_values = set(feature_values.items())

    paradigm_data = get_yaml_data_safe("Paradigm", paradigm_name)
    part_of_speech = paradigm_data["part_of_speech"]

    feature_marker_files = paradigm_data["feature_markers"].values()
    contingent_feature_marker_files = paradigm_data.get("contingent_markers", [])

    feature_markers = get_markers(
        feature_marker_files, contingent_feature_marker_files, feature_values
    )

    if "global_markers" in paradigm_data:
        feature_markers.extend(
            resolve_marker(marker) for marker in paradigm_data["global_markers"]
        )

    if "global_stage" in paradigm_data:
        for i, marker in enumerate(feature_markers):
            if hasattr(marker, "stage") and marker.stage is None:
                feature_markers[i] = marker._replace(
                    stage=paradigm_data["global_stage"]
                )

    for i, marker in enumerate(feature_markers):
        if isinstance(marker, UnorderedMarker) and marker.kind == "principal_part":
            roots = get_roots(part_of_speech)
            pps = get_principle_part_for_all_roots(part_of_speech, marker.value)
            feature_markers[i] = StringMapMarker(
                kind="string_map",
                value=tuple(zip(roots, pps)),
            )

    return feature_markers
