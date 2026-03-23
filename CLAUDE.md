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



## Prompt
You are a helpful prompt engineer.
Create a prompt for an LLM to implement the following change: I want to edit the Paradigm form @src/web/paradigms.py @src/web/templates/_paradigm_editor.html to use a sequence of dropdown menus for the 'lexical features' input field rather than a single text input.
Each row in the form data has a pair of      
dropdowns: the first selects a Feature name, the second a Feature value.
Features names and values are fetched from the `GrammarRegistry` class in @src/web/routes.py, which is done elsewhere in @src/web/paradigms.py already.
The logic for managing a mutable sequence of dropdown lists in the form should mimic the code in @src/web/templates/_marker_list_editor.html and @src/web/markers.py, and should avoid duplicating logic that already exists.
To whatever extent possible, be proactive and move logic that already exists to a centralized location and inherit for both the marker list editor and the new feature list editor.

The expected format for output is a list of couples, i.e. [(feature name, feature value)].
See @src/registry/grammar_registry.py for implementation details, and @config/tira/paradigms/README.md and @config/schemas/Paradigm.json for the expected YAML format.

While you're at it, make the 'Pattern' input field also a dropdown.
It should give a list over all patterns, accessible via `GrammarRegistry.FstRegistry.patterns`.
See @src/registry/FstRegistry.py for details.
Add a checkbox that lets the user toggle between selecting a pattern from the dropdown list and letting the user input their own text.
If no patterns are detected, keep the dropdown grayed out and display a warning that no patterns were found.

I am the backend engineer.
Ask any questions you have on the backend logic, especially if anything looks inconsistent to you.
Once you're done, give me a prompt that contains all the context the frontend engineer will need to implement this.