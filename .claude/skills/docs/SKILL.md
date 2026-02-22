---
name: docs
description: Generate OVERVIEW.md, QUICKREF.md, and per-component docs for a haybale library. Use when the user wants to generate or update library documentation.
argument-hint: "[library-path]"
---

# Generate Haybale Library Documentation

Generate `OVERVIEW.md` (discovery tier), `QUICKREF.md` (usage reference), and per-component docs under `docs/` for a haybale library.

## 1. Locate the library

If `$ARGUMENTS` is provided, use it as the library path. Otherwise, auto-detect:

- Look for a `libs/` directory in the current working directory
- If exactly one subdirectory in `libs/` contains a `pyproject.toml`, use it
- If multiple exist, ask the user which one to document
- Also accept paths like `libraries/haybale-core` for dev repo libraries

### Determine the module path (critical)

After locating `library_path` (the package root, containing `pyproject.toml`), determine `module_path` — the Python module directory where docs will be written:

- **Flat structure** — if `library_path/__init__.py` exists: `module_path = library_path`
- **Package structure** — if `library_path/pyproject.toml` exists without a top-level `__init__.py`: scan one level deep for a subdirectory that contains `__init__.py`. Use that subdirectory as `module_path`. (E.g., `library_path/haybale_visiongraph/` for haybale-visiongraph.)

All documentation output (OVERVIEW.md, QUICKREF.md, docs/) is written to `module_path`, not `library_path`. Component source files (nodes/, widgets/, etc.) are read from `module_path` subdirectories.

## 2. Sync docstrings (preprocess)

Before generating docs, scan all component source files and ensure their docstrings are complete and accurate. This step runs always and is idempotent — only write a file back if something actually changed.

For each Python file in these subdirectories (recursively):
- `widgets/` — `@widget` decorated classes
- `nodes/` — `@node` decorated classes
- `types/` — `@type` decorated classes
- `renderers/` — `@renderer` decorated classes
- `adapters/` — adapter classes

### Preservation rule (critical)

**Never overwrite an existing description paragraph.** The first paragraph of an existing docstring is human-authored and must be preserved verbatim. Only generate a description if the class has no docstring at all, in which case use the decorator's `description=` field as the first paragraph.

### Widget classes

1. Read `create_element()` and identify every property key consumed from `props = self.config.get('properties', {})`. Look for:
   - `for prop in ['key1', 'key2', ...]:` — explicit prop list
   - `props.get('key', default)` — individual access with default
   - `if 'key' in props:` — conditional access

2. Check whether the docstring already has a `Config options (via ``WidgetClass.config(properties={...})``)` block.

3. **If the block is missing** or **any code prop is absent from the block**:
   - Preserve the existing first paragraph (description)
   - Regenerate the full `Config options` block with one bullet per prop:
     ```
     - ``{key}`` ({type}): {description}. (default: ``{value}``)
     ```
     - **type**: infer from code — `int | float` for numeric props, `str` for string keys like `label`/`color`/`size`, `bool` for flags like `password`/`clearable`
     - **description**: infer from context — prop name + how it's passed to the NiceGUI element
     - **default**: include only if a default is visible in `props.get('key', default)` or the kwargs initializer; omit otherwise
   - Regenerate the `Example::` section with a minimal illustrative call
   - Write the updated docstring back to the file using the Edit tool, replacing only the docstring

4. If an existing prop in the docstring is **no longer in the code**, remove it from the block.

5. If the block is already complete and accurate, skip the file.

### Node classes

1. If the class has no docstring at all, generate a one-paragraph docstring from the decorator's `description=` field and write it back.

2. Do NOT add port lists to node docstrings. Ports are documented in the generated output files, not in source.

### Types, renderers, adapters

1. If no docstring exists, generate a one-line docstring from the decorator `description=` field.
2. Do not add any structured blocks — their metadata comes entirely from decorators.

## 3. Gather data

Read the following sources from the library directory:

### a. Package metadata
Read `pyproject.toml` and extract:
- `[project].name` — package name (e.g., `haybale-core`)
- `[project].version`
- `[project].description`
- `[project].authors[].name`
- `[project].keywords` — used as tags
- `[project].dependencies` — list of pip dependencies

### b. Library identity
Read the `module_path/__init__.py` file and extract fields from the `@library(...)` decorator:
- `id`, `label`, `version`, `description`, `author`, `tags`, `help_url`, `file_watcher`
- The `module_name` is the Python package directory name (e.g., `haybale_core`)

