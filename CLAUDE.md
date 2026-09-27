# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**parC** (Paradigm Compiler) is a toolkit for building and applying morphological analyzers (finite-state-transducer-based parsers) from linguistic fieldwork data. The grammar model is entirely config-driven (YAML validated against JSON Schemas) and the Python side is written in a functional style — plain functions over immutable data (`msgspec.Struct`/`NamedTuple`/dict), no class hierarchies for the grammar/compilation logic.

## Current branch state: mid-migration, tests do not collect

The `tira` branch is mid-refactor from hand-authored `schemas/<Kind>.json` + `NamedTuple` `resolve_rule`/`resolve_marker` resolution (old design, still visible in `src/yaml_utils/yaml_server.py`) to `msgspec.Struct`-based models in `src/models.py` with JSON Schemas *generated* from those structs (`src/yaml_utils/schema_gen.py` → `schemas/<PARDIR>/<Kind>.json`, e.g. `schemas/Phonology/Rule.json`; run via `uv run python -m src.yaml_utils.schema_gen`).

This migration is incomplete: `src/models.py` has been rewritten (structs use `tag_field="kind"` discriminated unions, decoded/validated via `msgspec.json.schema`/`msgspec.convert` rather than a separate resolver function), but the following have **not** been updated to match and are currently broken:
- `src/yaml_utils/schema_validation.py` is now an empty file (no `CONFIG_KIND_TO_PARDIR`, `CONFIG_KINDS`, or `validate_yaml`).
- `src/yaml_utils/yaml_server.py` still imports old names from `src.models` (`FeatureValue`, `resolve_rule`, `resolve_marker`, `UnorderedMarker`, `SingleStringMarker`, ...) that no longer exist — importing this module raises `ImportError`.
- `src/grammar/*.py` (all four modules) import from `yaml_server`/`schema_validation`, so importing any of them also fails.
- `tests/models_test.py`, `tests/transduction_test.py`, `tests/cache_invalidation_test.py` import stale names too (e.g. `RulesFile`/`FeatureCombinationsFile` instead of the current `RuleFile`/`FeatureCombinationFile`).

Net effect: **`uv run pytest` currently fails to collect any tests**, and the FastAPI app (`src/api.py`, which pulls in `src.grammar.*`) does not currently import successfully. When working on this branch, check whether your task is (a) continuing the migration — in which case `yaml_server.py`, `schema_validation.py`, `src/grammar/*`, and the test files all need their imports/usages reconciled with the current `src/models.py` names — or (b) unrelated work, in which case be aware you may not be able to run the existing test suite until the migration is finished, and say so rather than silently reporting tests as passing.

`src/yaml_utils/yaml_server.py` is otherwise a useful reference for the *shape* of the old design (per-kind YAML loading + validation, `resolve_rule`/`resolve_marker` picking a `NamedTuple` variant by trying constructors) even though its imports don't currently resolve.

## Commands

