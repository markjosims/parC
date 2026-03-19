from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, redirect, render_template, request, url_for
import yaml

from src.web.configs import (
    create_manifest_session,
    get_upload_session,
    group_yaml_files_by_kind,
    known_config_kinds,
    list_config_yaml_files,
    list_uploaded_yaml_files,
    load_config_entry,
    load_uploaded_config_entry,
    new_text_config_state,
    save_config_text,
    save_uploaded_config_text,
    suggested_config_path,
)
from src.registry.fst_registry import FstRegistry
from src.web.inventory import (
    add_child_node,
    add_root_node,
    inventory_yaml,
    load_inventory_state,
    load_uploaded_inventory_state,
    remove_node,
    save_inventory,
    save_uploaded_inventory,
    state_from_json,
    state_to_json,
    update_state_from_form,
)
from src.web.patterns import (
    add_pattern,
    load_patterns_state,
    load_uploaded_patterns_state,
    patterns_yaml,
    remove_pattern,
    save_patterns,
    save_uploaded_patterns,
    state_from_json as patterns_state_from_json,
    state_to_json as patterns_state_to_json,
    update_state_from_form as update_patterns_state_from_form,
)
from src.web.rules import (
    add_rule,
    load_rules_state,
    load_uploaded_rules_state,
    remove_rule,
    rules_yaml,
    save_rules,
    save_uploaded_rules,
    state_from_json as rules_state_from_json,
    state_to_json as rules_state_to_json,
    update_state_from_form as update_rules_state_from_form,
)
from flask import current_app as app


bp = Blueprint("web", __name__)
FST_REGISTRY_CACHE: dict[str, tuple[float, FstRegistry]] = {}


@bp.post("/scan-config")
def scan_config():
    manifest = request.form.get("manifest", "")
    if not manifest:
        return redirect(url_for("web.index", error="Choose a directory first."))
    token = create_manifest_session(manifest)
    return redirect(url_for("web.index", config_token=token))


