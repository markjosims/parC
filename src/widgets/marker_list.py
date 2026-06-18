import streamlit as st
from src.grammar.registry.feature_marker_registry import Marker
from src.pages.editors.editor_base import EditorBase

# Marker Editor Constants
_MARKER_TYPE_PREFIX = "marker-type-"
_MARKER_VALUE_PREFIX = "marker-val-"
_MARKER_REPLACE_IN_PREFIX = "marker-replace-in-"
_MARKER_REPLACE_OUT_PREFIX = "marker-replace-out-"
_MARKER_ORDER_PREFIX = "marker-order-"
_REMOVE_MARKER_PREFIX = "remove-marker-"

MARKER_WIDGET_PREFIXES = [
    _MARKER_TYPE_PREFIX,
    _MARKER_VALUE_PREFIX,
    _MARKER_REPLACE_IN_PREFIX,
    _MARKER_REPLACE_OUT_PREFIX,
    _MARKER_ORDER_PREFIX,
    _REMOVE_MARKER_PREFIX,
]

MARKER_TYPES = ["suffix", "prefix", "replace", "rule", "suppletion", "principal_part"]


def render_marker_list(
    editor: EditorBase,
    markers: list["Marker"],
    scope: str,
    available_rules: list[str],
    available_principal_parts: list[str],
    label: str = "Markers",
) -> None:
    """Reusable component for rendering a list of Markers."""
    st.subheader(label)

    # Check for pending removals
    pending_rm = st.session_state.pop(f"pending_remove_marker_{scope}", None)
    if pending_rm:
        remove_marker(markers, pending_rm)
        st.rerun()

    if not markers:
        st.info("Zero marking (no markers).")
    else:
        for marker in markers:
            render_marker_row(
                editor, marker, scope, available_rules, available_principal_parts
            )

    if st.button(f"➕ Add marker to {label.lower()}", key=f"add-m-{scope}"):
        add_marker(markers)
        st.rerun()


def render_marker_row(
    editor: EditorBase,
    marker: "Marker",
    scope: str,
    available_rules: list[str],
    available_principal_parts: list[str],
) -> None:
    """
    Reusable component for rendering a single Marker row.
    Handles selecting marker type and selecting an order stage.
    Marker type may be a suffix, prefix, unconditioned replace rule,
    conditioned rule, suppletion, or selection of a principal part.
    """
    m_uid = marker.uuid
    with st.container(border=True):
        col_type, col_order, col_del = st.columns([1.5, 1.5, 0.4])
        with col_type:
            selected_type = st.selectbox(
                "Type",
                options=MARKER_TYPES,
                index=(
                    MARKER_TYPES.index(marker.type)
                    if marker.type in MARKER_TYPES
                    else 0
                ),
                key=editor.get_widget_key(_MARKER_TYPE_PREFIX, scope, suffix=m_uid),
                label_visibility="collapsed",
            )
            if selected_type != marker.type:
                # Reset value fields when type changes to avoid confusion
                st.rerun()
        with col_order:
            st.text_input(
                "Order",
                value=marker.order or "",
                placeholder="Order stage",
                key=editor.get_widget_key(_MARKER_ORDER_PREFIX, scope, suffix=m_uid),
                label_visibility="collapsed",
            )
        with col_del:
            if st.button(
                "✕",
                key=editor.get_widget_key(_REMOVE_MARKER_PREFIX, scope, suffix=m_uid),
                help="Remove marker",
            ):
                st.session_state[f"pending_remove_marker_{scope}"] = m_uid
                st.rerun()

        if marker.type == "replace":
            r_col1, r_col2 = st.columns(2)
            val_in = marker.value[0] if isinstance(marker.value, tuple) else ""
            val_out = marker.value[1] if isinstance(marker.value, tuple) else ""
            with r_col1:
                st.text_input(
                    "Input",
                    value=val_in,
                    key=editor.get_widget_key(
                        _MARKER_REPLACE_IN_PREFIX, scope, suffix=m_uid
                    ),
                )
            with r_col2:
                st.text_input(
                    "Output",
                    value=val_out,
                    key=editor.get_widget_key(
                        _MARKER_REPLACE_OUT_PREFIX, scope, suffix=m_uid
                    ),
                )
        elif marker.type == "rule":
            st.selectbox(
                "Rule",
                options=[""] + available_rules,
                index=(
                    available_rules.index(marker.value) + 1
                    if isinstance(marker.value, str) and marker.value in available_rules
                    else 0
                ),
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
            )
        elif marker.type == "principal_part":
            st.selectbox(
                "Principal Part",
                options=[""] + available_principal_parts,
                index=(
                    available_principal_parts.index(marker.value) + 1
                    if isinstance(marker.value, str)
                    and marker.value in available_principal_parts
                    else 0
                ),
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
            )
        else:
            st.text_input(
                "Value",
                value=marker.value if isinstance(marker.value, str) else "",
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
                placeholder="e.g. -o, ba-",
            )


"""
Marker-specific lifecycle helpers
"""


def add_marker(markers: list[Marker]) -> None:
    markers.append(Marker(value="", type="suffix"))


def remove_marker(markers: list[Marker], m_uuid: str) -> None:
    markers[:] = [m for m in markers if m.uuid != m_uuid]


def sync_marker_list(editor: EditorBase, markers: list[Marker], scope: str) -> None:
    """Helper to sync a list of Marker objects from widgets."""
    for marker in markers:
        marker_uid = marker.uuid
        marker_type = editor.get_node_widget(
            _MARKER_TYPE_PREFIX, scope, suffix=marker_uid
        )
        marker_order = editor.get_node_widget(
            _MARKER_ORDER_PREFIX, scope, suffix=marker_uid
        )

        if marker_type is not None:
            marker.type = marker_type
        if marker_order is not None:
            marker.order = marker_order if marker_order.strip() else None

        if marker.type == "replace":
            replace_input = editor.get_node_widget(
                _MARKER_REPLACE_IN_PREFIX, scope, suffix=marker_uid
            )
            replace_output = editor.get_node_widget(
                _MARKER_REPLACE_OUT_PREFIX, scope, suffix=marker_uid
            )
            if replace_input is not None and replace_output is not None:
                value = [
                    editor.validate_pattern(
                        replace_input, label="Replace marker input pattern"
                    ),
                    editor.validate_pattern(
                        replace_output, label="Replace marker output pattern"
                    ),
                ]
                marker.value = tuple(value)
        elif marker.type in ["suffix", "prefix", "suppletion"]:
            val = editor.get_node_widget(_MARKER_VALUE_PREFIX, scope, suffix=marker_uid)
            val = editor.validate_pattern(
                val, label=f"{marker.type.capitalize()} marker pattern"
            )
            marker.value = val or ""
        else:  # marker.type in ["rule", "principal_part"]
            marker.value = (
                editor.get_node_widget(_MARKER_VALUE_PREFIX, scope, suffix=marker_uid)
                or ""
            )
