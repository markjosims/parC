"""
[Placeholder for now]
This file implements the `PartOfSpeech` and `Lexicon` classes
as well as the `LexiconRegistry` class, which is responsible for
storing and managing the lexicon for a given language.
"""

from dataclasses import dataclass, field
from typing import Tuple, List
from src.registry.registry_utils import Registry

@dataclass
class PartOfSpeech:
    """
    Object for representing a part of speech in the lexicon.
    """
    features: List[str] = field(default_factory=list)

@dataclass
class Lexicon:
    """
    Object for representing the lexicon for a given language.
    Stores a mapping from lemmas to their parts of speech and other
    relevant information (e.g. morphological features, etc.).
    """

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
        ...

    def __getitem__(self, part_of_speech_name: str) -> Tuple[PartOfSpeech, Lexicon]:
        """
        Get the `PartOfSpeech` and `Lexicon` objects for a given part of speech name.
        """
        ...