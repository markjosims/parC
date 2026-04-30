"""
Streamlit Morpheme Set Editor
=============================
A UI for creating and editing morpheme set marker YAML configs.
"""

from __future__ import annotations

import uuid

import streamlit as st
import yaml

from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
    render_editor_toolbar,
)
from src.grammar.registry.morpheme_set_registry import MorphemeSet

_config_kind = "MorphemeSet"
_config_key = "morpheme_set_configs"

# Prefix constants
_FEATURE_LIST_PREFIX = "features-list-"
_ENTRY_VAL_PREFIX = "entry-val-"
_REMOVE_ENTRY_PREFIX = "remove-entry-"
_MORPHEME_VALUE_PREFIX = "morpheme-value-"

_WIDGET_PREFIXES: list[str] = [
    _FEATURE_LIST_PREFIX,
    _ENTRY_VAL_PREFIX,
    _REMOVE_ENTRY_PREFIX,
    _MORPHEME_VALUE_PREFIX,
]

_help_str = """
Morpheme set files define morphemes mapped to feature vectors.
- **Features**: Select the features that participate in these contingencies.
- **Morphemes**: Define the string of a given morpheme
"""


class MorphmeSetEditor(EditorBase):
    """
    Editor for MorphemeSet YAML configs.

    self.data keys:
        features       — list[str] (participating features)
        global_order   — str
        global_markers — list[Marker]
        entries        — list[dict] (uuid, features: dict[str, str], morpheme: list[Marker])
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:

        morphemes_raw = config_object.get("data", [])
        features_set = set()
        entries = []
        for entry_config in morphemes_raw:
            f_vec = entry_config.get("features", {})
            morpheme = entry_config.get("morpheme", "")
            features_set.update(f_vec.keys())
            entries.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "features": f_vec,
                    "morpheme": morpheme,
                }
            )

        return {
            "features": sorted(list(features_set)),
            "entries": entries,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        self.clear_errors()
        # 1. Top-level fields
        selected_features = st.session_state.get(
            self.get_widget_key(_FEATURE_LIST_PREFIX, "main"), []
        )
        if selected_features:
            self.data["features"] = selected_features

        # 3. Entries
        for entry in self.data["entries"]:
            uid = entry["uuid"]
            for f in self.data["features"]:
                val = self.get_node_widget(_ENTRY_VAL_PREFIX, uid, suffix=f)
                if val is not None:
                    entry["features"][f] = val.strip()

            morpheme_val = self.get_node_widget(_MORPHEME_VALUE_PREFIX, uid)
            if morpheme_val is not None:
                entry["morpheme"] = morpheme_val.strip()
                self.validate_pattern(entry["morpheme"], f"Morpheme '{entry['morpheme']}'")

    def to_yaml(self) -> dict:
        grammar = st.session_state.get("grammar")
        if grammar is None:
            st.error("Grammar not loaded. Cannot serialize morpheme set.")
            st.stop()
        
        feature_orchestrator = grammar.feature_orchestrator
        features_objs = {feature_orchestrator.get_feature(f) for f in self.data["features"]}
        
        feature_mappings = {}
        for entry in self.data["entries"]:
            # Only include participating features
            clean_vec = {
                k: v
                for k, v in entry["features"].items()
                if k in self.data["features"] and v and v != "unmarked"
            }
            if not clean_vec:
                continue

            vector = frozenset(clean_vec.items())
            feature_mappings[vector] = entry["morpheme"]

        ms = MorphemeSet(
            features=features_objs,
            feature_mappings=feature_mappings
        )
        return ms.to_dict()

    def get_default_data(self) -> dict:
        return {
            "features": [],
            "entries": [],
        }

    def insert_entry(self) -> None:
        self.data["entries"].append(
            {"uuid": str(uuid.uuid4()), "features": {}, "morpheme": ""}
        )

    def remove_entry(self, uid: str) -> None:
        self.data["entries"] = [e for e in self.data["entries"] if e["uuid"] != uid]


def _render_entry(
    entry: dict,
    features: list[str],
    editor: MorphmeSetEditor,
    features_to_values: dict[str, list[str]],
) -> None:
    uid = entry["uuid"]
    with st.container(border=True):
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            with cols[i]:
                f_vals = features_to_values.get(f, [])
                options = ["unmarked"] + sorted(f_vals)
                current_val = entry["features"].get(f, "unmarked")
                if current_val not in options:
                    options.append(current_val)

                st.selectbox(
                    f,
                    options=options,
                    index=options.index(current_val),
                    key=editor.get_widget_key(_ENTRY_VAL_PREFIX, uid, suffix=f),
                    label_visibility="collapsed" if len(features) > 1 else "visible",
                )
        with cols[-1]:
            if st.button(
                "✕",
                key=editor.get_widget_key(_REMOVE_ENTRY_PREFIX, uid),
                help="Delete entry",
            ):
                editor.remove_entry(uid)
                st.rerun()

        st.text_input(
            "Morpheme",
            key=editor.get_widget_key(_MORPHEME_VALUE_PREFIX, uid),
            value=entry["morpheme"],
        )


def morpheme_set_page() -> None:
    st.set_page_config(
        page_title="Morpheme Set Editor",
        page_icon="👯",
        layout="wide",
    )

    editor_sidebar(
        kind=_config_kind,
        editor_class=MorphmeSetEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    grammar = st.session_state.get("grammar")
    available_features = []
    features_to_values = {}
    if grammar:
        features_to_values = (
            grammar.feature_orchestrator.feature_values_registry.features_to_values
        )
        available_features = list(features_to_values.keys())

    # 1. Config section
    current_features = editor.data.get("features", [])
    with st.expander("Configuration", expanded=not bool(current_features)):
        st.multiselect(
            "Participating Features",
            options=available_features or current_features,
            default=current_features,
            key=editor.get_widget_key(_FEATURE_LIST_PREFIX, "main"),
            help="Features each morpheme expones.",
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries section
    features = editor.data.get("features", [])
    if not features:
        st.warning("Please select at least one participating feature above.")
    else:
        # Table Header
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            cols[i].markdown(f"**{f}**")

        for entry in editor.data["entries"]:
            _render_entry(entry, features, editor, features_to_values)

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add entry", add_callback=editor.insert_entry
        )


if __name__ == "__main__":
    morpheme_set_page()
