# Implementation Brief: JSON Config Editor (PoC)

## Context

The grammar/config logic (`src/config_utils/config_walker.py`'s `ConfigWalker`, `src/config_utils/schema_validation.py`'s `load_schema`) already exists and reads/validates **YAML** config files against JSON Schemas in `config/schemas/`. The FastAPI backend does **not** exist yet — it needs to be built from scratch as a thin HTTP wrapper around this existing logic. We need a minimal browser-based editor for these config files with schema-driven validation, autocompletion, and template insertion.

## Decisions

- **On-disk format stays YAML.** The backend reads/writes the existing `.yaml` files under `CONFIG_DIR`; it converts to JSON only at the API boundary (response bodies are JSON, files on disk remain YAML).
- **Validate on write.** `PUT /file` validates the incoming JSON against `load_schema(kind)` (reusing the existing `jsonschema` validation already used by `ConfigWalker.read_config_files`) before writing. Invalid writes return 400 with the `ValidationError` message.
- **Single config dir per process.** Like `ConfigWalker`, the backend operates on one `CONFIG_DIR` (from `.env`/env var) for its whole lifetime — no per-request language switching.
- **Combined app.** This FastAPI app serves both the JSON API and the static `frontend/` files (one process, one port).

## Stack

- **Frontend:** Vanilla JS ES modules, no build step. `vanilla-jsoneditor` and its bundled AJV validator via CDN.
- **Backend:** FastAPI (new). Single-file app, barebones — no auth, no multi-user/concurrency handling beyond basic file I/O.

---

## File Structure

```
frontend/
├── index.html
├── main.js        # entry point, owns openFile()
├── editor.js      # JSONEditor lifecycle only
├── schema.js      # schema fetching, cross-ref resolution, live enum patching
├── templates.js   # TEMPLATES constant + renderTemplateSidebar()
├── api.js         # all fetch() calls, one function per endpoint
└── style.css

src/
└── api.py         # new FastAPI app; the 4 endpoints below + static mount
```

`config/schemas/*.json` (existing) and `config/<lang>/<kind_dir>/*.yaml` (existing, read via `CONFIG_DIR`) are reused as-is — no new schema or config files needed for the PoC.

---

## Backend: `src/api.py` (new, 4 endpoints)

```python
GET  /schemas/{kind}        # load_schema(kind) -> JSON
GET  /configs?kind={kind}   # ConfigWalker.glob_config_files(kind) -> ["$path", ...]
GET  /file?path={path}      # yaml.safe_load(path) -> JSON
PUT  /file?path={path}      # validate JSON body against load_schema(kind), then yaml.safe_dump(path)
```

Implementation notes:

