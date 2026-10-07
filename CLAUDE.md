# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**parC** (Paradigm Compiler) is a toolkit for building and applying morphological analyzers (finite-state-transducer-based parsers) from linguistic fieldwork data. The grammar model is entirely config-driven (YAML validated against JSON Schemas) and the Python side is written in a functional style — plain functions over immutable data (`msgspec.Struct`/`NamedTuple`/dict), no class hierarchies for the grammar/compilation logic.

## Current branch state: mid-migration, tests do not collect

The `tira` branch is mid-refactor from hand-authored `schemas/<Kind>.json` + `NamedTuple` resolution to `msgspec.Struct`-based models in `src/models.py`, with JSON Schemas *generated* from those structs (`src/yaml/schema_gen.py` → `schemas/<PARDIR>/<Kind>.json`).

What works today:
- `src/models.py` — the structs. Every config in `yaml/spanish-example` decodes with them.
- `src/yaml/yaml_server.py` — rewritten as the new loader: `read_configs_flat()` decodes every file into a struct registry (plus source-file, mtime and decode-error maps), and `walk_all_configs()` walks nested structs, validates relations and builds the dependency graph. It imports cleanly. It still has `breakpoint()` calls and a debugging `__main__` block, and reports errors by logging + raising rather than returning them.
- `src/relations.py` — the relation table (`Reference` / `Constraint` / `Mapping`) that validates cross-struct references and feeds the dependency graph. A rewrite is planned (MAR-10).

What is still broken:
- The old per-kind getters are gone from `yaml_server.py` (`get_rules`, `get_patterns`, `get_inventory_items`, `get_feature_map`, `get_feature_array`, `get_markers`, `get_inflection_stages`, `get_yaml_kind`, `get_yaml_data_safe`, `get_yaml_path`) and nothing replaces them yet (MAR-15).
- `src/grammar/*.py` (all four modules) and `src/lexicon.py` import those getters, and `transducer_compilation.py` / `marker_resolution.py` import marker types that no longer exist (`SingleStringMarker`, `StringTupleMarker`, `UnorderedMarker`, `resolve_marker`). Importing any of them fails.
- `src/yaml/schema_validation.py` no longer exists; `paradigm_compilation.py` still imports from it.
- A rename is half-applied in `cache.py`, `lexicon.py`, `paradigm_compilation.py` and `marker_resolution.py`: functions take a parameter named `description` while the body still uses `name`, so they would raise `NameError` even once the imports are fixed.
- `tests/models_test.py`, `tests/transduction_test.py`, `tests/cache_invalidation_test.py` import stale names (`*Ref` structs, old marker types, old getters).
- `schemas/` holds only a stale flat `MultiFeatureMarkers.json`; the generated per-directory schemas are not checked in.
- `yaml/tira-example` is only partly migrated: `Phonology/Inventory/tags.yaml` fails to decode, and it has no Exponence, Lexicon or Paradigm configs.
- `SuppletionMarker` is defined in `src/models.py` but is not a member of the `Marker` union, so a `kind: suppletion` marker would not decode.

Net effect: **`uv run pytest` currently fails to collect any tests**, and the FastAPI app (`src/api.py`, which pulls in `src.grammar.*`) does not import. When working on this branch, check whether your task is (a) continuing the migration or (b) unrelated work, in which case you may not be able to run the existing test suite — say so rather than silently reporting tests as passing.

## Roadmap and ownership

The roadmap lives in Linear (project **parC**, team key `MAR`). Milestones: **First light** (finish the migration, diagnostics, FST cache), **CLI** (service layer + typer CLI), **Web app and editor** (Litestar API, `static/` frontend, config editor), then the engine milestones (continuation lexicons, fuzzy search, context-free processes).

Planned layering, not yet built:
- core — `src/models.py`, `src/relations.py`, `src/yaml/` (to be renamed from `src/yaml/`), `src/grammar/`, `src/lexicon.py`.
- `src/diagnostics.py` — shared `Diagnostic` / `Location` / `DiagnosticError` types that core and services both import; problems are reported as data.
- `src/services/` — one plain function per use case, taking a `Project` and returning frozen msgspec Structs. No printing, no HTTP.
- `src/adapters/` — thin typer + rich CLI and Litestar API over the services. The CLI's `--json` output is the same payload the API returns. Litestar replaces FastAPI and pydantic.
- `static/` — the frontend (to be renamed from `frontend/`).

Ownership: Mark writes core (`src/yaml`, `src/grammar`, models, relations, lexicon) and the morphology slice (inflect / parse / search services and commands). Claude writes `src/diagnostics.py`, the rest of `src/services/`, `src/adapters/` and `static/`; those issues carry the `claude` label in Linear. Do not edit core unprompted — propose the interface change instead.