@bp.get("/")
def index():
    config_token = request.args.get("config_token", "").strip()
    selected_path = request.args.get("path", "").strip()
    message = request.args.get("message")
    error = request.args.get("error")

    source = _resolve_source(config_token)
    if source.get("error"):
        state = new_text_config_state(relative_path=selected_path)
        return _render_page(
            source,
            state,
            selected_path=selected_path,
            selected_kind=state.get("kind") or None,
            error=source["error"],
        )

    state = _load_editor_state(source, selected_path)
    return _render_page(
        source,
        state,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.post("/config")
def config_editor():
    action = request.form.get("action", "")
    config_token = request.form.get("config_token", "").strip()
    source = _resolve_source(config_token)
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    editor_kind = request.form.get("editor_kind", "").strip()
    message = None
    error = None

    if action == "new":
        new_kind = request.form.get("new_kind", "").strip() or "Inventory"
        file_stem = request.form.get("file_stem", "").strip()
        state = _new_editor_state(new_kind, suggested_config_path(new_kind, file_stem))
        if new_kind == "Inventory":
            state = add_root_node(state)
    else:
        state = _state_from_form(request.form, editor_kind)
        if action == "add-root" and state.get("kind") == "Inventory":
            state = add_root_node(state)

    if action == "save":
        try:
            _save_state(source, state)
            prefix = "Updated uploaded copy of" if source["config_token"] else "Saved"
            message = f"{prefix} {state['path']}"
        except ValueError as exc:
            error = str(exc)

    selected_path = state.get("path", "")
    return _render_page(
        source,
        state,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.post("/inventory/add-child/<node_id>")
def inventory_add_child(node_id: str):
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = state_from_json(request.form.get("state"))
    state = update_state_from_form(state, request.form)
    state = add_child_node(state, node_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/inventory/remove-node/<node_id>")
def inventory_remove_node(node_id: str):
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = state_from_json(request.form.get("state"))
    state = update_state_from_form(state, request.form)
    state = remove_node(state, node_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/patterns/add-entry")
def patterns_add_entry():
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = patterns_state_from_json(request.form.get("state"))
    state = update_patterns_state_from_form(state, request.form)
    state = add_pattern(state)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Patterns",
    )


@bp.post("/patterns/remove-entry/<pattern_id>")
def patterns_remove_entry(pattern_id: str):
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = patterns_state_from_json(request.form.get("state"))
    state = update_patterns_state_from_form(state, request.form)
    state = remove_pattern(state, pattern_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Patterns",
    )


@bp.post("/patterns/run-tests/<pattern_id>")
def patterns_run_tests(pattern_id: str):
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = patterns_state_from_json(request.form.get("state"))
    state = update_patterns_state_from_form(state, request.form)

    error = None
    target = next((p for p in state["patterns"] if p["id"] == pattern_id), None)
    if target is None:
        error = "Pattern not found in editor state."
    else:
        ref = target.get("ref", "").strip()
        includes = _split_test_strings(target.get("test_includes", ""))
        excludes = _split_test_strings(target.get("test_excludes", ""))
        try:
            config_dir = _local_config_dir()
            registry = _get_fst_registry(config_dir)
            results = registry.test_pattern(ref, includes, excludes)
            target["test_results"] = results
        except KeyError:
            error = f"Pattern ref '{ref}' not found in saved configs — save the file first."
        except Exception as exc:
            error = str(exc)

    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Patterns",
        error=error,
    )


@bp.post("/rules/add-entry")
def rules_add_entry():
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = rules_state_from_json(request.form.get("state"))
    state = update_rules_state_from_form(state, request.form)
    state = add_rule(state)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Rules",
    )


@bp.post("/rules/remove-entry/<rule_id>")
def rules_remove_entry(rule_id: str):
    source = _resolve_source(request.form.get("config_token", "").strip())
    if source.get("error"):
        return redirect(url_for("web.index", error=source["error"]))

    state = rules_state_from_json(request.form.get("state"))
    state = update_rules_state_from_form(state, request.form)
    state = remove_rule(state, rule_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Rules",
    )


def _resolve_source(config_token: str) -> dict[str, Any]:
    if config_token:
        upload_session = get_upload_session(config_token)
        if upload_session is None:
            return {"error": "Uploaded config session not found."}
        yaml_files = list_uploaded_yaml_files(config_token)
        return {
            "selected_source_label": upload_session["label"],
            "config_token": config_token,
            "yaml_files": yaml_files,
        }

    try:
        config_dir = _local_config_dir()
    except RuntimeError as exc:
        return {
            "error": str(exc),
            "selected_source_label": "",
            "config_token": "",
            "yaml_files": [],
        }
    return {
        "selected_source_label": config_dir,
        "config_token": "",
        "yaml_files": list_config_yaml_files(config_dir),
    }


def _load_editor_state(source: dict[str, Any], selected_path: str) -> dict[str, Any]:
    if not selected_path:
        return new_text_config_state()

    try:
        entry = _load_entry(source, selected_path)
    except (FileNotFoundError, ValueError):
        return new_text_config_state(relative_path=selected_path)

    if entry.get("kind") == "Inventory":
        return _load_inventory_state_for_source(source, selected_path)
    if entry.get("kind") == "Patterns":
        return _load_patterns_state_for_source(source, selected_path)
    if entry.get("kind") == "Rules":
        return _load_rules_state_for_source(source, selected_path)

    return {
        "path": selected_path,
        "kind": entry.get("kind", ""),
        "content": entry.get("content", ""),
    }


def _load_entry(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_config_entry(source["config_token"], relative_path)
    return load_config_entry(_local_config_dir(), relative_path)


def _load_inventory_state_for_source(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_inventory_state(source["config_token"], relative_path)
    return load_inventory_state(_local_config_dir(), relative_path)


def _load_patterns_state_for_source(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_patterns_state(source["config_token"], relative_path)
    return load_patterns_state(_local_config_dir(), relative_path)


def _new_editor_state(kind: str, relative_path: str) -> dict[str, Any]:
    if kind == "Inventory":
        return {
            "path": relative_path,
            "kind": "Inventory",
            "nodes": [],
        }
    if kind == "Patterns":
        return {
            "path": relative_path,
            "kind": "Patterns",
            "patterns": [],
        }
    if kind == "Rules":
        return {
            "path": relative_path,
            "kind": "Rules",
            "rules": [],
        }
    return new_text_config_state(kind, relative_path)


def _state_from_form(form: Any, editor_kind: str) -> dict[str, Any]:
    if editor_kind == "Inventory":
        state = state_from_json(form.get("state"))
        return update_state_from_form(state, form)
    if editor_kind == "Patterns":
        state = patterns_state_from_json(form.get("state"))
        return update_patterns_state_from_form(state, form)
    if editor_kind == "Rules":
        state = rules_state_from_json(form.get("state"))
        return update_rules_state_from_form(state, form)

    content = form.get("content", "")
    return {
        "path": form.get("path", "").strip(),
        "kind": _kind_from_content(content) or editor_kind,
        "content": content,
    }


def _save_state(source: dict[str, Any], state: dict[str, Any]) -> str:
    if state.get("kind") == "Inventory":
        if source["config_token"]:
            return save_uploaded_inventory(source["config_token"], state)
        return save_inventory(_local_config_dir(), state)
    if state.get("kind") == "Patterns":
        if source["config_token"]:
            return save_uploaded_patterns(source["config_token"], state)
        return save_patterns(_local_config_dir(), state)
    if state.get("kind") == "Rules":
        if source["config_token"]:
            return save_uploaded_rules(source["config_token"], state)
        return save_rules(_local_config_dir(), state)

    if source["config_token"]:
        return save_uploaded_config_text(source["config_token"], state["path"], state["content"])
    return save_config_text(_local_config_dir(), state["path"], state["content"])


def _render_page(
    source: dict[str, Any],
    state: dict[str, Any],
    selected_path: str = "",
    selected_kind: str | None = None,
    message: str | None = None,
    error: str | None = None,
):
    yaml_files = source.get("yaml_files", [])
    return render_template(
        "index.html",
        active_tab="config",
        selected_source_label=source.get("selected_source_label", ""),
        config_token=source.get("config_token", ""),
        yaml_files=yaml_files,
        yaml_groups=group_yaml_files_by_kind(yaml_files),
        available_kinds=known_config_kinds(yaml_files),
        state=state,
        selected_path=selected_path,
        selected_kind=selected_kind,
        editor_kind=state.get("kind", ""),
        state_json=_editor_state_json(state),
        yaml_preview=_editor_yaml_preview(state),
        message=message,
        error=error,
    )


def _kind_from_content(content: str) -> str:
    try:
        document = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return ""
    kind = document.get("kind") if isinstance(document, dict) else ""
    return kind if isinstance(kind, str) else ""


def _editor_state_json(state: dict[str, Any]) -> str:
    if state.get("kind") == "Inventory":
        return state_to_json(state)
    if state.get("kind") == "Patterns":
        return patterns_state_to_json(state)
    if state.get("kind") == "Rules":
        return rules_state_to_json(state)
    return ""


def _editor_yaml_preview(state: dict[str, Any]) -> str:
    if state.get("kind") == "Inventory":
        return inventory_yaml(state)
    if state.get("kind") == "Patterns":
        return patterns_yaml(state)
    if state.get("kind") == "Rules":
        return rules_yaml(state)
    return state.get("content", "")


def _load_rules_state_for_source(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_rules_state(source["config_token"], relative_path)
    return load_rules_state(_local_config_dir(), relative_path)


def _local_config_dir() -> str:
    config_dir = app.config.get("CONFIG_DIR")
    if not config_dir:
        raise RuntimeError("CONFIG_DIR is not configured for the Flask app.")
    return str(config_dir)


def _get_fst_registry(config_dir: str) -> FstRegistry:
    cache_key = str(Path(config_dir))
    current_stamp = _yaml_tree_mtime(cache_key)
    cached = FST_REGISTRY_CACHE.get(cache_key)
    if cached is not None and cached[0] == current_stamp:
        return cached[1]

    registry = FstRegistry.from_config_dir(cache_key)
    FST_REGISTRY_CACHE[cache_key] = (current_stamp, registry)
    return registry


def _yaml_tree_mtime(config_dir: str) -> float:
    root = Path(config_dir)
    mtimes = [path.stat().st_mtime for path in root.rglob("*.y*ml")]
    return max(mtimes, default=0.0)


def _split_test_strings(value: str) -> list[str]:
    """Split a comma-separated test string into a list, stripping whitespace."""
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]
