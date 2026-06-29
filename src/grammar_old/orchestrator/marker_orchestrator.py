"""
Implements `MarkerOrchestrator` which manages following registries:
- FeatureMarkersRegistry: loads/manages FeatureMarkers configs
- ContingentFeatureMarkersRegistry: loads/manages ContingentFeatureMarkers configs
- MarkerRegistry: orchestrates both registries, provides unified lookup
"""

from __future__ import annotations
from src.grammar_old.registry.feature_values_registry import FeatureValuesRegistry
from src.grammar_old.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar_old.registry.feature_marker_registry import FeatureMarkersRegistry
from src.grammar_old.registry.feature_combination_registry import FeatureValueCombinations
from src.grammar_old.registry.contingent_marker_registry import (
    ContingentFeatureMarkers,
    ContingentFeatureMarkersRegistry,
)
from src.grammar_old.registry.feature_marker_registry import (
    FeatureMarkers,
    FeatureMarkersRegistry,
)

from loguru import logger


class MarkerOrchestrator:
    """
    Orchestrates FeatureMarkersRegistry, ContingentFeatureMarkersRegistry,
    and FeatureOrchestrator. Uses FeatureOrchestrator to validate all feature
    combintions and values listed.
    """

    def __init__(
        self,
        feature_marker_configs: list[dict],
        contingent_marker_configs: list[dict],
        feature_orchestrator: FeatureOrchestrator,
    ):
        self.is_initialized = False
        self.feature_orchestrator = feature_orchestrator
        self.feature_values_registry = feature_orchestrator.feature_values_registry
        if not feature_orchestrator:
            logger.warning(
                "MarkerRegistry requres at minumum a feature registry to initialize. "
                "Returning an uninitialized MarkerRegistry. "
                "Provide a feature registry to load configs and initialize MarkerRegistry."
            )
            return
        self.features = feature_orchestrator.features
        # TODO: FeatureCombinations is buggy so it is commented out for now
        # self.feature_combinations = feature_orchestrator.feature_combinations

        self.feature_markers_registry = FeatureMarkersRegistry(
            feature_orchestrator=self.feature_orchestrator,
            config_objects=feature_marker_configs,
        )
        self.feature_markers = self.feature_markers_registry.data

        self.contingent_markers_registry = ContingentFeatureMarkersRegistry(
            feature_orchestrator=self.feature_orchestrator,
            config_objects=contingent_marker_configs,
        )
        self.contingent_markers: dict[str, ContingentFeatureMarkers] = (
            self.contingent_markers_registry.data
        )

        self.initialize()
        if not self.is_initialized:
            raise ValueError(
                "Error occurred while initializing MarkerRegistry, check logs."
            )

    def _validate_feature_values(self):
        """
        Iterate through every `FeatureMarkers` object and check its features
        are supported by `self.feature_orchestrator`
        """
        for markers_name, markers in self.feature_markers.items():
            feature = markers.feature
            if feature.name not in self.features:
                raise KeyError(
                    f"{markers_name} has unsupported feature {feature.name} "
                    f"expected one of {list(self.features.keys())}"
                )
            feature = self.features[feature.name]
            for feature_val in markers.data:
                if feature_val not in feature.values:
                    raise KeyError(
                        f"Unsupported value {feature_val} for feature {feature.name} "
                        f"in marker set {markers_name}. Expected values are {feature.values}"
                    )

    def _validate_contingent_features(self):
        """
        Iterate through every `ContingentFeatureMarkers` object and check its features
        are supported by `self.feature_orchestrator`
        """
        for markers_name, markers in self.contingent_markers.items():
            for vector in markers.feature_mappings.keys():
                for f_name, f_val in vector:
                    if f_name not in self.features:
                        raise KeyError(
                            f"{markers_name} has unsupported feature {f_name} "
                            f"expected one of {list(self.features.keys())}"
                        )
                    feature = self.features[f_name]
                    if f_val not in feature.values:
                        raise KeyError(
                            f"Unsupported value {f_val} for feature {f_name} "
                            f"in marker set {markers_name}. Expected values are {feature.values}"
                        )

    def initialize(self):
        if self.feature_markers_registry:
            self._validate_feature_values()
        if self.contingent_markers_registry:
            self._validate_contingent_features()
        self.is_initialized = True

    def get_feature_markers(self, name: str) -> FeatureMarkers:
        """Look up a feature marker config by filename stem."""
        name = name.removeprefix("$")
        if name not in self.feature_markers:
            raise KeyError(f"No FeatureMarkers found with name '{name}'.")
        return self.feature_markers[name]

    def get_contingent_markers(self, name: str) -> ContingentFeatureMarkers:
        """Look up a contingent marker config by filename stem."""
        name = name.removeprefix("$")
        if name not in self.contingent_markers:
            raise KeyError(f"No ContingentFeatureMarkers found with name '{name}'.")
        return self.contingent_markers[name]

    # TODO: FeatureCombinations is buggy so it is commented out for now
    # def get_feature_combinations(self, name: str) -> FeatureValueCombinations:
    #     """Look up a feature combinations config via feature_orchestrator."""
    #     return self.feature_orchestrator.get_feature_combinations(name)


if __name__ == "__main__":
    from src.constants import EXAMPLE_YAML_DIR

    # test initializing each config
    # TODO: update since
    # feature_reg = FeatureMarkersRegistry.from_YAML_DIR(EXAMPLE_YAML_DIR)
    # conting_marker_reg = ContingentFeatureMarkersRegistry.from_YAML_DIR(EXAMPLE_YAML_DIR)
    # marker_reg = MarkerRegistry.from_YAML_DIR(EXAMPLE_YAML_DIR)
    breakpoint()
