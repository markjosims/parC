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


def editor_guard(kind: ConfigKindType) -> EditorBase:
    """
    Check if an Editor instance is in session state;
    if not, show a prompt and stop execution.
    """

    # check if user just switched from a different page
    current_page = st.session_state.get("current_page", "unknown")
    if current_page != kind:
        st.session_state.pop("editor", None)
        st.session_state["current_page"] = kind

    editor = st.session_state.get("editor")

    if editor is None:
        st.info(
            "👈 Select a file in the sidebar and click **Open**, or open a **(new file)** to begin."
        )
        st.stop()
    return editor


def editor_sidebar(
    kind: str,
    editor_class: type[EditorBase],
    config_dir: str,
    config_walker: ConfigWalker,
    kind_files: list[str],
    help_str: str,
) -> None:
    """
    Render sidebar for the inventory page, including file selector and about info.
    """
    with st.sidebar:
        st.title("🔤 Inventory Editor")
        st.caption(f"`CONFIG_DIR`: `{config_dir}`")
        st.divider()

        st.subheader("Open file")
        file_options = [None] + kind_files
        file_indices = list(range(len(file_options)))

        kind_stems = [Path(f).stem for f in kind_files]
        file_display_options = ["(new file)"] + kind_stems

        if not kind_files:
            st.info(f"No {kind} files found.")

        selected_file_idx = st.selectbox(
            f"{kind} files",
            options=file_indices,
            format_func=lambda i: file_display_options[i],
            key="file_selector",
            label_visibility="collapsed",
        )
        selected_file = file_options[selected_file_idx]

        col_open, col_refresh = st.columns(2)
        with col_open:
            if st.button("Open", use_container_width=True, type="primary"):
                editor = editor_class()
                try:
                    if selected_file is None:
                        editor.new_file()
                    else:
                        editor.load_file(selected_file, config_walker)
                except (KeyError, ValueError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["editor"] = editor
                st.rerun()
        with col_refresh:
            if st.button(
                "↺ Refresh",
                use_container_width=True,
                help=f"Re-scan CONFIG_DIR for {kind} files",
            ):
                st.rerun()

        st.divider()
        st.subheader("About")
        st.markdown(help_str)


def editor_header(kind: ConfigKindType, editor: type[EditorBase]) -> None:
    """
    Render the page header, including the file name input field.
    The file name is stored in session state and used when saving the YAML file.
    """
    st.header(editor.stem or f"New {kind} file")

    col_name, _ = st.columns([3, 5])
    with col_name:
        st.text_input(
            "File name",
            key="file_name",
            value=editor.stem,
            placeholder="segments",
            help=f"Name for this {kind} file (no extension needed).",
        )
