"""
Registries and dataclasses for morphological features.

Registry classes (inherit Registry from src.registry_utils):
- FeatureValuesRegistry: loads/manages FeatureDefinitions configs
- FeatureCombinationsRegistry: loads/manages FeatureCombinations configs
- FeatureRegistry: orchestrates both registries

Dataclasses:
- Feature: a single feature category and its possible values

Utilities:
- FeatureValueCombinations: expands and queries licit feature-value combinations
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.grammar.registry.feature_combination_registry import (
    FeatureValueCombinations,
    FeatureCombinationsRegistry,
)
from src.grammar.registry.feature_registry import Feature, FeatureValuesRegistry
from src.grammar.classes import Orchestrator


class FeatureRegistry(Orchestrator):
    """
    Orchestrates FeatureValuesRegistry and FeatureCombinationsRegistry.
    """

    feature_regex = re.compile(r"\[([^=]+)=([^=]+)\]")

    def __init__(
        self,
        feature_configs: dict[str, dict],
        feature_combo_configs: dict[str, dict],
    ):
        self.feature_registry = FeatureValuesRegistry(config_objects=feature_configs)
        self.feature_combinations_registry = FeatureCombinationsRegistry(config_objects=feature_combo_configs)

        self.features: dict[str, Feature] = self.feature_registry.data
        self.feature_combinations: dict[str, FeatureValueCombinations] = (
            self.feature_combinations_registry.data
        )

    def get_feature(self, name: str) -> Feature:
        if name not in self.features:
            raise KeyError(f"No feature found with name '{name}'.")
        return self.features[name]

    def get_feature_combinations(self, name: str) -> FeatureValueCombinations:
        if name not in self.feature_combinations:
            raise KeyError(f"No feature-combinations config found with name '{name}'.")
        return self.feature_combinations[name]


def stringify_features(features: dict[str, str]) -> str:
    feature_strings = [
        f"[{feature_name}={feature_value or 'unmarked'}]"
        for feature_name, feature_value in features.items()
    ]
    feature_strings.sort()
    result_str = "".join(feature_strings)
    return result_str


def serialize_feature_str(feature_str: str) -> dict[str, str]:
    feature_tuples = FeatureRegistry.feature_regex.findall(feature_str)
    feature_dict = {}
    for feature_name, feature_value in feature_tuples:
        feature_dict[feature_name] = feature_value
    return feature_dict
