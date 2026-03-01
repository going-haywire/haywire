# Documentation Format Specification

This file defines the canonical structure for haybale library documentation. Both the `/docs` agent skill and any future CLI tooling MUST produce output matching these formats exactly.

---

## Output files

For each library, three files plus a per-component doc tree are generated:

```text
libs/haybale-myproject/
├── OVERVIEW.md              # discovery tier — intent-focused node list
├── QUICKREF.md              # usage tier — ports, types, config (machine-optimized)
├── LIBRARY.md               # manual supplement — NEVER overwritten
└── docs/
    ├── nodes/
    │   └── {ClassName}.md   # full detail doc per node
    └── widgets/
        └── {ClassName}.md   # full detail doc per widget
```

`OVERVIEW.md` and `QUICKREF.md` are always regenerated. Per-component docs are only regenerated if the source file has changed (detected via content hash stored in the file).

---

## OVERVIEW.md — Discovery Tier

Purpose: answers "does this library have what I need?" — concise, intent-focused, good for both users and LLMs choosing libraries.

````markdown
# {library_label} 

**({package_name})**

v{version} | By {author}

__{description}__

**Source:** {source_url}
**Dependencies:** {comma-separated from pyproject.toml}
**Tags:** {comma-separated}

---

## Nodes

### {Category Name}

- **{node_label}** (`{node_registry_id}`) — {one-sentence intent: what problem it solves or what it does}
- **{node_label}** (`{node_registry_id}`) — {one-sentence intent}

### {Another Category}

- **{node_label}** (`{node_registry_id}`) — {one-sentence intent}

---

## Types

- **{type_label}** (`{type_registry_id}`) — {one-line description}

---

## Widgets

- **{widget_label}** (`{widget_registry_id}`) — {one-line description}. Compatible: {type_registry_ids}

---

## Adapters

- **{source_type}** → **{target_type}**: {one-line description}

---

## Additional Notes

{Contents of LIBRARY.md verbatim, if the file exists. Otherwise omit this entire section.}
````

### OVERVIEW.md rules

- Node categories come from the first segment of the `menu=` path (e.g., `control/loops` → "Control", `event/runtime` → "Events"), title-cased
- Nodes sorted alphabetically within each category
- One line per node — focus on intent/purpose, not ports
- Omit Types, Widgets, Adapters, Renderers sections if the library has none
- Omit "Additional Notes" if `LIBRARY.md` does not exist
- Renderers are not listed (implementation detail, not user-facing)

---

## QUICKREF.md — Usage Tier

Purpose: answers "how exactly do I use this node?" — compact, token-efficient, complete port/type/config signatures. Renamed from `LIBRARY_LLM.md`.

````markdown
# {package_name} v{version}
# Library ID: {library_id}
# Module: {python_module_name}
# Source: {source_url}
# Dependencies: {comma-separated from pyproject.toml}
# Description: {one_line_description}

## Nodes

### {NodeClassName}
- registry_key: {library_id}:node:{registry_id}
- module: {full.dotted.module.path}
- label: {label}
- menu: {menu_path}
- node_type: {DATA|CONTROL|EVENT|OUTPUT|LOOPBACK}
- description: {one-line description}
- ports:
  - inlet {port_id}: {TYPE_REGISTRY_ID} (default: {value})
  - outlet {port_id}: {TYPE_REGISTRY_ID}
  - config {port_id}: {TYPE_REGISTRY_ID} (default: {value}) -- {brief description}
- dynamic_ports:
  - trigger: {config_port_id} on_change -> {method_name}
  - variations: {one-line description of what changes}

## Types

### {TypeClassName}
- registry_key: {library_id}:type:{registry_id}
- module: {full.dotted.module.path}
- base: {ParentClassName}
- color: {hex_color}
- description: {one-line}

## Widgets

### {WidgetClassName}
- registry_key: {library_id}:widget:{registry_id}
- module: {full.dotted.module.path}
- compatible_types: [{type_registry_ids}]
- description: {one-line}
- config_options: {name: type, name: type, ...}

