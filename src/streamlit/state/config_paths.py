"""
Fetches, validates and normalizes config directory path
"""

import streamlit as st
import dotenv
import os
from pathlib import Path
from src.constants import PROJECT_ROOT

# TODO: in the future, desired behavior is for the user to specify the config dir via
# a GUI and have that persist across sessions
# for now, loading from environment variable
dotenv.load_dotenv()
CONFIG_DIR = os.environ.get('CONFIG_DIR', './config')

def get_config_dir() -> str | None:
    config_dir_path = _validated_config_dir(CONFIG_DIR)
    return config_dir_path

def _validated_config_dir(config_dir: str | None) -> str | None:
    """
    Normalize config directory path and check if path exists.
    If not, throws error.
    """
    if config_dir is None:
        return None

    normalized = _normalize_config_dir(config_dir)
    if normalized is None:
        raise ValueError(f"Directory not found: {config_dir}")
    return str(normalized)

def _normalize_config_dir(config_dir: str) -> Path | None:
    """
    Normalizes config directory path by expanding tildes and setting
    path to absolute if not already (assume relative to project root).
    If path does not exist, return None (does not throw error).
    """
    if not config_dir.strip():
        return None
    raw_path = Path(config_dir).expanduser()
    if not raw_path.is_absolute():
        raw_path = Path(PROJECT_ROOT) / raw_path
    resolved = raw_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return None
    return resolved