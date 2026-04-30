"""
Streamlit Morpheme Sequence Editor
==================================
A UI for creating and editing MorphemeSequence YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
import yaml
from pathlib import Path

from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
    render_editor_toolbar,
)

_config_kind = "MorphemeSequence"
_config_key = "morpheme_sequence_configs"

# Prefix constants
_STEP_TYPE_PREFIX = "step-type-"
_STEP_VAL_PREFIX = "step-val-"
_REMOVE_STEP_PREFIX = "remove-step-"
_MOVE_UP_PREFIX = "move-up-"
_MOVE_DOWN_PREFIX = "move-down-"

_WIDGET_PREFIXES: list[str] = [
    _STEP_TYPE_PREFIX,
    _STEP_VAL_PREFIX,
    _REMOVE_STEP_PREFIX,
    _MOVE_UP_PREFIX,
    _MOVE_DOWN_PREFIX,
]

_MORPHEME_TYPES = ["Lexicon", "Paradigm", "Pattern", "Rule"]

_help_str = """
Morpheme Sequence files define a sequence of morphemes (Lexicons, Paradigms, Patterns, or Rules)
to be concatenated or composed to form fully inflected words.
"""

class MorphemeSequenceEditor(EditorBase):
    """
    Editor for MorphemeSequence YAML configs.

    self.data keys:
        steps — list[dict] (uuid, type, value)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        raw_data = config_object.get("data", [])
        steps = []
        for step in raw_data:
            steps.append({
                "uuid": str(uuid.uuid4()),
                "type": step.get("type", "Lexicon"),
                "value": step.get("value", ""),
            })
        return {
            "steps": steps,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        for step in self.data["steps"]:
            uid = step["uuid"]
            s_type = self.get_node_widget(_STEP_TYPE_PREFIX, uid)
            s_val = self.get_node_widget(_STEP_VAL_PREFIX, uid)
            if s_type is not None:
                step["type"] = s_type
            if s_val is not None:
                step["value"] = s_val

    def to_yaml(self) -> dict:
        output_data = []
        for step in self.data["steps"]:
            output_data.append({
                "type": step["type"],
                "value": step["value"],
            })
        return {
            "kind": self.kind,
            "data": output_data,
        }

    def get_default_data(self) -> dict:
        return {
            "steps": [],
        }

    def insert_step(self) -> None:
        self.data["steps"].append({
            "uuid": str(uuid.uuid4()),
            "type": "Lexicon",
            "value": "",
        })

    def remove_step(self, uid: str) -> None:
        self.data["steps"] = [s for s in self.data["steps"] if s["uuid"] != uid]

    def move_step(self, uid: str, direction: str) -> None:
        steps = self.data["steps"]
        idx = next((i for i, s in enumerate(steps) if s["uuid"] == uid), -1)
        if idx == -1:
            return
        
        new_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= new_idx < len(steps):
            steps[idx], steps[new_idx] = steps[new_idx], steps[idx]


def _render_step(
    step: dict, 
    editor: MorphemeSequenceEditor, 
    available_lexicons: list[str],
    available_paradigms: list[str],
    available_patterns: list[str],
    available_rules: list[str],
    index: int,
    total: int
) -> None:
    uid = step["uuid"]
    with st.container(border=True):
        col_type, col_val, col_move, col_del = st.columns([1.5, 4, 0.8, 0.4])
        
        with col_type:
            st.selectbox(
                "Type",
                options=_MORPHEME_TYPES,
                index=_MORPHEME_TYPES.index(step["type"]) if step["type"] in _MORPHEME_TYPES else 0,
                key=editor.get_widget_key(_STEP_TYPE_PREFIX, uid),
                label_visibility="collapsed",
            )
            
        with col_val:
            s_type = step["type"]
            options = []
            if s_type == "Lexicon":
                options = available_lexicons
            elif s_type == "Paradigm":
                options = available_paradigms
            elif s_type == "Pattern":
                options = available_patterns
            elif s_type == "Rule":
                options = available_rules
            
            # Pattern can be inline, so allow text input if not in options
            if s_type == "Pattern" and step["value"] and not step["value"].startswith("$") and step["value"] not in options:
                 st.text_input(
                    "Value",
                    value=step["value"],
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )
            elif options:
                # Add current value to options if it's a ref but missing (maybe deleted or wrong kind)
                current_val = step["value"]
                all_opts = [""] + options
                if current_val and current_val not in all_opts:
                    all_opts.append(current_val)
                    
                st.selectbox(
                    "Value",
                    options=all_opts,
                    index=all_opts.index(current_val) if current_val in all_opts else 0,
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )
            else:
                st.text_input(
                    "Value",
                    value=step["value"],
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                    placeholder="Reference ($name) or inline pattern"
                )

        with col_move:
            m_up, m_down = st.columns(2)
            if m_up.button("↑", key=editor.get_widget_key(_MOVE_UP_PREFIX, uid), disabled=(index == 0)):
                editor.move_step(uid, "up")
                st.rerun()
            if m_down.button("↓", key=editor.get_widget_key(_MOVE_DOWN_PREFIX, uid), disabled=(index == total - 1)):
                editor.move_step(uid, "down")
                st.rerun()

        with col_del:
            if st.button("✕", key=editor.get_widget_key(_REMOVE_STEP_PREFIX, uid), help="Remove step"):
                editor.remove_step(uid)
                st.rerun()

def morpheme_sequence_page() -> None:
    st.set_page_config(
        page_title="Morpheme Sequence Editor",
        page_icon="🔗",
        layout="wide",
    )

    editor_sidebar(
        kind=_config_kind,
        editor_class=MorphemeSequenceEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    grammar = st.session_state.get("grammar")
    available_lexicons = []
    available_paradigms = []
    available_patterns = []
    available_rules = []
    
    if grammar:
        available_lexicons = sorted(["$" + name for name in grammar.lexicon_registry.data.keys()])
        available_paradigms = sorted(["$" + name for name in grammar.paradigm_registry.data.keys()])
        available_patterns = sorted(["$" + name for name in grammar.fst_orchestrator.pattern_registry.data.keys()])
        available_rules = sorted(["$" + name for name in grammar.fst_orchestrator.rule_registry.data.keys()])

    toolbar_placeholder = st.empty()
    st.divider()

    # 1. Sequence Editor
    st.subheader("Sequence Steps")
    steps = editor.data.get("steps", [])
    if not steps:
        st.info("No steps yet. Click **➕ Add step** to start.")
    else:
        # Header for columns
        h1, h2, h3, h4 = st.columns([1.5, 4, 0.8, 0.4])
        h1.markdown("**Type**")
        h2.markdown("**Value (Reference or Inline Pattern)**")
        h3.markdown("**Move**")
        
        for i, step in enumerate(steps):
            _render_step(
                step, 
                editor, 
                available_lexicons, 
                available_paradigms, 
                available_patterns, 
                available_rules,
                i,
                len(steps)
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(editor, add_label="Add step", add_callback=editor.insert_step)

    # 2. Inflection Tester (read-only based on current state)
    st.divider()
    st.subheader("Inflection Tester")
    
    # Try to resolve sequence from current data if it exists in registry, 
    # but registry might be stale. For immediate feedback, we might need a 
    # way to initialize a temporary sequence object.
    # For now, if saved, use grammar's sequence.
    
    if editor.path and grammar:
        seq_name = editor.stem
        sequence = grammar.morpheme_sequence_registry.get_sequence(seq_name)
        
        if sequence:
            if not sequence.is_initialized:
                sequence.initialize()
                
            all_features = sorted(list(sequence.features))
            features = {}
            if all_features:
                st.caption("Enter feature values to test inflection:")
                cols = st.columns(3)
                for i, feat_name in enumerate(all_features):
                    col = cols[i % 3]
                    val = col.text_input(f"{feat_name}", key=f"test-feat-{feat_name}")
                    if val:
                        features[feat_name] = val
            
            if st.button("Generate Forms"):
                try:
                    with st.spinner("Generating..."):
                        forms = sequence.get_inflected_form(features)
                    if not forms:
                        st.warning("No forms generated.")
                    else:
                        st.success(f"Generated {len(forms)} forms:")
                        st.write(", ".join(forms))
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("Save sequence to enable inflection tester.")
    else:
        st.info("Open an existing file to enable inflection tester.")

if __name__ == "__main__":
    morpheme_sequence_page()