- Install deps: `uv sync` (`uv.lock` is canonical; `pyproject.toml` pins `pynini==2.1.6` and `requires-python = ">=3.8, <3.11"` — the checked-in `.venv` is 3.10, don't assume a newer interpreter works).
- Run the app: `uv run parC` (the `parC` console script → `src.api:run_app`), or directly `uv run uvicorn src.api:app --reload --port 8000`. `src/launcher.py` is stale/non-functional (broken import, checks a literal string instead of `YAML_DIR`) — don't use it as an entry point. Note: per the migration state above, this currently fails to import.
- Run tests: `YAML_DIR=yaml/spanish-example uv run pytest`. You must set `YAML_DIR` explicitly — `pyproject.toml` has a `[pytest]` `env_files = [".test.env"]` section intended to set `YAML_DIR=yaml/spanish-example` automatically, but the `pytest-env` plugin it depends on isn't installed, so it's a no-op. Without the explicit env var, `parC.env`'s `YAML_DIR=yaml/tira-example` wins by default and tests fail (they're written against the `spanish-example` dataset, e.g. rule name `diphthongization`, pattern `word_final_coda`). Currently this fails at collection time regardless — see migration state above.
- Run a single test: `YAML_DIR=yaml/spanish-example uv run pytest tests/transduction_test.py::test_suffix`.
- Regenerate schemas from the msgspec structs: `uv run python -m src.yaml_utils.schema_gen` (writes `schemas/<PARDIR>/<Kind>.json` for every entry in `CONFIG_KIND_TO_STRUCT`, keyed by `CONFIG_KIND_TO_PARDIR` — both dicts live at the bottom of `src/models.py`).
- Which YAML dataset loads is controlled by `YAML_DIR` (`src/constants.py::get_yaml_dir`, falls back to `parC.env`, then to `yaml/spanish-example`). Two example datasets ship in-repo: `yaml/spanish-example` and `yaml/tira-example`.
- Logging: `PARC_LOG_LEVEL` (default `INFO`) and `TIRA_LOG_OUTPUT` (`stdout`/`stderr`) control `loguru` output (`src/__init__.py`).

## Architecture

### Data lifecycle: YAML → validated struct → compiled FST → API → frontend

1. **Models** — `src/models.py` defines one `msgspec.Struct` per YAML file kind (`InventoryFile`, `PatternFile`, `RuleFile`, `FeatureDefinitionFile`, `FeatureMarkerFile`, `MultiFeatureMarkerFile`, `FeatureCombinationFile`, `ParadigmFile`, `PartOfSpeechFile`), each carrying a `tag_field="kind"` discriminator so cross-references and unions decode unambiguously. Rules (`Rule = SimpleRule | StringMapRule | RuleSequence`) and markers (`Marker = PrefixMarker | SuffixMarker | SuppletionMarker | PrincipalPartMarker | RuleMarker | ReplaceMarker`) are themselves tagged unions nested inside the file structs — no separate resolver function; `msgspec.convert`/`msgspec.json.decode` pick the right variant from the `kind` tag directly. Cross-file references (e.g. a `Paradigm` pointing at a `PartOfSpeech`) are typed `*Ref` structs (`RuleRef`, `PartOfSpeechRef`, `FeatureCombinationRef`, `MultiFeatureMarkerRef`, `FeatureMarkerRef`, `ParadigmRef`), each its own tagged struct rather than a bare string. `CONFIG_KIND_TO_STRUCT` and `CONFIG_KIND_TO_PARDIR` at the bottom of the file are the canonical kind→struct and kind→parent-directory maps.
2. **Reading + validation** — intended to read YAML files under `YAML_DIR` and validate each against `schemas/<PARDIR>/<Kind>.json` before use; see the migration-state note above for what's currently wired up vs. not.
3. **FST compilation**, in dependency order:
   - `src/grammar/acceptor_compilation.py` — builds the `pynini.SymbolTable` from inventory phones/tags + feature values, special FSAs (sigma, phone, flag, boundary...), a token map for the pattern-string DSL, and compiles pattern strings (`fsa()`, `word_fsa()`) via a hand-written recursive-descent parser over the operators in `ReservedSymbolMixin` (`src/fst_utils.py`).
   - `src/grammar/transducer_compilation.py` — compiles `Rule`s into `pynini.cdrewrite` FSTs and `Marker`s into prefix/suffix/suppletion/replace/rule/string-map FSTs, built on `acceptor_compilation`'s `fsa`/symbol table.
   - `src/grammar/marker_resolution.py` — given a paradigm + feature-value combo, resolves which markers apply (multi-feature markers first, then regular feature markers for remaining features, then global/principal-part markers), including resolving `principal_part` markers into a string-map marker via the lexicon (`src/lexicon.py`).
   - `src/grammar/paradigm_compilation.py` — builds per-paradigm `inflect`/`parse`/`search_lexicon`/`search_left_factor` FSTs by applying resolved markers to every root × feature-combo, and exposes the public `inflect`/`parse`/`search`/`inflect_stages` functions consumed by the API.
