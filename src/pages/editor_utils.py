from __future__ import annotations

import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st
from camel_converter import to_snake

from src.config_utils.schema_validation import ConfigKindType

if TYPE_CHECKING:
    from src.config_utils.config_walker import ConfigWalker


class EditorBase(ABC):
    """
    Abstract base class for YAML config editors.

    Subclasses implement the four abstract methods to handle the
    editor-specific data model.  The base provides concrete load/save
    orchestration that delegates to those methods.

    Instances are stored directly in st.session_state["editor"].
    """

    def __init__(self, kind: ConfigKindType, config_key: str) -> None:
        """
        Args:
            kind:       The config kind string, e.g. "Inventory".
            config_key: The key used in ConfigWalker.config_data,
                        e.g. "inventory_configs".
        """
        self.kind = kind
        self.config_key = config_key
        self.path: str = ""
        self.config_dir: str = ""
        self.data: dict = {}

    @property
    def subdir(self) -> str:
        """Subdirectory name for this kind, derived via to_snake(kind)."""
        return to_snake(self.kind)

    @property
    def stem(self) -> str:
        """Filename stem of the loaded file, or '' for new files."""
        return Path(self.path).stem if self.path else ""

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def build_state_from_config(self, config_object: dict) -> dict:
        """
        Parse a raw config dict (as returned by ConfigWalker) into the
        editor's working data dict.  Use backend Registry classes here;
        do not re-parse YAML manually.

        Returns the new value for self.data.
        """

    @abstractmethod
    def read_form_to_state(self) -> None:
        """
        Pull widget values from st.session_state back into model objects
        in self.data.  Called by save() before serialization.
        """

    @abstractmethod
    def to_yaml(self) -> dict:
        """
        Serialize self.data to a YAML-serializable dict (the full
        document, including top-level 'kind' and 'data' keys).
        Delegate to model .to_dict() methods where possible.
        """

    @abstractmethod
    def clear_widget_keys(self) -> None:
        """
        Remove all Streamlit widget keys owned by this editor from
        st.session_state.  Called before loading a new file to prevent
        stale key conflicts.
        """

    # ------------------------------------------------------------------
    # Concrete lifecycle helpers
    # ------------------------------------------------------------------

    def load_file(self, filepath: str, config_walker: "ConfigWalker") -> None:
        """Clear widget state, then load and parse the given file."""
        self.clear_widget_keys()
        self.config_dir = str(config_walker.config_dir)
        config_object = config_walker.config_data[self.config_key][filepath]
        self.data = self.build_state_from_config(config_object)
        self.path = filepath

    def new_file(self) -> None:
        """Reset to a blank state (no file loaded)."""
        self.clear_widget_keys()
        self.data = {}
        self.path = ""

    def resolve_save_path(self, stem: str) -> Path:
        """Build the full save path: config_dir / subdir / stem.yaml."""
        if not stem:
            raise ValueError("File name cannot be empty.")
        if not self.config_dir:
            raise ValueError("No config directory set — open a file first.")
        return Path(self.config_dir) / self.subdir / f"{stem}.yaml"

    def save(self, stem: str) -> None:
        """
        Sync form → model, serialize to YAML, and write to the kind's subdirectory.
        Updates self.path to the written location.
        """
        dest = self.resolve_save_path(stem)
        self.read_form_to_state()
        yaml_doc = self.to_yaml()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as f:
            yaml.dump(yaml_doc, f, allow_unicode=True, sort_keys=False)
        self.path = str(dest)
