"""
Implements the MorphemeSequence class, which handles concatenative morphology
by sequencing Lexicons, Paradigms, Patterns, and Rules, and the MorphemeSequenceRegistry
class, which manages multiple MorphemeSequence configurations.
"""

from loguru import logger
import os
import itertools
import pynini
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.classes import Registry
from src.grammar.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.grammar.registry.paradigm_registry import ParadigmRegistry, Paradigm

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
        fst_orchestrator: FstOrchestrator,
        source_path: str | None = None,
    ):
        self.name = name
        self.sequence_data = sequence_data
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.fst_orchestrator = fst_orchestrator
        self.source_path = source_path
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
            fst_orchestrator=fst_orchestrator,
            source_path=source_path,
        )

    def to_dict(self) -> dict:
        return {
            "kind": "MorphemeSequence",
            "name": self.name,
            "data": self.sequence_data,
            "source_path": self.source_path,
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
                resolved = self.fst_orchestrator.get_rule(m_val)

            if resolved is None and m_type != "Pattern":
                logger.error(f"Could not resolve {m_type} reference: {m_val}")

            self.morphemes.append({"type": m_type, "value": resolved})

        self.is_initialized = True
        logger.info(
            f"MorphemeSequence '{self.name}' initialized with {len(self.morphemes)} steps."
        )

    def get_sequence_fst(self, features: dict[str, str]) -> pynini.Fst:
        """
        Builds the sequence graph for a specific feature set by concatenating/composing
        sequence items.
        """
        if not self.is_initialized:
            self.initialize()

        # Initialize with empty string acceptor
        result_fst = pynini.acceptor("")

        for item in self.morphemes:
            m_type = item["type"]
            resolved = item["value"]

            if resolved is None:
                continue

            if m_type == "Lexicon":
                assert isinstance(resolved, Lexicon)
                step_fst = resolved.roots_to_analyses(features)
                result_fst.concat(step_fst)
            elif m_type == "Paradigm":
                assert isinstance(resolved, Paradigm)
                step_fst = resolved.get_subparadigm_inflect_graph(features)
                result_fst.concat(step_fst)
            elif m_type == "Pattern":
                # resolved is pynini.Fst from fst_orchestrator.fsa()
                result_fst.concat(resolved)
            elif m_type == "Rule":
                # resolved is Rule object with .fst property
                # Rules are composed with ALL prior input
                result_fst = result_fst @ resolved.fst

        return result_fst.optimize()

    def get_inflected_form(self, features: dict) -> list[str]:
        """
        Generates inflected forms based on feature vector.
        Logic: Intersect features, collect compatible strings from each morpheme, concatenate.
        """
        # If features incomplete, we should theoretically expand to all combinations.
        # But for now, assume features passed are sufficient or 'unmarked' handles it.
        # User requested: "iterate over feature vectors in a for-loop and concatenating for each vector"
        
        fst = self.get_sequence_fst(features)
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
        data: dict[str, MorphemeSequence] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.fst_orchestrator = fst_orchestrator
        super().__init__(kind="MorphemeSequence", data=data, config_objects=config_objects)

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
            config,
            self.lexicon_registry,
            self.paradigm_registry,
            self.fst_orchestrator,
        )
        return {sequence.name: sequence}

    def get_sequence(self, name: str) -> MorphemeSequence | None:
        return self.data.get(name)
        
    def initialize_sequences(self):
        for sequence in self.data.values():
            sequence.initialize()
