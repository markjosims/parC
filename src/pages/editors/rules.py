"""
Streamlit Rules Editor
======================
A UI for creating and editing rule YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Rules are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run src/streamlit/app.py
"""

from __future__ import annotations

from typing import Any, Literal

import streamlit as st

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.rule_registry import Rule, RuleRegistry
from src.fst_utils import Acceptor
from src.pages.editors.editor_base import (
    EditorBase,
    editor_guard,
    editor_sidebar,
    editor_header,
    render_editor_toolbar,
)
from src.fst_utils import Acceptor
from src.grammar import Grammar

_config_kind = "Rules"
_config_key = "rule_configs"

_NAME_PREFIX = "name-"
_TYPE_PREFIX = "type-"
_DESC_PREFIX = "desc-"
_INPUT_PREFIX = "input-"
_OUTPUT_PREFIX = "output-"
_LEFT_CTX_PREFIX = "left_ctx-"
_RIGHT_CTX_PREFIX = "right_ctx-"
_DIRECTION_PREFIX = "direction-"
_STRING_MAP_PREFIX = "string_map-"
_RULE_SEQ_PREFIX = "rule_seq-"
_TEST_MAPPINGS_PREFIX = "test_mappings-"
_TEST_BUTTON_PREFIX = "test_button-"
_REMOVE_PREFIX = "remove-"
_CHANGE_TYPE_PREFIX = "change-type-"

_WIDGET_PREFIXES: list[str] = [
    _NAME_PREFIX,
    _TYPE_PREFIX,
    _DESC_PREFIX,
    _INPUT_PREFIX,
    _OUTPUT_PREFIX,
    _LEFT_CTX_PREFIX,
    _RIGHT_CTX_PREFIX,
    _DIRECTION_PREFIX,
    _STRING_MAP_PREFIX,
    _RULE_SEQ_PREFIX,
    _TEST_MAPPINGS_PREFIX,
    _TEST_BUTTON_PREFIX,
    _REMOVE_PREFIX,
    _CHANGE_TYPE_PREFIX,
]

_RULE_TYPES = ["simple_rule", "string_map", "rule_sequence"]
_DIRECTIONS = ["ltr", "rtl", "sim"]

_help_str = """
Rule files define phonological rewrite rules applied by the FST parser.
Each entry is one of:
- **Simple rule**: input/output pattern pair with optional left/right context.
- **String map**: explicit list of `input => output` pairs.
- **Rule sequence**: ordered chain of other rules applied in sequence.
"""

"""
RulesEditor
"""