4. `src/api.py` — FastAPI app exposing `grammar-stats`/`inflection-meta`/`roots`/`lexical-features`/`patterns`/`rules`/`test-pattern`/`test-rule`/`inflect`/`parse`/`search`, and mounts `frontend/` as static files at `/`. Serializes `msgspec.Struct` results to JSON via `msgspec.to_builtins(...)`.
5. `frontend/` — plain ES-module JS, no build step. `api.js` is the only file that calls `fetch`; `hub.js`/`inflect.js`/`parse.js`/`tests.js` drive the tab-based UI defined in `index.html`.

### Caching — two independent layers

- **In-memory**: `@observed_cache([dirs...])` (`src/yaml_utils/cache.py`) wraps `functools.lru_cache` and additionally invalidates whenever the max mtime across the given source directories advances; args/kwargs are coerced to hashable equivalents (`list`→`tuple`, `dict`→`frozendict`) before hitting the cache. Used throughout `acceptor_compilation.py`/`transducer_compilation.py`/`paradigm_compilation.py`.
- **On-disk**: the symbol table and per-paradigm FSTs also persist under `<YAML_DIR>/.cache/` (`symbol_table.syms`, `Paradigm/{name}.{fst_kind}.fst`), validated against source-file mtimes the same way (`is_syms_cache_valid`/`is_fst_cache_valid`).
- `tests/cache_invalidation_test.py` exercises both invalidation paths by writing to real YAML files under `YAML_DIR` and restoring them via fixtures — if a test run is interrupted, check `git status` under `yaml/` for leftover mutations.

### Config directory taxonomy

Per-language config lives under `yaml/<language>-example/<ParDir>/<Kind>/*.yaml`, e.g. `yaml/spanish-example/Phonology/Rules/vowel_alternations.yaml`. `CONFIG_KIND_TO_PARDIR` (`src/models.py`) maps each kind to its parent dir: `Inventory`/`Pattern`/`Rule` → `Phonology`; `FeatureDefinition`/`FeatureMarker`/`MultiFeatureMarker` → `Exponence`; `Paradigm`/`FeatureCombination` → `Morphotactics`; `PartOfSpeech`/`Wordlist` → `Lexicon`. Generated schemas mirror this layout under `schemas/` (e.g. `schemas/Phonology/Rule.json`) — this replaces the old flat `schemas/<Kind>.json` layout.

Lexicon word lists (`Lexicon/Wordlists/*.csv`/`.xlsx`) are the one config surface *not* validated against a JSON Schema — `src/lexicon.py` reads them directly via pandas, cross-referencing `lexical_features`/`principal_parts` declared in the corresponding `PartOfSpeech` YAML, and auto-creates an empty CSV with the right columns if the wordlist is missing.

### Pattern-string DSL

Inventory classes, Patterns, and morpheme/rule contexts all share one regex-like DSL: `<ClassName>` references an inventory class or named pattern, `|` is disjunction, `{A B}` is union of literal tokens, `*`/`+`/`?` are closures, `^` negates inside `{}`. Reserved operators/symbols live in `ReservedSymbolMixin` (`src/fst_utils.py`). See `doc/grammar_modules.rst` for the linguistic rationale behind the phonology/exponence/morphotactics module split.

### `src/search/` — in-progress replacement for the paradigm-compilation search path

`src/search/` (`beam_search.py`, `beam_search_jit.py`, `edit_graph.py`, `edit_modeling.py`) implements a numba-jitted beam search over the compiled FSTs, intended to eventually replace the search path in `paradigm_compilation.py`. It is not yet wired into `src/api.py` — the live fuzzy-search path today is `build_search_lexicon_and_leftfactor`/`search` in `src/grammar/paradigm_compilation.py`. `beam_search_jit_stale.py` is a superseded variant of `beam_search_jit.py` — check before using either.
