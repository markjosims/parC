"""
Implements the `Paradigm` and `GrammarRegistry` classes, which
are the highest-level objects in the registry system.

The `Paradigm` class describes a paradigm or sub-paradigm in the
linguistic sense, represented here as a set of `Marker` lists over
a feature space. It also provides logic for defining the order of
application for markers, and for selecting stems and principal parts
from the lexicon.

The `GrammarRegistry` class orchestrates all registries for a given language.
[At present, the `GrammarRegistry` is essentially a wrapper over the
`MarkerRegistry` and `FstRegistry`, but it will eventually also include
the `LexiconRegistry`, and will directly load in `Paradigm` objects.
Since paradigm objects are themselves the the highest level of abstraction
in the registry system, there is no intermediate `ParadigmRegistry` class.]
"""

from loguru import logger
import pynini
from pynini.lib import pynutil

from src.fst_utils import FsaLike
from src.registry.registry_utils import Registry
from src.registry.marker_registry import (
    Marker,
    MarkerList,
    MarkerRegistry,
    FeatureMarkers,
    ContingentMarkers,
)
from src.registry.fst_registry import FstRegistry, InventoryItem
from src.registry.feature_registry import (
    FeatureRegistry,
    FeatureValueCombinations,
    Feature,
    stringify_features,
    serialize_feature_str,
)
from src.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.constants import TIRA_CONFIG_DIR
from typing import Any, Dict, Dict, List, Optional, Tuple, Union
from collections import defaultdict
import itertools
import os
import pandas as pd
from pathlib import Path
import functools
from tqdm import tqdm
from copy import deepcopy

EDIT_BOUND = 5
EDIT_COST = 1


class Grammar(Registry):
    """
    Orchestrates all registries for a given language.
    """

    def __init__(
        self,
        marker_registry: Optional[MarkerRegistry] = None,
        lexicon_registry: Optional[LexiconRegistry] = None,
        fst_registry: Optional[FstRegistry] = None,
        feature_registry: Optional[FeatureRegistry] = None,
        config_objects: Optional[Dict[str, dict]] = None,
        paradigms: Optional[Dict[str, Paradigm]] = None,
        do_initialize: bool = False,
    ):
        self.is_initialized = False
        super().__init__(kind="Paradigm", data=paradigms, config_objects=config_objects)

        self.marker_registry = marker_registry
        self.lexicon_registry = lexicon_registry
        self.fst_registry = fst_registry
        self.feature_registry = feature_registry

        self.paradigms = paradigms or []

        if do_initialize:
            self.initialize()

    @classmethod
    def from_config_dir(cls, config_dir: str) -> "Grammar":
        """
        Factory method for constructing a GrammarRegistry object from a config directory.
        """

        logger.info("Initializing GrammarRegistry from config directory.")
        grammar_reg = super().from_config_dir(config_dir)

        # load dependent registries from lowest level of abstraction to highest
        # logging errors while loading as much as possible
        feature_registry = None
        try:
            feature_registry = FeatureRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading FeatureRegistry: {e}")

        fst_registry = None
        try:
            fst_registry = FstRegistry.from_config_dir(config_dir)
        except Exception as e:
            logger.exception(f"Error occurred while loading FstRegistry: {e}")

        marker_registry = None
        lexicon_registry = None
        if feature_registry is not None:
            try:
                marker_registry = MarkerRegistry.from_config_dir(
                    config_dir, feature_registry=feature_registry
                )
            except Exception as e:
                logger.exception(f"Error occurred while loading Marker registry: {e}")

            try:
                lexicon_registry = LexiconRegistry.from_config_dir(
                    config_dir, feature_registry=feature_registry
                )
            except Exception as e:
                logger.exception(f"Error occurred while loading Lexicon registry: {e}")

        grammar_reg.marker_registry = marker_registry
        grammar_reg.feature_registry = feature_registry
        grammar_reg.lexicon_registry = lexicon_registry
        grammar_reg.fst_registry = fst_registry

        # only load paradigms if all child registries loaded successfully
        # since paradigm loading depends on all of them
        paradigms = None
        if all(
            reg is not None for reg in [marker_registry, lexicon_registry, fst_registry]
        ):
            logger.info("All child registries loaded successfully. Loading paradigms.")
            try:
                paradigms = grammar_reg.load_all_configs()
                logger.info(f"Loaded {len(paradigms)} paradigms successfully.")
            except Exception as e:
                logger.exception(f"Error occurred while loading paradigms: {e}")
        grammar_reg.paradigms = paradigms
        grammar_reg.initialize()
        return grammar_reg

    def load_all_configs(self) -> Dict[str, Paradigm]:
        config_items: Dict[str, Paradigm] = {}
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

    def load_data_from_config(self, config: dict) -> Dict[str, Paradigm]:
        source_path = config.get("source_path", "")
        name = (
            os.path.splitext(os.path.basename(source_path))[0]
            if source_path
            else config.get("part_of_speech", "")
        )
        paradigm = Paradigm.from_config(
            config, self.marker_registry, self.lexicon_registry, self.fst_registry
        )
        return {name: paradigm}

    def initialize(self):
        if all(
            reg is not None
            for reg in [
                self.marker_registry,
                self.lexicon_registry,
                self.fst_registry,
                self.feature_registry,
            ]
        ):
            self.is_initialized = True
            logger.info(
                "All child registries detected, GrammarRegistry loaded successfully."
            )
        else:
            if self.marker_registry is None:
                logger.warning(
                    "Grammar registry received None instead of MarkerRegistry"
                )
            if self.fst_registry is None:
                logger.warning("Grammar registry received None instead of FstRegistry")
            if self.lexicon_registry is None:
                logger.warning(
                    "Grammar registry received None instead of LexiconRegistry"
                )
            if self.feature_registry is None:
                logger.warning(
                    "Grammar registry received None instead of FeatureRegistry"
                )


if __name__ == "__main__":
    import random

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
