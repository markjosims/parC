# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tool for building morphological parsers for language documentation.


### Registry layer (`src/registry/`)
- **`registry_utils.py`** - Base `Registry` class (loads YAML configs, validates against JSON schema, resolves `$name` cross-file refs) and `ReservedSymbolMixin` (defines reserved pattern-string symbols).
- **`fst_registry.py`** - `InventoryRegistry`, `PatternRegistry`, `RuleRegistry`, and the orchestrating `FstRegistry`. `FstRegistry` compiles pattern strings into pynini acceptors via `parse_pattern()`, builds sigma/phone/flag universal acceptors, and manages the symbol table. Key method: `FstRegistry.from_config_dir(config_dir)`.
- **`feature_registry.py`** - `Feature`, `FeatureRegistry` (loads `FeatureDefinitions` configs), `FeatureValueCombinations` (expands wildcards/lists into a deduplicated pandas DataFrame of licit combos), `FeatureCombinationsRegistry`, and `FeaturesRegistry` (orchestrates both).
- **`marker_registry.py`** - `Marker` (single morphological formative), `FeatureMarkers` (value→markers map for one feature), `ContingentMarkers` (multi-feature combo→markers, flattened to sorted key strings), plus `FeatureMarkersRegistry`, `ContingentMarkersRegistry`, and `MarkerRegistry` (orchestrates both). Marker types: `prefix`, `suffix`, `replace`, `suppletion`, `rule`.
- **`paradigm_registry.py`** - `ParadigmMarkers` combines `FeatureValueCombinations` + marker objects + contingent marker objects into a lookup table keyed by sorted `"feature=value"` strings. Contingent markers take priority. Marker lists are sorted by `order` stage.

### Web app (`src/web/`)
- **`__init__.py`** - `create_app(config_dir)` Flask factory. Registers `web` blueprint. `CONFIG_DIR` stored in `app.config`.
- **`routes.py`** - Flask Blueprint `web`. Routes:
  - `GET /` — config editor (browse by kind, dedicated UI for Inventory/Patterns/Rules, raw text for others)
  - `POST /config` — save/new/update config actions
  - `GET|POST /parser-test` — test FST patterns against input strings; `FstRegistry` cached per config dir by YAML mtime
  - CRUD routes for inventory nodes, pattern entries, and rule entries
  - Upload session support: users can upload a config dir; a `config_token` identifies the session
- **`configs.py`** - Config file utilities: list/group YAML files by kind, load/save entries, manage upload sessions
- **`inventory.py`** - Inventory editor state management (tree structure, JSON serialization, YAML generation)
- **`patterns.py`** - Patterns editor state management (list structure, JSON serialization, YAML generation)
- **`rules.py`** - Rules editor state management (list structure, JSON serialization, YAML generation)

### Entry point
- **`app.py`** - `python app.py [--config_dir DIR] [--debug]` starts the Flask app.


