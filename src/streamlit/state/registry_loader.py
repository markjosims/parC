"""
Loads state for grammar registry.
TODO: no real logic here, but eventually it would be useful
to implement fragmented updating so that the, rather than rebuilding
the entire registry, we only rebuild components that have been updated.
"""

from pathlib import Path
from src.registry.grammar_registry import GrammarRegistry

def load_registry(config_dir: Path):
    reg = GrammarRegistry.from_config_dir(str(config_dir))
    return reg