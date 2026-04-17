"""
Streamlit Pattern Editor
========================
A UI for creating and editing pattern YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Patterns are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run src/streamlit/app.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.pattern_registry import Pattern, PatternRegistry
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.pages.editor_utils import EditorBase

_config_kind = "Patterns"
_config_key = "pattern_configs"

_NODE_PREFIXES = ("name-", "ref-", "pattern_text-", "test_includes-", "test_excludes-")


"""
PatternEditor
"""


class PatternEditor(EditorBase):
    """
    Editor for Patterns YAML configs.

    self.data keys:
        patterns     — list[Pattern] in topological display order
        id_map       — dict[uuid, Pattern] for stable widget keying
        test_results — dict[uuid, Any] populated by run_tests()
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    # ------------------------------------------------------------------
    # EditorBase abstract methods
    # ------------------------------------------------------------------

    def build_state_from_config(self, config_object: dict) -> dict:
        filepath = config_object["source_path"]
        registry = PatternRegistry(config_objects={filepath: config_object})
        # patterns_sorted gives topological order (dependencies first)
        id_map: dict[str, Pattern] = {uuid4().hex: p for p in registry.patterns_sorted}
        return {
            "patterns": list(id_map.values()),
            "id_map": id_map,
            "test_results": {},
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into Pattern objects.
        Clears cached test results for any pattern whose ref or value changed.
        """
        id_map: dict[str, Pattern] = self.data.get("id_map", {})
        test_results: dict[str, Any] = self.data.get("test_results", {})

        for uid, pattern in id_map.items():
            old_ref = pattern._ref
            old_value = pattern.value

            name_val = st.session_state.get(f"name-{uid}")
            ref_val = st.session_state.get(f"ref-{uid}")
            pattern_val = st.session_state.get(f"pattern_text-{uid}")
            includes_val = st.session_state.get(f"test_includes-{uid}")
            excludes_val = st.session_state.get(f"test_excludes-{uid}")

            if name_val is not None:
                pattern.name = name_val
            if ref_val is not None:
                pattern._ref = ref_val
            if pattern_val is not None:
                pattern.value = pattern_val
            if includes_val is not None:
                pattern.test_includes = [
                    s.strip() for s in includes_val.split(",") if s.strip()
                ]
            if excludes_val is not None:
                pattern.test_excludes = [
                    s.strip() for s in excludes_val.split(",") if s.strip()
                ]

            # invalidate cached test results if the pattern definition changed
            if pattern._ref != old_ref or pattern.value != old_value:
                test_results.pop(uid, None)

    def to_yaml(self) -> dict:
        patterns: list[Pattern] = self.data.get("patterns", [])
        return {
            "kind": self.kind,
            "patterns": [p.to_dict() for p in patterns],
        }

    def clear_widget_keys(self) -> None:
        id_map: dict[str, Pattern] = self.data.get("id_map", {})
        for uid in list(id_map.keys()):
            for prefix in _NODE_PREFIXES:
                st.session_state.pop(f"{prefix}{uid}", None)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert_pattern(self) -> str:
        """Append a blank pattern at the bottom; return its uuid."""
        new_pattern = Pattern(name="", value="", _ref="<new_ref>")
        uid = uuid4().hex
        self.data["id_map"][uid] = new_pattern
        self.data["patterns"].append(new_pattern)
        return uid

    def remove_pattern(self, uid: str) -> Pattern:
        """Remove pattern by uuid, clear its widget keys."""
        pattern = self.data["id_map"].pop(uid)
        self.data["patterns"].remove(pattern)
        self.data["test_results"].pop(uid, None)
        for prefix in _NODE_PREFIXES:
            st.session_state.pop(f"{prefix}{uid}", None)
        return pattern

    def run_tests(self, uid: str, grammar: Any) -> None:
        """
        Run include/exclude tests for the pattern identified by uid.
        Requires a loaded Grammar instance. Results are stored in
        self.data["test_results"][uid].
        """
        pattern = self.data["id_map"][uid]
        fst_orch: FstOrchestrator = grammar.fst_orchestrator
        results = fst_orch.test_pattern(
            pattern._ref,
            pattern.test_includes,
            pattern.test_excludes,
        )
        self.data["test_results"][uid] = results


"""
Pattern rendering
"""


def _render_pattern(uid: str, editor: PatternEditor) -> None:
    """Render a single pattern entry as an expandable card."""
    pattern = editor.data["id_map"][uid]
    test_results = editor.data["test_results"].get(uid)

    ref_label = pattern._ref or "(ref not set)"
    name_label = pattern.name or "(unnamed)"

    with st.expander(f"{name_label} `{ref_label}`", expanded=False):
        col_name, col_ref = st.columns(2)
        with col_name:
            st.text_input(
                "Pattern name",
                key=f"name-{uid}",
                value=pattern.name,
                placeholder="Front vowel",
            )
        with col_ref:
            st.text_input(
                "Reference",
                key=f"ref-{uid}",
                value=pattern._ref,
                placeholder="<V_Front>",
            )

        st.text_input(
            "Pattern",
            key=f"pattern_text-{uid}",
            value=pattern.value,
            placeholder="(<e>|<i>|<ɛ>)",
            help="Regular expression string interpreted as an FSA.",
        )

        col_inc, col_exc = st.columns(2)
        with col_inc:
            st.text_input(
                "Test includes",
                key=f"test_includes-{uid}",
                value=", ".join(pattern.test_includes),
                placeholder="e, i, ɛ",
                help="Comma-separated strings the pattern should accept.",
            )
        with col_exc:
            st.text_input(
                "Test excludes",
                key=f"test_excludes-{uid}",
                value=", ".join(pattern.test_excludes),
                placeholder="a, o, u",
                help="Comma-separated strings the pattern should reject.",
            )

        col_test, col_remove = st.columns(2)
        with col_test:
            if st.button("▶ Run tests", key=f"test-{uid}", use_container_width=True):
                grammar = st.session_state.get("grammar")
                if grammar is None:
                    st.warning("Grammar not loaded — cannot run tests.")
                else:
                    editor.read_form_to_state()
                    editor.run_tests(uid, grammar)
                    st.rerun()
        with col_remove:
            if st.button(
                "✕ Delete", key=f"remove-{uid}", use_container_width=True
            ):
                editor.remove_pattern(uid)
                st.rerun()

        # Test results
        if test_results is not None:
            results_list = test_results.get("results", [])
            all_pass = test_results.get("all_pass", False)
            if results_list:
                st.divider()
                badges = st.columns(len(results_list))
                for col, r in zip(badges, results_list):
                    icon = "✅" if r["pass"] else "❌"
                    col.markdown(
                        f"{icon} `{r['string']}`",
                        help=f"Type: {r.get('type', '?')}",
                    )
                if all_pass:
                    st.success("All tests pass")
                else:
                    st.error("Some tests failed")


"""
Page function
"""


def patterns_page() -> None:
    st.set_page_config(
        page_title="Pattern Editor",
        page_icon="🔣",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    pattern_files = config_walker.config_filemap[_config_key]

    # Sidebar: file picker
    with st.sidebar:
        st.title("🔣 Pattern Editor")
        st.caption(f"`CONFIG_DIR`: `{config_dir}`")
        st.divider()

        st.subheader("Open file")
        file_options = [None] + pattern_files
        file_indices = list(range(len(file_options)))
        pattern_stems = [Path(f).stem for f in pattern_files]
        file_display_options = ["(new file)"] + pattern_stems

        if not pattern_files:
            st.info("No pattern files found.")

        selected_file_idx = st.selectbox(
            "Pattern files",
            options=file_indices,
            format_func=lambda i: file_display_options[i],
            key="file_selector",
            label_visibility="collapsed",
        )
        selected_file = file_options[selected_file_idx]

        col_open, col_refresh = st.columns(2)
        with col_open:
            if st.button("Open", use_container_width=True, type="primary"):
                editor = PatternEditor()
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
                help="Re-scan CONFIG_DIR for pattern files",
            ):
                st.rerun()

        st.divider()
        st.subheader("About")
        st.markdown(
            "Pattern files define FSA shorthands used in morphological rules. "
            "Each entry has a **reference** (e.g. `<V_Front>`) and a **pattern** "
            "string (a regex-like expression over inventory refs). "
            "Patterns are displayed in dependency order."
        )

    # Guard: no state yet
    editor: PatternEditor | None = st.session_state.get("editor")
    if editor is None:
        st.info(
            "👈 Select a file in the sidebar and click **Open**, "
            "or open a **(new file)** to begin."
        )
        st.stop()

    # Header
    st.header(editor.stem or "New patterns file")

    col_name, col_spacer = st.columns([3, 5])
    with col_name:
        st.text_input(
            "File name",
            key="file_name",
            value=editor.stem,
            placeholder="vowel_classes",
            help="Name for this patterns file (no extension needed).",
        )

    # Toolbar
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add pattern", use_container_width=True):
            editor.insert_pattern()
            st.rerun()

    with col_save:
        if st.button("💾 Save YAML", use_container_width=True, type="primary"):
            stem = st.session_state.get("file_name", "").strip()
            if not stem:
                st.error("Enter a file name before saving.")
            else:
                try:
                    editor.save(stem)
                    st.toast(f"✅ Saved as `{stem}`", icon="✅")
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    with col_preview_toggle:
        show_preview = st.toggle("Show YAML preview", value=False)

    if show_preview:
        editor.read_form_to_state()
        import yaml as _yaml
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(
                _yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False)
            )

    st.divider()

    # Pattern list
    id_map = editor.data.get("id_map", {})
    if not id_map:
        st.info(
            "No patterns yet. Click **➕ Add pattern** to start — "
            "for example a `Front vowel` or `Syllable` pattern."
        )
    else:
        for uid in id_map:
            _render_pattern(uid, editor)


if __name__ == "__main__":
    patterns_page()
