"""
Implements the MorphemeSequence class, which handles concatenative morphology
by sequencing Lexicons, Paradigms, Patterns, and Rules, and the MorphemeSequenceRegistry
class, which manages multiple MorphemeSequence configurations.
"""

from loguru import logger
import os
import pynini
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.classes import Registry
from src.grammar.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.grammar.registry.paradigm_registry import ParadigmRegistry, Paradigm
from src.grammar.registry.morpheme_set_registry import MorphemeSetRegistry, MorphemeSet
from src.grammar.registry.rule_registry import Rule
from src.grammar.registry.feature_values_registry import Feature
from typing import Any


class MorphemeSequence:
    """
    Defines a sequence of morphemes and provides logic for generating
    inflected forms and analysis strings.
    """

    def __init__(
        self,
        name: str,
        sequence_data: list[dict],
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        morpheme_set_registry: MorphemeSetRegistry,
        fst_orchestrator: FstOrchestrator,
        source_path: str | None = None,
        fixed_features: dict[str, Feature] | None = None,
    ):
        self.name = name
        self.sequence_data = sequence_data
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.morpheme_set_registry = morpheme_set_registry
        self.fst_orchestrator = fst_orchestrator
        self.source_path = source_path
        self.fixed_features = fixed_features or {}
        self.is_initialized = False

        # To be populated during initialization
        self.morphemes = []
        self.features = set()

    @classmethod
    def from_config(
        cls,
        config: dict,
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        morpheme_set_registry: MorphemeSetRegistry,
        fst_orchestrator: FstOrchestrator,
    ) -> "MorphemeSequence":
        source_path = config.get("source_path")
        name = config.get("name")
        if not name and source_path:
            name = os.path.splitext(os.path.basename(source_path))[0]

        return cls(
            name=name or "[UNNAMED]",
            sequence_data=config.get("data", []),
            lexicon_registry=lexicon_registry,
            paradigm_registry=paradigm_registry,
            morpheme_set_registry=morpheme_set_registry,
            fst_orchestrator=fst_orchestrator,
            source_path=source_path,
            fixed_features=config.get("fixed_features"),
        )

    def to_dict(self) -> dict:
        return {
            "kind": "MorphemeSequence",
            "name": self.name,
            "data": self.sequence_data,
            "source_path": self.source_path,
            "fixed_features": self.fixed_features,
        }

    def initialize(self):
        """
        Resolve references and identify all involved features.
        """
        for item in self.sequence_data:
            m_type = item["type"]
            m_val = item["value"]

            resolved = None
            if m_type == "Lexicon":
                resolved = self.lexicon_registry.get_lexicon(m_val)
                if resolved:
                    self.features.update([f.name for f in resolved.features])
                    self.features.update([f.name for f in resolved.lexical_features])
            elif m_type == "Paradigm":
                resolved = self.paradigm_registry.get_paradigm(m_val)
                if resolved:
                    self.features.update([f.name for f in resolved.features])
                    # Paradigms also have access to lexical features of their lexicon
                    if resolved.lexicon:
                        self.features.update(
                            [f.name for f in resolved.lexicon.lexical_features]
                        )
            elif m_type == "Pattern":
                resolved = self.fst_orchestrator.fsa(m_val)
            elif m_type == "Rule":
                resolved = lambda input_fst: self.fst_orchestrator.apply_rule(
                    input_fst, m_val
                )
            elif m_type == "MorphemeSet":
                resolved = self.morpheme_set_registry.get_morpheme_set(m_val)
                if resolved:
                    self.features.update([f.name for f in resolved.features])

            if resolved is None:
                logger.error(f"Could not resolve {m_type} reference: {m_val}")

            self.morphemes.append({"type": m_type, "value": resolved})

        self.is_initialized = True
        logger.info(
            f"MorphemeSequence '{self.name}' initialized with {len(self.morphemes)} steps."
        )

    def get_sequence_fst(
        self, features: dict[str, str], stems: list[str | pynini.Fst] | None = None
    ) -> pynini.Fst:
        """
        Builds the sequence graph for a specific feature set by concatenating/composing
        sequence items. If `stems` is provided, it must contain one stem for each
        Lexicon or Paradigm step in the sequence.
        """
        if not self.is_initialized:
            self.initialize()

        # Merge fixed features and check for conflicts
        features = features.copy()
        for f, v in self.fixed_features.items():
            if f in features and features[f] != v and features[f] != "unmarked":
                raise ValueError(
                    f"Conflict for fixed feature {f}: sequence expects {v}, got {features[f]}"
                )
            features[f] = v

        # Initialize with empty string acceptor
        result_fst = pynini.accep("")
        stem_idx = 0

        for item in self.morphemes:
            m_type = item["type"]
            resolved = item["value"]

            if resolved is None:
                continue

            step_fst = None
            try:
                if m_type == "Lexicon":
                    assert isinstance(resolved, Lexicon)
                    if stems:
                        if stem_idx >= len(stems):
                            raise ValueError(
                                f"Not enough stems provided for Lexicon step {resolved.name}"
                            )
                        stem = stems[stem_idx]
                        stem_idx += 1
                        step_fst = self.fst_orchestrator._cast_fsalike_to_fsa(
                            stem, is_word=True
                        )
                    else:
                        step_fst = resolved.analyses_to_roots(features)
                elif m_type == "Paradigm":
                    assert isinstance(resolved, Paradigm)
                    if stems:
                        if stem_idx >= len(stems):
                            raise ValueError(
                                f"Not enough stems provided for Paradigm step {resolved.name}"
                            )
                        stem = stems[stem_idx]
                        stem_idx += 1
                        step_fst = resolved.inflect(stem, features)
                    else:
                        step_fst = resolved.get_subparadigm_inflect_graph(features)
                elif m_type == "MorphemeSet":
                    assert isinstance(resolved, MorphemeSet)
                    step_fst = resolved.analysis_to_morpheme(**features)
                elif m_type == "Pattern":
                    # resolved is pynini.Fst from fst_orchestrator.fsa()
                    step_fst = resolved
                elif m_type == "Rule":
                    # resolved is a function that takes an FST and returns an FST
                    assert callable(resolved)
                    result_fst = resolved(result_fst)
                    continue

                if step_fst is not None:
                    # skip if fst is empty (no paths)
                    if step_fst.start() == pynini.NO_STATE_ID:
                        logger.warning(
                            f"Step {m_type} {resolved} returned empty FST, skipping."
                        )
                        continue
                    result_fst.concat(step_fst)

            except KeyError as e:
                logger.warning(
                    f"Skipping step {m_type} {resolved} due to KeyError: {e}"
                )
                continue

        return result_fst.optimize()

    def inflect(
        self, stems: list[str | pynini.Fst], features: dict[str, str]
    ) -> pynini.Fst:
        """
        Inflect a sequence of stems according to the provided feature set.
        `stems` should be a list containing one stem (str or Fst) for each
        Lexicon or Paradigm step in the sequence.
        """
        return self.get_sequence_fst(features, stems=stems)

    def get_inflection_stages(
        self, stems: list[str | pynini.Fst], features: dict[str, str]
    ) -> list[dict[str, Any]]:
        """
        Get intermediate stages of inflection for a MorphemeSequence.
        """
        if not self.is_initialized:
            self.initialize()

        # Merge fixed features and check for conflicts
        features = features.copy()
        for f, v in self.fixed_features.items():
            if f in features and features[f] != v and features[f] != "unmarked":
                raise ValueError(
                    f"Conflict for fixed feature {f}: sequence expects {v}, got {features[f]}"
                )
            features[f] = v

        current_fst = pynini.accep("")
        stem_idx = 0
        stages = []

        # Initial stage
        stages.append(
            {
                "step": 0,
                "type": "START",
                # "value": "",
                "form": "",
                "fst": current_fst,
            }
        )

        for i, item in enumerate(self.morphemes):
            m_type = item["type"]
            resolved = item["value"]
            step_info = {"step": i + 1, "type": m_type}

            step_fst = None
            try:
                if m_type == "Lexicon":
                    assert isinstance(resolved, Lexicon)
                    stem = stems[stem_idx]
                    stem_idx += 1
                    step_fst = self.fst_orchestrator._cast_fsalike_to_fsa(
                        stem, is_word=True
                    )
                elif m_type == "Paradigm":
                    assert isinstance(resolved, Paradigm)
                    stem = stems[stem_idx]
                    stem_idx += 1
                    step_fst = resolved.inflect(stem, features)
                elif m_type == "MorphemeSet":
                    assert isinstance(resolved, MorphemeSet)
                    step_fst = resolved.analysis_to_morpheme(**features)
                elif m_type == "Pattern":
                    step_fst = resolved
                elif m_type == "Rule":
                    assert callable(resolved)
                    current_fst = resolved(current_fst)

                if step_fst is not None:
                    if step_fst.start() == pynini.NO_STATE_ID:
                        logger.warning(
                            f"Step {m_type} {resolved} returned empty FST, skipping."
                        )
                    else:
                        current_fst = current_fst + step_fst

            except KeyError as e:
                logger.warning(
                    f"Skipping step {m_type} {resolved} due to KeyError: {e}"
                )

            # Extract form string for the stage
            form = ""
            try:
                forms = self.fst_orchestrator.fsm_strings(current_fst)
                if forms:
                    form = forms[0]
            except Exception:
                form = "<ERROR>"

            stages.append({**step_info, "form": form, "fst": current_fst})

        stages.append(
            {
                "step": len(self.morphemes) + 1,
                "type": "FINAL",
                "form": self.fst_orchestrator.fsm_strings(
                    current_fst, strip_all_flags=True
                )[0],
            }
        )

        return stages

    def get_inflected_form(
        self, features: dict, stems: list[str] | None = None
    ) -> list[str]:
        """
        Generates inflected forms based on feature vector.
        """
        fst = self.get_sequence_fst(features, stems=stems)
        return self.fst_orchestrator.fsm_strings(fst)


class MorphemeSequenceRegistry(Registry):
    """
    Registry for MorphemeSequence objects.
    """

    def __init__(
        self,
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        fst_orchestrator: FstOrchestrator,
        morpheme_set_registry: MorphemeSetRegistry,
        data: dict[str, MorphemeSequence] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.morpheme_set_registry = morpheme_set_registry
        self.fst_orchestrator = fst_orchestrator
        super().__init__(
            kind="MorphemeSequence", data=data, config_objects=config_objects
        )

    def load_all_configs(self) -> dict[str, MorphemeSequence]:
        config_items: dict[str, MorphemeSequence] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate MorphemeSequence '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, MorphemeSequence]:
        sequence = MorphemeSequence.from_config(
            config=config,
            lexicon_registry=self.lexicon_registry,
            paradigm_registry=self.paradigm_registry,
            fst_orchestrator=self.fst_orchestrator,
            morpheme_set_registry=self.morpheme_set_registry,
        )
        return {sequence.name: sequence}

    def get_sequence(self, name: str) -> MorphemeSequence | None:
        return self.data.get(name)

    def initialize_sequences(self):
        for sequence in self.data.values():
            sequence.initialize()
