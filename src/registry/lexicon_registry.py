"""
[Placeholder for now]
This file implements the `PartOfSpeech` and `Lexicon` classes
as well as the `LexiconRegistry` class, which is responsible for
storing and managing the lexicon for a given language.
"""

from dataclasses import dataclass, field
from typing import Tuple, List
from src.registry.registry_utils import Registry
from src.registry.feature_registry import Feature, FeatureRegistry
import pandas as pd

@dataclass
class PartOfSpeech:
    """
    Object for representing a part of speech in the lexicon.
    """
    features: List[Feature] = field(default_factory=list)
    invariant_features: List[Feature] = field(default_factory=list)
    lexical_flags: List[str] = field(default_factory=list)
    principal_parts: List[str] = field(default_factory=list)

@dataclass
class Lexicon:
    """
    Object for representing the lexicon for a given language.
    Essentially a wrapper around a `PartOfSpeech` object and
    a `pandas.DataFrame` containing the lexicon entries for that
    part of speech, performing validation between the columns of
    the dataframe and those expected by the `PartOfSpeech` object.
    """
    part_of_speech: PartOfSpeech
    entries: pd.DataFrame

    def __post_init__(self):
        # Validate that the columns of the entries dataframe match the expected features
        expected_columns = self.part_of_speech.lexical_flags + self.part_of_speech.principal_parts
        actual_columns = set(self.entries.columns)
        if not expected_columns.issubset(actual_columns):
            missing_columns = expected_columns - actual_columns
            raise ValueError(f"Missing columns in entries dataframe: {missing_columns}")
        
@dataclass
class LexiconRegistry:
    """
    Object for storing and managing `Lexicon` and `PartOfSpeech` objects
    for a given language.
    """

    @classmethod
    def from_config_dir(cls, config_dir: str) -> "LexiconRegistry":
        """
        Factory method for creating a `LexiconRegistry` from a configuration directory.
        """
        # TODO: read every PartOfSpeech config and the corresponding CSV
        # how to link the two? maybe the config file can specify the name of the CSV file?

    def __getitem__(self, part_of_speech_name: str) -> Tuple[PartOfSpeech, Lexicon]:
        """
        Get the `PartOfSpeech` and `Lexicon` objects for a given part of speech name.
        """
        ...