### c. Components
Read ALL Python files in these subdirectories of `module_path` (recursively):
- `nodes/`, `types/`, `widgets/`, `renderers/`, `adapters/`

For EACH decorated class, extract:
- **Decorator arguments** — all keyword arguments
- **Class docstring** — full docstring (now guaranteed complete by step 2)
- **Module path** — full dotted import path (e.g., `haybale_core.nodes.switch`)
- **Source file path** — relative to `module_path` (for hash comments, e.g. `nodes/start_web_cam_stream_node.py`)

### d. Widget config options
Extract from each widget's `Config options (via ...)` docstring block:
- **name**, **type**, **description**, **default** per property
- **usage example** from the `Example::` section

### e. Node ports (critical)
For each `@node` class, read the `init()` method to extract all `self.add()` calls:

```python
self.add(TYPE.as_inlet('port_id', label='Label', default=value, ...))
self.add(TYPE.as_outlet('port_id', label='Label', ...))
self.add(TYPE.as_config('port_id', label='Label', default=value, widget=..., ...))
```

Extract: direction (inlet/outlet/config), port_id, type name, label, default value, widget info, on_change callback.

### f. Dynamic port behavior (important — this is where the skill adds value)
Search each node class for:
- `self.rejig(...)` calls — context manager for port reconfiguration
- `on_change='method_name'` in port definitions — callback triggers
- `post_init()` method — may trigger rejig
- Methods named `hb_reconfigure`, `hb_change`, `hb_rebuild`, or similar

When found, read the full method to understand what triggers it, what changes, and the variations.

### g. Manual supplement
Check if `LIBRARY_EXTRA.md` exists at `module_path/LIBRARY_EXTRA.md`. If so, include its contents verbatim in the "Additional Notes" section of `OVERVIEW.md`. NEVER modify or overwrite this file.

### h. Compute source hashes
For each node and widget source file, compute `sha256(file_content)` and take the first 12 hex characters. Store alongside the component data for use in per-component doc headers.

## 4. Generate documentation

Write output files using the exact canonical formats defined in [format-spec.md](format-spec.md).

### 4a. OVERVIEW.md (always regenerate)

Write to `module_path/OVERVIEW.md`.

- Group nodes by the first segment of their `menu=` path, title-cased (e.g., `control/loops` → "Control", `event/runtime` → "Events")
- One bullet per node: `- **{label}** (`{registry_id}`) — {intent sentence}`
- Intent sentence: what the node does or solves, NOT its ports — use the class docstring first sentence
- List types, widgets, adapters as flat bullet lists
- Renderers are omitted (implementation detail)
- Include "Additional Notes" section only if `LIBRARY_EXTRA.md` exists

### 4b. QUICKREF.md (always regenerate)

Write to `module_path/QUICKREF.md`.

- Compact key-value format, no tables, one line per field
- Include `# Source: {source_url}` header line if available
- Alphabetical by class name within each section

### 4c. Per-component docs (incremental)

Write to `module_path/docs/nodes/{ClassName}.md` and `module_path/docs/widgets/{ClassName}.md`.

For each node and widget:

1. Compute the sha256 hash of the source `.py` file (first 12 hex chars)
2. Check if `module_path/docs/nodes/{ClassName}.md` (or `docs/widgets/`) exists
3. If the file exists, read its first line and parse the stored hash
4. **If hashes match**: skip this component — do not write
5. **If hashes differ or file is absent**: write the full component doc with the hash comment as the first line

The hash comment format is: `<!-- source: {relative/path.py} | sha256: {12-char-hash} -->`
where `{relative/path.py}` is relative to `module_path` (e.g. `nodes/start_web_cam_stream_node.py`).

Create `module_path/docs/nodes/` and `module_path/docs/widgets/` directories as needed.

### Rules
- Always overwrite `module_path/OVERVIEW.md` and `module_path/QUICKREF.md` completely
- Per-component docs: only write if hash has changed or file is absent (idempotent)
- NEVER modify or overwrite `LIBRARY_EXTRA.md`
- Use the type's `registry_id` for port types (e.g., `FLOAT`, `INT`, `Image`), not the Python class name
- For `registry_key`, use `{library_id}:{component_type}:{registry_id}` — registry_id defaults to class name if not set in decorator
- Dynamic port behavior: natural language description of triggers, static ports, and variations
- Keep QUICKREF descriptions to one line; put detail in component docs