- `CONFIG_DIR` is resolved once at startup the same way `ConfigWalker`/`get_config_dir()` do.
- `path` query params are file paths; resolve and confirm they stay inside `CONFIG_DIR` before any read/write (basic traversal guard — no other auth).
- `/configs?kind={kind}` reuses `ConfigWalker.glob_config_files(kind)` and returns `$`-prefixed stem names (e.g. `$rules/verbal`), matching the reference convention `ConfigWalker.resolve_ref` already expects.
- `/file` GET/PUT convert YAML ↔ JSON at the boundary only — `yaml.safe_load`/`yaml.safe_dump`, never `json.load`/`json.dump`, since the files on disk are YAML.
- `PUT /file` reads `kind` from the JSON body, calls `load_schema(kind)`, and runs `jsonschema.validate` before writing; on `ValidationError`, return HTTP 400 with the message (don't write the file).
- Mount `frontend/` as static files at `/` (`StaticFiles(directory="frontend", html=True)`).

---

## Frontend: module responsibilities

**`api.js`** — only file that knows the server exists:

```js
export const fetchSchema = (kind) => ...   // GET /schemas/{kind}
export const fetchRefs = (kind) => ...     // GET /configs?kind=
export const readFile = (path) => ...      // GET /file
export const writeFile = (path, json) => ... // PUT /file
```

**`schema.js`** — only file that knows schema conventions:

- `getSchema(kind)` — fetches and caches schemas
- `patchRefEnums(schema, kind)` — clones schema and injects live filesystem enums into fields that use `$`-prefixed references. Only two cases matter for PoC:
  - `MorphemeSequence.data[].value` — `oneOf` branch per kind (`Rule`, `Paradigm`, etc.), each with `enum` from `fetchRefs(kind)`
  - `Paradigm.feature_markers` — `additionalProperties.oneOf[0].enum` from `fetchRefs('FeatureMarkers')`
- `buildSchemaDefinitions()` — returns `{ './FeatureMarkers.json': schema, ... }` map for cross-file `$ref` resolution (needed because `Paradigm.json` references `./FeatureMarkers.json#/definitions/marker`)

**`templates.js`** — only file that knows what sub-objects each kind contains:

```js
export const TEMPLATES = {
  MorphemeSequence: [
    { label: "data item", value: { kind: "Rule", value: "" } },
  ],
  Paradigm: [
    { label: "global marker", value: { kind: "suffix", value: "" } },
    { label: "filter", value: { lexical_features: [], pattern: "" } },
  ],
  FeatureMarkers: [
    { label: "marker", value: { kind: "suffix", value: "" } },
  ],
  Inventory: [
    { label: "inventory node", value: { name: "", _ref: "<>", _phones: [] } },
    { label: "child node", value: { name: "", _children: [] } },
  ],
};

export function renderTemplateSidebar(kind, onInsert) { ... }
// Renders only TEMPLATES[kind] into #template-list as buttons
```

**`editor.js`** — only file that imports from vanilla-jsoneditor. Exports:

- `mountEditor(target, content, schema, schemaDefinitions)` — creates editor instance
- `getContent()` — returns current JSON
- `insertTemplate(value)` — reads current JSON, appends value to `data[]` if it's a data-item shape, else merges at root, calls `editor.update()`

**`main.js`** — owns the sequence, delegates everything:

```
openFile(path):
  readFile(path)
  getSchema(kind) + patchRefEnums()
  buildSchemaDefinitions()
  mountEditor(...)
  renderTemplateSidebar(kind, insertTemplate)

saveFile():
  getContent() → writeFile(path, json)
```

---

## Key implementation notes

1. **Schema descriptions are free.** `vanilla-jsoneditor` in tree mode renders `description` fields from the schema as tooltips automatically. No extra work needed.

2. **`schemaDefinitions` is required.** `Paradigm.json` has a cross-file `$ref` to `./FeatureMarkers.json#/definitions/marker`. Pass the definitions map as the `schemaDefinitions` prop to both the editor and `createAjvValidator`, otherwise validation silently fails on those fields.

3. **`additionalProperties` objects won't get key suggestions.** `markers` in FeatureMarkers and `feature_markers` in Paradigm have open-ended string keys (linguistic feature names). The editor validates values against the schema but cannot suggest keys. This is expected and acceptable for the PoC.

4. **Templates are plain objects, not derived from the schema.** Do not attempt to recurse the schema to generate templates. The templates are shallow and domain-specific; just write them out explicitly in `TEMPLATES`.

5. **`kind` is the only dispatch key.** Every branching decision — which schema to load, which templates to show, which fields to patch — is driven by `fileData.kind`, which is present in every config.

6. **One editor instance at a time.** `editor.js` holds a module-level reference. `mountEditor` calls `editor.destroy()` before creating a new one.

---

## HTML structure

```
body
├── #sidebar
│   ├── #file-list      (populated from GET /configs for all kinds at startup)
│   └── #template-list  (repopulated on each openFile)
└── #main
    ├── #toolbar         (Save button)
    └── #editor          (JSONEditor mount point)
```
