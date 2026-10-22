# No relative imports in haybale libraries

**Rule:** code under `barn/` imports its own package absolutely
(`from haybale_graph_editor.settings.node_skin_settings import …`, never
`from ..settings…`). Enforced by ruff `TID252` with `ban-relative-imports = "all"`,
scoped to `barn/**` in `pyproject.toml`. `packages/` is not covered.

**Why:**

- **Hot-reload dependency detection.** `DependencyGraph._resolve_relative_import`
  must look the importing module up in `sys.modules` to know whether it is a
  package (`__init__.py`), because one dot means something different there. A
  module not loaded yet, or mid-reload, resolves one level off — silently, to the
  wrong module or none. Absolute imports need no lookup.
- **Copying code.** Node cloning already has to rewrite relative imports to
  absolute (glossary: Clone). Any other copy path (templates, moving a file
  between haybales) breaks them silently or binds them to the wrong module; a
  broken absolute import fails loudly.
- **Loading by path.** A module loaded with `spec_from_file_location` without a
  package context fails with "attempted relative import with no known parent
  package".
- **Search.** A dotted module path is greppable, and matches string references
  (`patch("haybale_x.y.Z")`) and the `check-rename` skill; `..` hides from all three.

**Cost accepted:** a top-level package rename has to rewrite the imports.
`haywire rename` patches Python sources anyway.

**Not fixed by either style:** `from pkg import submodule` (and `from . import
submodule`) records a dependency on `pkg`, not on `pkg.submodule`.
