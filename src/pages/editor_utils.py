from __future__ import annotations

import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

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
        self.data: dict = {}

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
        config_object = config_walker.config_data[self.config_key][filepath]
        self.data = self.build_state_from_config(config_object)
        self.path = filepath

    def new_file(self) -> None:
        """Reset to a blank state (no file loaded)."""
        self.clear_widget_keys()
        self.data = {}
        self.path = ""

    def save(self, dest_path: str | Path) -> None:
        """
        Sync form → model, serialize to YAML, and write to dest_path.
        Creates parent directories as needed.
        """
        self.read_form_to_state()
        yaml_doc = self.to_yaml()
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as f:
            yaml.dump(yaml_doc, f, allow_unicode=True, sort_keys=False)