## Renderers

### {RendererClassName}
- registry_key: {library_id}:renderer:{registry_id}
- module: {full.dotted.module.path}
- is_default: {true|false}
- description: {one-line}

## Adapters

### {AdapterClassName}
- registry_key: {library_id}:adapter:{registry_id}
- module: {full.dotted.module.path}
- converts: {source_type_registry_id} -> {target_type_registry_id}
- description: {one-line}
````

### QUICKREF.md rules

- Header lines starting with `#` (after the title) are comments providing metadata
- All descriptions are one line maximum
- No tables — use flat `- key: value` format
- Omit `dynamic_ports` block entirely if the node has no dynamic behavior
- Omit `(default: ...)` if no default is set
- Omit `config_options` line for widgets if there are none
- Use `--` (double dash) not em-dash for inline separators
- Use `->` not unicode arrows
- Omit empty sections entirely
- Components sorted alphabetically by class name within each section

---

## Per-component docs — Detail Tier

Purpose: full deep-dive on a single component — rendered in the UI side panel when a user selects a node or widget.

Stored at `docs/nodes/{ClassName}.md` and `docs/widgets/{ClassName}.md`. Only nodes and widgets get per-component files (types, renderers, adapters are covered in OVERVIEW and QUICKREF).

### Hash comment (required — enables incremental updates)

The first line of every per-component doc MUST be a hash comment:

```html
<!-- source: {path/relative/to/library/root.py} | sha256: {first-12-chars-of-sha256-hex} -->
```

Example:

```html
<!-- source: haybale_core/nodes/switch.py | sha256: a3f9c1b2d4e5 -->
```

On regeneration: if this hash matches the current hash of the source file, skip the file. Only write if changed or absent.

### Node doc format (`docs/nodes/{ClassName}.md`)

````markdown
<!-- source: {relative_source_path} | sha256: {hash} -->

# {node_label} 

**(`{node_registry_id}`)**

**Category:** {menu} | **Type:** {node_type} | **Library:** {library_id}

{full description from class docstring — can be multi-paragraph}

## Ports

| Direction | Name | Type | Default | Description |
|-----------|------|------|---------|-------------|
| inlet | {port_id} | {TYPE_REGISTRY_ID} | {default_value} | {label or description} |
| config | {port_id} | {TYPE_REGISTRY_ID} | {default_value} | {label or description} |
| outlet | {port_id} | {TYPE_REGISTRY_ID} | | {label or description} |

{sort the ports by direction inlets first, then configs, then outlets, and within each direction by control, data and then callback type}

## Dynamic Behavior

> Only include this section if the node uses `rejig()` or dynamic port patterns.

{Describe in natural language:
- What triggers the reconfiguration (e.g., "Changing the `DataType` config port triggers `hb_change()`")
- Which ports are static (excluded from rejig)
- What the variations look like (e.g., "When set to 'int': adds STRING config `condition` and INT inlets `compare` and `with`; when 'float': same but FLOAT inlets; when 'string': STRING condition options restricted to `==` and `!=`")
}
````

### Widget doc format (`docs/widgets/{ClassName}.md`)

````markdown
<!-- source: {relative_source_path} | sha256: {hash} -->

# {widget_label} (`{widget_registry_id}`)

**Library:** {library_id} | **Compatible types:** {comma-separated type registry_ids}

{full description from class docstring — first paragraph}

Config options:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| {name} | {type} | {default} | {description} |

```python
{usage example from docstring}
```

> If a widget has no config options, replace the Config Options block with "No configuration options."
````

---

## Section ordering rules (OVERVIEW.md and QUICKREF.md)

- Sections appear in this fixed order: Nodes, Types, Widgets, Renderers, Adapters, Additional Notes
- Within each section, components are sorted alphabetically by label (OVERVIEW) or class name (QUICKREF)
- Omit any section that has no components
