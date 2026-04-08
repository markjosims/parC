"""
Implements the `Paradigm` and `Grammar` classes, which
are the highest-level objects in the registry system.

The `Grammar` class orchestrates all registries for a given language.
"""

from loguru import logger

from src.grammar.classes import Orchestrator
from src.grammar.orchestrator.marker_orchestrator import MarkerOrchestrator
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.feature_values_registry import FeatureValuesRegistry
from src.grammar.registry.lexicon_registry import LexiconRegistry
from src.grammar.paradigm import Paradigm
import os
from camel_converter import to_snake


class Grammar(Orchestrator):
    """
    Orchestrates all data for a given language.
    """

    def __init__(
        self,
        feature_marker_configs: list[dict],
        contingent_marker_configs: list[dict],
        lexicon_configs: list[dict],
        inventory_configs: list[dict],
        pattern_configs: list[dict],
        rule_configs: list[dict],
        feature_configs: list[dict],
        feature_combo_configs: list[dict],
        paradigms: dict[str, Paradigm],
    ):
        self.is_initialized = False
        super().__init__(kind="Paradigm", data=paradigms)

        self.feature_orchestrator = FeatureOrchestrator(
            feature_configs=feature_configs, feature_combo_configs=feature_combo_configs
        )
        self.lexicon_registry = LexiconRegistry(config_objects=lexicon_configs)
        self.fst_orchestrator = FstOrchestrator(
            inventory_configs=inventory_configs,
            pattern_configs=pattern_configs,
            rule_configs=rule_configs,
            feature_values_registry=self.feature_orchestrator.feature_values_registry,
        )
        self.marker_orchestrator = MarkerOrchestrator(
            contingent_marker_configs=contingent_marker_configs,
            feature_marker_configs=feature_marker_configs,
            feature_values_registry=self.feature_orchestrator.feature_values_registry,
        )

        if not paradigms:
            logger.info("Loading paradigms.")
            try:
                paradigms = self.load_all_configs()
                logger.info(f"Loaded {len(paradigms)} paradigms successfully.")
            except Exception as e:
                logger.exception(f"Error occurred while loading paradigms: {e}")
        self.paradigms = paradigms
        self.initialize()

    def load_all_configs(self) -> dict[str, Paradigm]:
        config_items: dict[str, Paradigm] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = (
                        f"Duplicate Paradigm '{key}' found in multiple config files."
                    )
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, Paradigm]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get("part_of_speech", "")
        )
        paradigm = Paradigm.from_config(
            config,
            self.marker_orchestrator,
            self.lexicon_registry,
            self.fst_orchestrator,
        )
        return {name: paradigm}

    def initialize(self):
        if all(
            reg is not None
            for reg in [
                self.marker_orchestrator,
                self.lexicon_registry,
                self.fst_orchestrator,
                self.feature_orchestrator,
            ]
        ):
            self.is_initialized = True
            logger.info(
                "All child registries detected, Grammar loaded successfully."
            )
        else:
            if self.marker_orchestrator is None:
                logger.warning(
                    "Grammar received None instead of MarkerOrchestrator"
                )
            if self.fst_orchestrator is None:
                logger.warning(
                    "Grammar received None instead of FstOrchestrator"
                )
            if self.lexicon_registry is None:
                logger.warning(
                    "Grammar received None instead of LexiconRegistry"
                )
            if self.feature_orchestrator is None:
                logger.warning(
                    "Grammar received None instead of FeatureOrchestrator"
                )


if __name__ == "__main__":
    import random
    from src.constants import TIRA_CONFIG_DIR

    reg = Grammar.from_config_dir(TIRA_CONFIG_DIR)

    para = reg.paradigms["verb_no_pronoun"]
    root = random.choice(para.get_filtered_roots())
    stages = para.get_inflection_stages(
        root, {"tam": "imperfective", "class_marker": "l", "deixis": "itive"}
    )
    inflected_paradigm = para.get_subparadigm_table(root)

    para._build_main_graphs()
    random_form = random.choice(inflected_paradigm)["form"].split(";")[0]
    parse = para.get_parses(random_form)

    para._build_edit_graphs()
    random_index = random.randint(0, len(random_form) - 1)
    random_form_list = list(random_form)
    random_form_list.pop(random_index)
    random_form_deletion = "".join(random_form_list)
    search_hits = para.search_form(random_form_deletion)
    search_parses = [para.get_parses(hit_str) for hit_str, _ in search_hits]

    logger.info(f"random_form: {random_form}")
    logger.info(f"parse: {parse}")
    logger.info(f"random_form_deletion: {random_form_deletion}")
    logger.info(f"search_hits: {search_hits}")
    logger.info(f"search_parses: {search_parses}")

    breakpoint()
