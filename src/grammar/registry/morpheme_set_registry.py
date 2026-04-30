from src.grammar.classes import Registry
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from dataclasses import dataclass, field
import os
from loguru import logger


@dataclass
class MorphemeSet:
    """
    Maps arbitrary feature vectors to morpheme strings.
    Corresponds to a ``kind: MorphemeSet`` YAML config.

    Attributes:
        feature_mappings: Dict mapping feature vector (frozenset of items) to MarkerList
        source: Filepath this config was loaded from
    """

    feature_mappings: dict[frozenset[tuple[str, str]], str] = field(
        default_factory=dict
    )
    source: os.PathLike | None = None

    @classmethod
    def from_config(
        cls, config: dict, feature_orchestrator: FeatureOrchestrator
    ) -> "MorphemeSet":
        """Build a MorphemeSet from a full YAML config dict."""
        source = config.get("source_path")
        morpheme_config = config.get("data", [])

        feature_mappings: dict[frozenset[tuple[str, str]], str] = {}
        for entry in morpheme_config:
            features_dict = entry.get("features", {})
            morpheme = entry.get("morpheme", [])

            # Validate features
            for f_name, f_val in features_dict.items():
                feature = feature_orchestrator.get_feature(f_name)
                if f_val not in feature.values:
                    raise ValueError(
                        f"Invalid value '{f_val}' for feature '{f_name}' in {source}"
                    )

            vector = frozenset(features_dict.items())
            feature_mappings[vector] = morpheme

        return cls(
            feature_mappings=feature_mappings,
            source=source,
        )

    def get_morpheme(self, **feature_dict: str) -> str:
        """Retrieve morpheme matching the feature vector."""
        for vector, morpheme in self.feature_mappings.items():
            if vector.issubset(feature_dict.items()):
                return morpheme

        raise KeyError(
            f"No matching feature vector in {self.source} for {feature_dict}"
        )

    def __str__(self):
        return (
            f"MorphemeSet(source='{self.source}', "
            f"vectors={len(self.feature_mappings)})"
        )

    def __repr__(self):
        return self.__str__()


class MorphemeSetRegistry(Registry):
    """
    Registry for ``kind: MorphemeSetRegistry`` configs.
    ``data`` maps config filename stems to MorphemeSet objects.
    """

    def __init__(
        self,
        feature_orchestrator: FeatureOrchestrator,
        data: dict[str, MorphemeSet | None] = None,
        config_objects: dict[str, dict | None] = None,
    ):
        self.feature_orchestrator = feature_orchestrator
        super().__init__(
            kind="MorphemeSet",
            data=data,
            config_objects=config_objects,
        )

    def load_all_configs(self) -> dict[str, MorphemeSet]:
        config_items: dict[str, MorphemeSet] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate MorphemeSet '{key}' found in "
                        f"multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, MorphemeSet]:
        source_path = config.get("source_path", "")
        name = os.path.splitext(os.path.basename(source_path))[0] if source_path else ""
        contingent_markers = MorphemeSet.from_config(
            config, self.feature_orchestrator
        )
        return {name: contingent_markers}