Caching decision: parC is assumed to run as one-off CLI executions. Structs are re-read and re-validated on every run; only the symbol table and per-paradigm FSTs are cached, on disk. The in-memory `observed_cache` layer described under "Caching" below is being removed (MAR-11); do not build on it.

## Commands

- Install deps: `uv sync` (`uv.lock` is canonical; `pyproject.toml` pins `pynini==2.1.6` and `requires-python = ">=3.8, <3.11"` — the checked-in `.venv` is 3.10, don't assume a newer interpreter works).
- Run the app: `uv run parC` (the `parC` console script → `src.api:run_app`), or directly `uv run uvicorn src.api:app --reload --port 8000`. `src/launcher.py` is stale/non-functional (broken import, checks a literal string instead of `YAML_DIR`) — don't use it as an entry point. Note: per the migration state above, this currently fails to import.
- Run tests: `YAML_DIR=yaml/spanish-example uv run pytest`. You must set `YAML_DIR` explicitly — `pyproject.toml` has a `[pytest]` `env_files = [".test.env"]` section intended to set `YAML_DIR=yaml/spanish-example` automatically, but the `pytest-env` plugin it depends on isn't installed, so it's a no-op. Without the explicit env var, `parC.env`'s `YAML_DIR=yaml/tira-example` wins by default and tests fail (they're written against the `spanish-example` dataset, e.g. rule name `diphthongization`, pattern `word_final_coda`). Currently this fails at collection time regardless — see migration state above.
- Run a single test: `YAML_DIR=yaml/spanish-example uv run pytest tests/transduction_test.py::test_suffix`.
- Regenerate schemas from the msgspec structs: `uv run python -m src.yaml.schema_gen` (writes `schemas/<PARDIR>/<Kind>.json` for every entry in `CONFIG_KIND_TO_STRUCT`, keyed by `CONFIG_KIND_TO_PARDIR` — both dicts live at the bottom of `src/models.py`).
- Which YAML dataset loads is controlled by `YAML_DIR` (`src/constants.py::get_yaml_dir`, falls back to `parC.env`, then to `yaml/spanish-example`). Two example datasets ship in-repo: `yaml/spanish-example` and `yaml/tira-example`.
- Logging: `PARC_LOG_LEVEL` (default `INFO`) and `TIRA_LOG_OUTPUT` (`stdout`/`stderr`) control `loguru` output (`src/__init__.py`).

## Architecture

### Data lifecycle: YAML → validated struct → compiled FST → API → frontend

1. **Models** — `src/models.py` defines one `msgspec.Struct` per YAML file kind (`InventoryFile`, `PatternFile`, `RuleFile`, `FeatureDefinitionFile`, `FeatureMarkerFile`, `MultiFeatureMarkerFile`, `FeatureCombinationFile`, `ParadigmFile`, `PartOfSpeechFile`), each carrying a `tag_field="kind"` discriminator so cross-references and unions decode unambiguously. Rules (`Rule = SimpleRule | StringMapRule | RuleSequence`), markers (`Marker = PrefixMarker | SuffixMarker | ReplaceMarker | PrincipalPartMarker | RuleMarker`) and inventory nodes (`Node = PhonesNode | TagsNode | NestedNode`) are themselves tagged unions nested inside the file structs — no separate resolver function; `msgspec.convert`/`msgspec.json.decode` pick the right variant from the `kind` tag directly. Cross-file references (e.g. `ParadigmFile.part_of_speech`) are bare id strings; the typed `*Ref` structs were dropped. What a string field refers to, and which values it may take, is declared in the relation table in `src/relations.py` and checked after decoding. Structs are identified by `(id, kind)` tuples (`StructIdType`, via `get_struct_id`). `CONFIG_KIND_TO_STRUCT` and `CONFIG_KIND_TO_PARDIR` at the bottom of the file are the canonical kind→struct and kind→parent-directory maps.
2. **Reading + validation** — `src/yaml/yaml_server.py` reads every YAML file under `YAML_DIR`, decodes it with `msgspec.yaml.decode` into its file struct (the decode is the schema check; the generated JSON Schemas are for editors), then walks the structs to validate relations and build the dependency graph. See the migration-state note above for what downstream code is wired up to it.
3. **FST compilation**, in dependency order:
   - `src/grammar/acceptor_compilation.py` — builds the `pynini.SymbolTable` from inventory phones/tags + feature values, special FSAs (sigma, phone, flag, boundary...), a token map for the pattern-string DSL, and compiles pattern strings (`fsa()`, `word_fsa()`) via a hand-written recursive-descent parser over the operators in `ReservedSymbolMixin` (`src.grammar.fst_utils.py`).
   - `src/grammar/transducer_compilation.py` — compiles `Rule`s into `pynini.cdrewrite` FSTs and `Marker`s into prefix/suffix/suppletion/replace/rule/string-map FSTs, built on `acceptor_compilation`'s `fsa`/symbol table.
   - `src/grammar/marker_resolution.py` — given a paradigm + feature-value combo, resolves which markers apply (multi-feature markers first, then regular feature markers for remaining features, then global/principal-part markers), including resolving `principal_part` markers into a string-map marker via the lexicon (`src/lexicon.py`).
   - `src/grammar/paradigm_compilation.py` — builds per-paradigm `inflect`/`parse`/`search_lexicon`/`search_left_factor` FSTs by applying resolved markers to every root × feature-combo, and exposes the public `inflect`/`parse`/`search`/`inflect_stages` functions consumed by the API.
