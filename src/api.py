"""
FastAPI backend for parC grammar.
Provides following endpoints:
- `GET /schema/<kind>`: Retrieve the schema for a specific configuration kind.
- `GET /configs/<kind>`: List all configuration files for a specific kind.
- `GET /file/<kind>/<path>`: Read a specific configuration file.
- `PUT /file/<kind>/<path>`: Update a specific configuration file.
"""

import os
import yaml
import dotenv
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from jsonschema import validate, ValidationError
from camel_converter import to_snake

from src.config_utils.schema_validation import load_schema, CONFIG_KINDS
from src.config_utils.config_walker import ConfigWalker
from src.config_utils.watcher import _config_changed, start_watcher
from src.grammar.orchestrator.grammar_orchestrator import Grammar

dotenv.load_dotenv()
_raw = os.environ.get("CONFIG_DIR")
if not _raw:
    raise RuntimeError("CONFIG_DIR env var is not set")
_path = Path(_raw).expanduser()
if not _path.is_absolute():
    from src.constants import PROJECT_ROOT
    _path = Path(PROJECT_ROOT) / _path
CONFIG_DIR = _path.resolve()
if not CONFIG_DIR.is_dir():
    raise RuntimeError(f"CONFIG_DIR is not a valid directory: {CONFIG_DIR}")

start_watcher(str(CONFIG_DIR))

app = FastAPI()

_grammar: Grammar | None = None


def get_grammar() -> Grammar:
    global _grammar
    if _grammar is None or _config_changed.is_set():
        _config_changed.clear()
        _grammar = Grammar(**ConfigWalker(CONFIG_DIR).config_data)
    return _grammar


def _resolve_path(kind: str, ref: str) -> Path:
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind!r}")
    stem = ref.removeprefix("$")
    resolved = (CONFIG_DIR / to_snake(kind) / stem).with_suffix(".yaml").resolve()
    if not resolved.is_relative_to(CONFIG_DIR):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


@app.get("/schemas/{kind}")
def get_schema(kind: str):
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown kind: {kind!r}")
    schema = load_schema(kind)
    if schema is None:
        raise HTTPException(status_code=500, detail=f"Schema file missing for kind: {kind!r}")
    return schema


@app.get("/configs")
def list_configs(kind: str):
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind!r}")
    kind_dir = CONFIG_DIR / to_snake(kind)
    if not kind_dir.is_dir():
        return []
    return sorted(f"${p.stem}" for p in kind_dir.glob("*.yaml"))


@app.get("/file")
def read_file(kind: str, path: str):
    resolved = _resolve_path(kind, path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path!r}")
    with resolved.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.put("/file")
def write_file(kind: str, path: str, body: dict[str, Any]):
    resolved = _resolve_path(kind, path)
    schema = load_schema(kind)
    if schema is None:
        raise HTTPException(status_code=500, detail=f"Schema missing for kind: {kind!r}")
    try:
        validate(instance=body, schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    with resolved.open("w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, allow_unicode=True)


# app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