class RulesEditor(EditorBase):
    """
    Editor for Rules YAML configs.

    self.data keys:
        rules        — list[Rule] in topological display order
        id_map       — dict[uuid, Rule]
        test_results — dict[uuid, Any] populated by run_tests()
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    # ------------------------------------------------------------------
    # EditorBase abstract methods
    # ------------------------------------------------------------------

    def build_state_from_config(self, config_object: dict) -> dict:
        rule_configs = config_object["rules"]
        rules = [Rule.from_config(config) for config in rule_configs]
        id_map: dict[str, Rule] = {r.uuid: r for r in rules}
        return {
            "rules": list(id_map.values()),
            "id_map": id_map,
            "test_results": {},
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into Rule objects.
        Clears cached test results for any rule whose definition changed.
        """
        self.clear_errors()
        id_map: dict[str, Rule] = self.data.get("id_map", {})
        test_results: dict[str, Any] = self.data.get("test_results", {})

        for uid, rule in id_map.items():
            old_ref = rule._ref

            name_val = self.get_node_widget(_NAME_PREFIX, uid)
            desc_val = self.get_node_widget(_DESC_PREFIX, uid)

            if name_val is not None:
                rule._ref = name_val
                rule.value = name_val
            if desc_val is not None:
                rule.description = desc_val or None

            if rule.type == "simple_rule":
                inp = self.get_node_widget(_INPUT_PREFIX, uid)
                out = self.get_node_widget(_OUTPUT_PREFIX, uid)
                left = self.get_node_widget(_LEFT_CTX_PREFIX, uid)
                right = self.get_node_widget(_RIGHT_CTX_PREFIX, uid)
                direction = self.get_node_widget(_DIRECTION_PREFIX, uid)
                if inp is not None:
                    self.validate_acceptor(inp, f"Input Pattern for '{rule._ref}'")
                    rule.input_pattern.value = inp
                if out is not None:
                    self.validate_acceptor(out, f"Output Pattern for '{rule._ref}'")
                    rule.output_pattern.value = out
                if left is not None:
                    self.validate_acceptor(left, f"Left Context for '{rule._ref}'")
                    rule.left_context.value = left
                if right is not None:
                    self.validate_acceptor(right, f"Right Context for '{rule._ref}'")
                    rule.right_context.value = right
                if direction is not None:
                    rule.direction = direction

            elif rule.type == "string_map":
                left = self.get_node_widget(_LEFT_CTX_PREFIX, uid)
                right = self.get_node_widget(_RIGHT_CTX_PREFIX, uid)
                direction = self.get_node_widget(_DIRECTION_PREFIX, uid)
                
                pairs = []
                i = 0
                while True:
                    in_key = f"{_STRING_MAP_PREFIX}in-{i}-"
                    out_key = f"{_STRING_MAP_PREFIX}out-{i}-"
                    in_val = self.get_node_widget(in_key, uid)
                    out_val = self.get_node_widget(out_key, uid)
                    if in_val is None or out_val is None:
                        break
                    
                    self.validate_acceptor(in_val, f"String Map Input (Line {i + 1}) for '{rule._ref}'")
                    self.validate_acceptor(out_val, f"String Map Output (Line {i + 1}) for '{rule._ref}'")
                    pairs.append((Acceptor(in_val), Acceptor(out_val)))
                    i += 1
                
                if i > 0 or not rule.string_map:
                    rule.string_map = pairs

                if left is not None:
                    self.validate_acceptor(left, f"Left Context for '{rule._ref}'")
                    rule.left_context.value = left
                if right is not None:
                    self.validate_acceptor(right, f"Right Context for '{rule._ref}'")
                    rule.right_context.value = right
                if direction is not None:
                    rule.direction = direction

            elif rule.type == "rule_sequence":
                ref_map = {r._ref: r for r in id_map.values() if r._ref}
                seq = []
                i = 0
                while True:
                    key = self.get_widget_key(f"{_RULE_SEQ_PREFIX}{i}-", uid)
                    if key in st.session_state:
                        ref_name = st.session_state[key]
                        if ref_name in ref_map:
                            seq.append(ref_map[ref_name])
                        i += 1
                    else:
                        break
                if i > 0 or not rule.rule_sequence:
                    rule.rule_sequence = seq

            raw_mappings = []
            i = 0
            while True:
                in_key = f"{_TEST_MAPPINGS_PREFIX}in-{i}-"
                out_key = f"{_TEST_MAPPINGS_PREFIX}out-{i}-"
                in_val = self.get_node_widget(in_key, uid)
                out_val = self.get_node_widget(out_key, uid)
                if in_val is None or out_val is None:
                    break
                raw_mappings.append([in_val, out_val])
                i += 1
            
            if i > 0 or not rule.test_mappings:
                rule.test_mappings = raw_mappings

            if rule._ref != old_ref:
                test_results.pop(uid, None)

            self.validate_rule(rule)

    def to_yaml(self) -> dict:
        rules: list[Rule] = self.data.get("rules", [])
        registry = RuleRegistry(data={r._ref: r for r in rules})
        return registry.to_dict()

    def get_default_data(self) -> dict:
        return {
            "rules": [],
            "id_map": {},
            "test_results": {},
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert_rule(
        self,
        rule_type: Literal[
            "simple_rule", "string_map", "rule_sequence"
        ] = "simple_rule",
    ) -> str:
        """Append a blank rule; return its uuid."""

        if rule_type == "simple_rule":
            new_rule = Rule(
                _ref="new_rule",
                type="simple_rule",
                input_pattern=Acceptor(""),
                output_pattern=Acceptor(""),
            )
        elif rule_type == "string_map":
            new_rule = Rule(
                _ref="new_rule",
                type="string_map",
                string_map=[(Acceptor("a"), Acceptor("b"))],
            )
        else:
            new_rule = Rule(
                _ref="new_rule",
                type="rule_sequence",
                rule_sequence=[],
            )

        self.data["id_map"][new_rule.uuid] = new_rule
        self.data["rules"].append(new_rule)
        return new_rule.uuid

    def remove_rule(self, uid: str) -> Rule:
        """Remove rule by uuid, clear its widget keys."""
        rule = self.data["id_map"].pop(uid)
        self.data["rules"].remove(rule)
        self.data["test_results"].pop(uid, None)
        for prefix in _WIDGET_PREFIXES:
            st.session_state.pop(f"{prefix}{uid}", None)
        return rule

    def change_rule_type(
        self,
        uid: str,
        new_type: Literal["simple_rule", "string_map", "rule_sequence"],
    ) -> None:
        """Change a rule's type and reset fields that are specific to the old type."""

        rule = self.data["id_map"].get(uid)
        if rule is None:
            raise ValueError(f"Rule {uid!r} does not exist.")

        if rule.type == new_type:
            return

        rule.type = new_type

        # Reset all type-specific state so the new form starts clean.
        rule.input_pattern = Acceptor("")
        rule.output_pattern = Acceptor("")
        rule.string_map = []
        rule.rule_sequence = []
        rule.left_context = Acceptor("")
        rule.right_context = Acceptor("")
        rule.direction = "ltr"
        rule.test_mappings = []
        self.data["test_results"].pop(uid, None)

        if new_type == "simple_rule":
            rule.input_pattern = Acceptor("")
            rule.output_pattern = Acceptor("")
        elif new_type == "string_map":
            rule.string_map = [(Acceptor("a"), Acceptor("b"))]
        elif new_type == "rule_sequence":
            rule.rule_sequence = []

        for prefix in (
            _INPUT_PREFIX,
            _OUTPUT_PREFIX,
            _LEFT_CTX_PREFIX,
            _RIGHT_CTX_PREFIX,
            _DIRECTION_PREFIX,
            _STRING_MAP_PREFIX,
            _RULE_SEQ_PREFIX,
            _TEST_MAPPINGS_PREFIX,
            _TEST_BUTTON_PREFIX,
        ):
            st.session_state.pop(editor_key := self.get_widget_key(prefix, uid), None)

    def add_string_map_pair(self, uid: str) -> None:
        """Add a blank pair to a string_map."""
        rule = self.data["id_map"].get(uid)
        if rule and rule.type == "string_map":
            rule.string_map.append((Acceptor(""), Acceptor("")))

    def remove_string_map_pair(self, uid: str, index: int) -> None:
        """Remove a pair from a string_map by index."""
        rule = self.data["id_map"].get(uid)
        if rule and rule.type == "string_map":
            if 0 <= index < len(rule.string_map):
                rule.string_map.pop(index)

    def add_test_mapping(self, uid: str) -> None:
        """Add a blank pair to test_mappings."""
        rule = self.data["id_map"].get(uid)
        if rule:
            rule.test_mappings.append(["", ""])

    def remove_test_mapping(self, uid: str, index: int) -> None:
        """Remove a pair from test_mappings by index."""
        rule = self.data["id_map"].get(uid)
        if rule:
            if 0 <= index < len(rule.test_mappings):
                rule.test_mappings.pop(index)

    def run_tests(self, uid: str, grammar: Any) -> None:
        """
        Run test mappings for the rule identified by uid.
        Results are stored in self.data["test_results"][uid].
        """
        rule = self.data["id_map"][uid]
        fst_orch = grammar.fst_orchestrator
        # Pass the rule object directly for in-memory testing
        results = fst_orch.test_rule(rule, rule.test_mappings)
        self.data["test_results"][uid] = results

    def add_sequence_step(self, uid: str) -> None:
        """Append a step to a rule_sequence."""
        rule = self.data["id_map"].get(uid)
        if rule and rule.type == "rule_sequence":
            id_map = self.data["id_map"]
            # default to the first available rule that isn't itself
            available = [r for r in id_map.values() if r.uuid != uid and r._ref]
            if available:
                rule.rule_sequence.append(available[0])

    def remove_sequence_step(self, uid: str, index: int) -> None:
        """Remove a step from a rule_sequence by index and clear associated widget keys."""
        rule = self.data["id_map"].get(uid)
        if rule and rule.type == "rule_sequence":
            if 0 <= index < len(rule.rule_sequence):
                rule.rule_sequence.pop(index)
                # Clear session state keys to force re-render with shifted indices
                i = 0
                while True:
                    key = self.get_widget_key(f"{_RULE_SEQ_PREFIX}{i}-", uid)
                    if key in st.session_state:
                        st.session_state.pop(key, None)
                        i += 1
                    else:
                        break


"""
Rule rendering
"""


def _render_rule(uid: str, editor: RulesEditor) -> None:
    """Render a single rule as an expandable card."""
    rule: Rule = editor.data["id_map"][uid]
    test_results = editor.data["test_results"].get(uid)

    ref_label = rule._ref or "(ref not set)"
    type_label = rule.type.replace("_", " ").title()

    with st.expander(f"`{ref_label}` — {type_label}", expanded=False, key=editor.get_widget_key("expander-", uid)):
        col_name, col_type = st.columns(2)
        with col_name:
            st.text_input(
                "Rule name",
                key=editor.get_widget_key(_NAME_PREFIX, uid),
                value=rule._ref,
                placeholder="coalesce_before_i",
            )
        with col_type:
            new_type = st.selectbox(
                "Rule type",
                options=_RULE_TYPES,
                index=_RULE_TYPES.index(rule.type) if rule.type in _RULE_TYPES else 0,
                format_func=lambda s: s.replace("_", " ").title(),
                key=editor.get_widget_key(_TYPE_PREFIX, uid),
            )
            st.button(
                "Change rule type",
                disabled=(new_type == rule.type),
                key=editor.get_widget_key(_CHANGE_TYPE_PREFIX, uid),
                on_click=editor.change_rule_type,
                args=(uid, new_type),
            )

        st.text_input(
            "Description",
            key=editor.get_widget_key(_DESC_PREFIX, uid),
            value=rule.description or "",
            placeholder="Short explanation of what this rule does",
        )

        # Type-specific fields
        if rule.type == "simple_rule":
            col_in, col_out = st.columns(2)
            with col_in:
                editor.render_keyup_input(
                    "Input pattern",
                    _INPUT_PREFIX,
                    uid,
                    value=rule.input_pattern.value or "",
                    placeholder="<V>-?",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Input Pattern for '{rule._ref}'")
                )
            with col_out:
                editor.render_keyup_input(
                    "Output pattern",
                    _OUTPUT_PREFIX,
                    uid,
                    value=rule.output_pattern.value or "",
                    placeholder="ɛ",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Output Pattern for '{rule._ref}'")
                )

            col_left, col_right = st.columns(2)
            with col_left:
                editor.render_keyup_input(
                    "Left context",
                    _LEFT_CTX_PREFIX,
                    uid,
                    value=rule.left_context.value or "",
                    placeholder="(<R>|<N>)",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Left Context for '{rule._ref}'")
                )
            with col_right:
                editor.render_keyup_input(
                    "Right context",
                    _RIGHT_CTX_PREFIX,
                    uid,
                    value=rule.right_context.value or "",
                    placeholder="<V>",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Right Context for '{rule._ref}'")
                )

            st.selectbox(
                "Direction",
                options=_DIRECTIONS,
                index=_DIRECTIONS.index(rule.direction)
                if rule.direction in _DIRECTIONS
                else 0,
                key=editor.get_widget_key(_DIRECTION_PREFIX, uid),
            )

        elif rule.type == "string_map":
            st.markdown("**String map**")
            for i, (inp, out) in enumerate(rule.string_map):
                m_col1, m_col2, m_col3 = st.columns([1, 1, 0.2])
                with m_col1:
                    editor.render_keyup_input(
                        "Input",
                        f"{_STRING_MAP_PREFIX}in-{i}-",
                        uid,
                        value=inp.value or "",
                        label_visibility="collapsed",
                        validation_fn=lambda v: editor.validate_acceptor(v, f"String Map Input (Line {i + 1}) for '{rule._ref}'")
                    )
                with m_col2:
                    editor.render_keyup_input(
                        "Output",
                        f"{_STRING_MAP_PREFIX}out-{i}-",
                        uid,
                        value=out.value or "",
                        label_visibility="collapsed",
                        validation_fn=lambda v: editor.validate_acceptor(v, f"String Map Output (Line {i + 1}) for '{rule._ref}'")
                    )
                with m_col3:
                    st.button(
                        "🗑️",
                        key=editor.get_widget_key(f"remove_sm-{i}-", uid),
                        on_click=editor.remove_string_map_pair,
                        args=(uid, i),
                    )
            st.button(
                "➕ Add pair",
                key=editor.get_widget_key("add_sm-", uid),
                on_click=editor.add_string_map_pair,
                args=(uid,),
            )

            col_left, col_right = st.columns(2)
            with col_left:
                editor.render_keyup_input(
                    "Left context",
                    _LEFT_CTX_PREFIX,
                    uid,
                    value=rule.left_context.value or "",
                    placeholder="(<R>|<N>)",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Left Context for '{rule._ref}'")
                )
            with col_right:
                editor.render_keyup_input(
                    "Right context",
                    _RIGHT_CTX_PREFIX,
                    uid,
                    value=rule.right_context.value or "",
                    placeholder="<V>",
                    validation_fn=lambda v: editor.validate_acceptor(v, f"Right Context for '{rule._ref}'")
                )

            st.selectbox(
                "Direction",
                options=_DIRECTIONS,
                index=_DIRECTIONS.index(rule.direction)
                if rule.direction in _DIRECTIONS
                else 0,
                key=editor.get_widget_key(_DIRECTION_PREFIX, uid),
            )

        elif rule.type == "rule_sequence":
            id_map: dict[str, Rule] = editor.data["id_map"]
            available_refs = sorted(
                [r._ref for r in id_map.values() if r.uuid != uid and r._ref]
            )

            if not available_refs:
                st.warning("No other rules available to create a sequence.")
            else:
                st.markdown("**Sequence steps**")
                for i, step_rule in enumerate(rule.rule_sequence):
                    col_step, col_btn = st.columns([0.8, 0.2])
                    with col_step:
                        selected_ref = (
                            step_rule._ref if hasattr(step_rule, "_ref") else ""
                        )
                        st.selectbox(
                            f"Step {i + 1}",
                            options=available_refs,
                            index=available_refs.index(selected_ref)
                            if selected_ref in available_refs
                            else 0,
                            key=editor.get_widget_key(f"{_RULE_SEQ_PREFIX}{i}-", uid),
                            label_visibility="collapsed",
                        )
                    with col_btn:
                        st.button(
                            "🗑️",
                            key=editor.get_widget_key(f"remove_step-{i}-", uid),
                            on_click=editor.remove_sequence_step,
                            args=(uid, i),
                        )

                st.button(
                    "➕ Add step",
                    key=editor.get_widget_key("add_step-", uid),
                    on_click=editor.add_sequence_step,
                    args=(uid,),
                )

        # Test mappings (all rule types)
        st.markdown("**Test mappings**")
        for i, (inp, out) in enumerate(rule.test_mappings):
            t_col1, t_col2, t_col3 = st.columns([1, 1, 0.2])
            with t_col1:
                st.text_input(
                    "Input",
                    value=inp,
                    key=editor.get_widget_key(f"{_TEST_MAPPINGS_PREFIX}in-{i}-", uid),
                    label_visibility="collapsed",
                )
            with t_col2:
                st.text_input(
                    "Expected Output",
                    value=out,
                    key=editor.get_widget_key(f"{_TEST_MAPPINGS_PREFIX}out-{i}-", uid),
                    label_visibility="collapsed",
                )
            with t_col3:
                st.button(
                    "🗑️",
                    key=editor.get_widget_key(f"remove_tm-{i}-", uid),
                    on_click=editor.remove_test_mapping,
                    args=(uid, i),
                )
        st.button(
            "➕ Add test mapping",
            key=editor.get_widget_key("add_tm-", uid),
            on_click=editor.add_test_mapping,
            args=(uid,),
        )

        col_test, col_remove = st.columns(2)
        with col_test:
            if st.button(
                "▶ Run tests",
                key=editor.get_widget_key(_TEST_BUTTON_PREFIX, uid),
                use_container_width=True,
                disabled=not rule.test_mappings,
            ):
                grammar = st.session_state.get("grammar")
                if grammar is None:
                    st.warning("Grammar not loaded — cannot run tests.")
                else:
                    st.session_state["do_run_tests"] = uid
                    st.rerun()
        with col_remove:
            if st.button(
                "✕ Delete",
                key=editor.get_widget_key(_REMOVE_PREFIX, uid),
                use_container_width=True,
            ):
                editor.remove_rule(uid)
                st.rerun()

        # Test results
        if test_results is not None:
            results_list = test_results.get("results", [])
            all_pass = test_results.get("all_pass", False)
            if results_list:
                st.divider()
                for r in results_list:
                    icon = "✅" if r["pass"] else "❌"
                    extra_output = [s for s in r["output"] if s != r["expected_output"]]
                    if r["pass"] and not extra_output:
                        detail = f"`{r['input']}` → `{r['expected_output']}`"
                    elif r["pass"]:
                        detail = f"`{r['input']}` → `{r['expected_output']}` (also {'; '.join(extra_output)})"
                    else:
                        detail = f"`{r['input']}` → `{'; '.join(r['output'])}` (expected `{r['expected_output']}`)"
                    st.markdown(f"{icon} {detail}")
                if all_pass:
                    st.success("All tests pass")
                else:
                    st.error("Some tests failed")


"""
Page components
"""


def rules_form(editor: RulesEditor) -> None:
    """Render all rule cards."""
    id_map: dict[str, Rule] = editor.data.get("id_map", {})
    if not id_map:
        st.info(
            "No rules yet. Select a rule type and click **➕ Add rule** to start — "
            "for example a `simple_rule` rewrite or a `string_map`."
        )
    else:
        for uid in id_map:
            _render_rule(uid, editor)


"""
Page function
"""


def rules_page() -> None:
    st.set_page_config(
        page_title="Rules Editor",
        page_icon="📐",
        layout="wide",
    )

    editor_sidebar(
        kind=_config_kind,
        editor_class=RulesEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()

    if "do_run_tests" in st.session_state:
        uid: str = st.session_state.pop("do_run_tests")
        grammar: Grammar | None = st.session_state.get("grammar")
        if grammar is not None:
            editor.run_tests(uid, grammar)
            st.rerun()

    editor_header(kind=_config_kind, editor=editor)

    toolbar_placeholder = st.empty()

    st.divider()

    rules_form(editor)

    with toolbar_placeholder.container():
        st.selectbox(
            "New rule type",
            options=_RULE_TYPES,
            format_func=lambda s: s.replace("_", " ").title(),
            key="new_rule_type_select",
        )
        render_editor_toolbar(
            editor=editor,
            add_label="Add rule",
            add_callback=lambda: editor.insert_rule(
                st.session_state.get("new_rule_type_select", "simple_rule")
            ),
        )


if __name__ == "__main__":
    rules_page()