4. `src/api.py` — FastAPI app exposing `grammar-stats`/`inflection-meta`/`roots`/`lexical-features`/`patterns`/`rules`/`test-pattern`/`test-rule`/`inflect`/`parse`/`search`, and mounts `frontend/` as static files at `/`. Serializes `msgspec.Struct` results to JSON via `msgspec.to_builtins(...)`.
5. `frontend/` — plain ES-module JS, no build step. `api.js` is the only file that calls `fetch`; `hub.js`/`inflect.js`/`parse.js`/`tests.js` drive the tab-based UI defined in `index.html`.

### Caching — two independent layers

- **In-memory**: `@observed_cache([dirs...])` (`src/yaml/cache.py`) wraps `functools.lru_cache` and additionally invalidates whenever the max mtime across the given source directories advances; args/kwargs are coerced to hashable equivalents (`list`→`tuple`, `dict`→`frozendict`) before hitting the cache. Used throughout `acceptor_compilation.py`/`transducer_compilation.py`/`paradigm_compilation.py`.
- **On-disk**: the symbol table and per-paradigm FSTs also persist under `<YAML_DIR>/.cache/` (`symbol_table.syms`, `Paradigm/{name}.{fst_kind}.fst`), validated against source-file mtimes the same way (`is_syms_cache_valid`/`is_fst_cache_valid`).
- `tests/cache_invalidation_test.py` exercises both invalidation paths by writing to real YAML files under `YAML_DIR` and restoring them via fixtures — if a test run is interrupted, check `git status` under `yaml/` for leftover mutations.

### Config directory taxonomy

Per-language config lives under `yaml/<language>-example/<ParDir>/<Kind>/*.yaml`, e.g. `yaml/spanish-example/Phonology/Rules/vowel_alternations.yaml`. `CONFIG_KIND_TO_PARDIR` (`src/models.py`) maps each kind to its parent dir: `Inventory`/`Pattern`/`Rule` → `Phonology`; `FeatureDefinition`/`FeatureMarker`/`MultiFeatureMarker` → `Exponence`; `Paradigm`/`FeatureCombination` → `Morphotactics`; `PartOfSpeech`/`Wordlist` → `Lexicon`. Generated schemas mirror this layout under `schemas/` (e.g. `schemas/Phonology/Rule.json`) — this replaces the old flat `schemas/<Kind>.json` layout.

Lexicon word lists (`Lexicon/Wordlists/*.csv`/`.xlsx`) are the one config surface *not* validated against a JSON Schema — `src/lexicon.py` reads them directly via pandas, cross-referencing `lexical_features`/`principal_parts` declared in the corresponding `PartOfSpeech` YAML, and auto-creates an empty CSV with the right columns if the wordlist is missing.

### Pattern-string DSL

Inventory classes, Patterns, and morpheme/rule contexts all share one regex-like DSL: `<ClassName>` references an inventory class or named pattern, `|` is disjunction, `{A B}` is union of literal tokens, `*`/`+`/`?` are closures, `^` negates inside `{}`. Reserved operators/symbols live in `ReservedSymbolMixin` (`src.grammar.fst_utils.py`). See `doc/grammar_modules.rst` for the linguistic rationale behind the phonology/exponence/morphotactics module split.

### `src/search/` — in-progress replacement for the paradigm-compilation search path

`src/search/` (`beam_search.py`, `beam_search_jit.py`, `edit_graph.py`, `edit_modeling.py`) implements a numba-jitted beam search over the compiled FSTs, intended to eventually replace the search path in `paradigm_compilation.py`. It is not yet wired into `src/api.py` — the live fuzzy-search path today is `build_search_lexicon_and_leftfactor`/`search` in `src/grammar/paradigm_compilation.py`. `beam_search_jit_stale.py` is a superseded variant of `beam_search_jit.py` — check before using either.
