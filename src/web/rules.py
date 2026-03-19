from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from src.web.configs import safe_file_path


RULES_DIR_NAME = "rules"


def safe_rules_path(config_dir: str, relative_path: str) -> Path | None:
    path = safe_file_path(config_dir, relative_path)
    if path is None:
        return None
    if RULES_DIR_NAME not in path.parts:
        return None
    return path


def new_rules_state(relative_path: str = "") -> dict[str, Any]:
    return {
        "path": relative_path,
        "kind": "Rules",
        "rules": [],
    }


def load_rules_state(config_dir: str, relative_path: str) -> dict[str, Any]:
    path = safe_rules_path(config_dir, relative_path)
    if path is None or not path.exists():
        raise FileNotFoundError(relative_path)

    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}

    if document.get("kind") != "Rules":
        raise ValueError(f"{relative_path} is not a Rules config")

    return {
        "path": relative_path,
        "kind": "Rules",
        "rules": _rules_from_document(document.get("rules", {})),
    }
def state_from_json(payload: str | None) -> dict[str, Any]:
    if not payload:
        return new_rules_state()
    state = json.loads(payload)
    state.setdefault("kind", "Rules")
    state.setdefault("path", "")
    state.setdefault("rules", [])
    return _ensure_ids(state)


def state_to_json(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False)


def update_state_from_form(state: dict[str, Any], form: Any) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["path"] = form.get("path", updated.get("path", "")).strip()
    updated["rules"] = _update_rules_from_form(updated.get("rules", []), form)
    return updated


def add_rule(state: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated.setdefault("rules", []).append(_blank_rule())
    return updated


def remove_rule(state: dict[str, Any], rule_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["rules"] = [rule for rule in updated.get("rules", []) if rule.get("id") != rule_id]
    return updated


def rules_yaml(state: dict[str, Any]) -> str:
    document = {
        "kind": "Rules",
        "rules": _document_rules(state.get("rules", [])),
    }
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def save_rules(config_dir: str, state: dict[str, Any]) -> str:
    relative_path = state.get("path", "").strip()
    if not relative_path:
        raise ValueError("A file path is required")

    path = safe_rules_path(config_dir, relative_path)
    if path is None:
        raise ValueError("Path must point to a YAML file inside a rules directory under the selected config path.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(rules_yaml(state))
    return relative_path
def _ensure_ids(state: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["rules"] = [_ensure_rule_ids(rule) for rule in updated.get("rules", [])]
    return updated


def _ensure_rule_ids(rule: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(rule)
    current.setdefault("id", uuid.uuid4().hex)
    current.setdefault("name", "")
    current.setdefault("rule_type", "simple_rule")
    current.setdefault("description", "")
    current.setdefault("input_pattern", "")
    current.setdefault("output_pattern", "")
    current.setdefault("string_map_text", "")
    current.setdefault("rule_sequence_text", "")
    current.setdefault("left_context", "")
    current.setdefault("right_context", "")
    current.setdefault("direction", "")
    current.setdefault("sigma_star", "")
    current.setdefault("test_mappings_text", "")
    return current


def _blank_rule() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "name": "",
        "rule_type": "simple_rule",
        "description": "",
        "input_pattern": "",
        "output_pattern": "",
        "string_map_text": "",
        "rule_sequence_text": "",
        "left_context": "",
        "right_context": "",
        "direction": "",
        "sigma_star": "",
        "test_mappings_text": "",
    }


def _rules_from_document(document_rules: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for name, value in document_rules.items():
        if not isinstance(value, dict):
            continue
        rule = _blank_rule()
        rule["name"] = str(name)
        rule["description"] = str(value.get("description", "") or "")
        rule["left_context"] = str(value.get("left_context", "") or "")
        rule["right_context"] = str(value.get("right_context", "") or "")
        rule["direction"] = str(value.get("direction", "") or "")
        rule["sigma_star"] = str(value.get("sigma_star", "") or "")
        rule["test_mappings_text"] = "\n".join(
            f"{source} => {target}" for source, target in value.get("test_mappings", [])
        )

        if "string_map" in value:
            rule["rule_type"] = "string_map"
            rule["string_map_text"] = "\n".join(
                f"{source} => {target}" for source, target in value.get("string_map", [])
            )
        elif "rule_sequence" in value:
            rule["rule_type"] = "rule_sequence"
            rule["rule_sequence_text"] = "\n".join(str(item) for item in value.get("rule_sequence", []))
        else:
            rule["rule_type"] = "simple_rule"
            rule["input_pattern"] = _serialize_nullable(value.get("input_pattern", ""))
            rule["output_pattern"] = _serialize_nullable(value.get("output_pattern", ""))

        rules.append(rule)
    return rules


def _document_rules(rules: list[dict[str, Any]]) -> dict[str, Any]:
    document_rules: dict[str, Any] = {}
    for rule in rules:
        name = rule.get("name", "").strip()
        if not name:
            continue

        entry: dict[str, Any] = {}
        description = rule.get("description", "").strip()
        if description:
            entry["description"] = description

        rule_type = rule.get("rule_type", "simple_rule")
        if rule_type == "string_map":
            string_map = _split_pairs(rule.get("string_map_text", ""))
            if string_map:
                entry["string_map"] = string_map
        elif rule_type == "rule_sequence":
            rule_sequence = _split_lines(rule.get("rule_sequence_text", ""))
            if rule_sequence:
                entry["rule_sequence"] = rule_sequence
        else:
            entry["input_pattern"] = _coerce_nullable_pattern(rule.get("input_pattern", ""))
            entry["output_pattern"] = _coerce_nullable_pattern(rule.get("output_pattern", ""))

        for attr in ("left_context", "right_context", "direction", "sigma_star"):
            value = rule.get(attr, "").strip()
            if value:
                entry[attr] = value

        test_mappings = _split_pairs(rule.get("test_mappings_text", ""))
        if test_mappings:
            entry["test_mappings"] = test_mappings

        document_rules[name] = entry
    return document_rules


def _update_rules_from_form(rules: list[dict[str, Any]], form: Any) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = rule["id"]
        current = copy.deepcopy(rule)
        for attr in (
            "name",
            "rule_type",
            "description",
            "input_pattern",
            "output_pattern",
            "string_map_text",
            "rule_sequence_text",
            "left_context",
            "right_context",
            "direction",
            "sigma_star",
            "test_mappings_text",
        ):
            current[attr] = form.get(f"{attr}-{rule_id}", current.get(attr, "")).strip()
        updated.append(current)
    return updated


def _split_pairs(value: str) -> list[list[str]]:
    pairs: list[list[str]] = []
    for line in _split_lines(value):
        if "=>" in line:
            source, target = line.split("=>", 1)
        elif "," in line:
            source, target = line.split(",", 1)
        else:
            continue
        pairs.append([source.strip(), target.strip()])
    return pairs


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _serialize_nullable(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _coerce_nullable_pattern(value: str) -> Any:
    stripped = value.strip()
    if stripped.lower() == "null":
        return None
    return stripped
