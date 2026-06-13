# CodeMirror Code Intelligence — Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the jedi-backed CodeMirror autocompletion + hover-documentation feature out of `ComponentSourceEditor` into a reusable, language-gated helper in `haywire-core`, backed by an editor-agnostic `code_intelligence` provider in `haywire-studio`, and wire it into both real code editors.

**Architecture:** Two halves, cleanly layered. (1) A **provider** — `haywire_studio.code_intelligence` — registers three jedi-backed HTTP endpoints that take editor text + cursor position and return **plain structured data in jedi's own vocabulary** (no CodeMirror types, no `boost`, no HTML). (2) An **element-aspect helper** — `haywire.ui.components.codemirror` — that attaches completion + hover to any `ui.codemirror`, owning *all* CodeMirror-specific translation (jedi-kind → CM type, the `boost` sort policy, markdown→HTML rendering, the `hw-cm-doc` class, the mount-poll + `appendConfig` injection). The helper's completion source reads the live CodeMirror language and **no-ops unless the language is in a caller-supplied filter** (default `('Python',)`), so it is safe on the polymorphic `CodeEditor` (TOML/JSON/Markdown/plain-text files simply get no intelligence).

**Tech Stack:** Python 3.11+, NiceGUI 3.x (`ui.codemirror`, `ui.run_javascript`), jedi (provider), markdown2 + pygments (doc rendering, now in core), FastAPI routes via `nicegui.app.post`, CodeMirror 6 autocomplete/hover-tooltip extensions (injected JS).

---

## Background & Key Decisions (read before starting)

This plan is the output of a design interview. The decisions below are settled — do **not** re-litigate them:

- **Goal:** reuse across CodeMirror surfaces.
- **Provider stays in `haywire-studio`; element moves to `haywire-core`.** Verified: `haywire-core` never imports `haywire_studio` (layering holds). The element must not import anything studio-specific.
- **Provider is editor-agnostic** (jedi-in, plain-data-out). All CodeMirror knowledge — `type` mapping, `boost`, markdown→HTML, CSS class — lives in the **element**.
- **Provider renamed** `completion.py` → `code_intelligence.py`; the user-facing concept is "code intelligence" (completion + hover + future go-to-def), not just "completion".
- **Helper shape:** a free function `attach_code_intelligence(editor, *, ...)`, NOT a `ui.codemirror` subclass. Call sites keep constructing `ui.codemirror` exactly as they do today and bolt intelligence on.
- **Polymorphic-language handling:** the JS completion source + hover source read the editor's live language and return `null` (no fetch) unless the language is in `language_filter`. Attach once; self-silences for non-Python. No teardown logic.
- **Scope of rewiring:** `ComponentSourceEditor` **and** `CodeEditor`. NOT the read-only error display ([haywire_exception.py:150](../../../packages/haywire-core/src/haywire/ui/errors/haywire_exception.py#L150)) — completion on uneditable traceback source has no value.
- **OUT OF SCOPE (tracked separately, do not touch here):** the NiceGUI bundle `export * from "@codemirror/autocomplete"` change, the upstream PR, and replacing the `cp -r` site-packages hack with a proper editable install. This plan **assumes the bundle already exports the autocomplete + hoverTooltip symbols** (it does, in the dev environment).
- **Glossary already updated** with the "component" overload note — no doc work needed there.

### The wire contract (provider ⇄ element)

The provider returns **plain data in jedi's vocabulary**. The element translates to CodeMirror.

`POST /api/code-intel/complete` — request `{code, line, column, path, explicit}` → response:
```json
{"completions": [{"name": "add", "kind": "function", "signature": "add(spec: ...) -> DataPort", "docstring": "Add a port ..."}]}
```
(`kind` is jedi's raw `Completion.type` string. `signature`/`docstring` are plain text. NO `type`, NO `boost`, NO HTML.)

`POST /api/code-intel/info` — request `{code, line, column, path, label}` → response:
```json
{"signature": "add(spec: ...) -> DataPort", "docstring": "Add a port ..."}
```

`POST /api/code-intel/hover` — request `{code, line, column, path}` → response:
```json
{"signature": "...", "docstring": "..."}
```

(Endpoints renamed from the prototype's `/api/complete*` + `/api/hover` to namespaced `/api/code-intel/*` so the routes read as belonging to this subsystem and won't collide with future app routes.)

### Current prototype locations (what exists today, to be moved/replaced)

- `packages/haywire-studio/src/haywire_studio/completion.py` — prototype provider (returns CM-typed + HTML). **Will be rewritten** into `code_intelligence.py`.
- `packages/haywire-studio/src/haywire_studio/app.py` — calls `register_completion_endpoint()`. **Will be updated** to the new name.
- `barn/haybale-studio/haybale_studio/editors/component_source_editor.py` — contains `_inject_completions` (~110 lines of injected JS). **Will be gutted** and replaced with a one-line helper call.
- `packages/haywire-core/src/haywire/ui/app/shell.py` — has the `.hw-cm-doc` + pygments CSS (`_pygments_doc_css()`). **Stays** (already in core, already correct).
- `packages/haywire-core/pyproject.toml` — does NOT declare `markdown2`/`pygments` (currently transitive via nicegui). **Will add them.**

---

## File Structure

**Create:**
- `packages/haywire-core/src/haywire/ui/components/codemirror/__init__.py` — exports `attach_code_intelligence`.
- `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py` — the helper: `attach_code_intelligence(editor, *, completion_url, info_url, hover_url, language_filter)`, plus the CM-translation helpers (`_jedi_kind_to_cm_type`, `_boost`, `_render_doc_html`) moved here from the studio prototype.
- `packages/haywire-studio/src/haywire_studio/code_intelligence.py` — the provider: `register_code_intelligence_endpoints()` + pure helpers (`_signature_and_doc`).
- `tests/ui/components/codemirror/test_code_intelligence_translation.py` — unit tests for the element's pure CM-translation helpers.
- `tests/studio/test_code_intelligence_provider.py` — unit tests for the provider's pure helpers + endpoint shape.

**Modify:**
- `packages/haywire-core/pyproject.toml` — add `markdown2`, `pygments` to dependencies.
- `packages/haywire-studio/src/haywire_studio/app.py` — call `register_code_intelligence_endpoints()`.
- `barn/haybale-studio/haybale_studio/editors/component_source_editor.py` — replace `_inject_completions` body with helper call; drop dead code.
- `barn/haybale-studio/haybale_studio/editors/code_editor.py` — attach the helper in `_make_codemirror`.

**Delete:**
- `packages/haywire-studio/src/haywire_studio/completion.py` (after `code_intelligence.py` replaces it).

---

## A note on testing strategy (read this)

Most of this feature is **CodeMirror extension logic injected as a JavaScript string via `ui.run_javascript`**. There is no Python seam to unit-test for the injected JS — asserting against a string blob tests nothing real. So this plan uses:

- **TDD (real pytest) for the pure Python functions**: the provider's jedi-result → `{signature, docstring}` extraction, and the element's `kind`→CM-type / `boost` / markdown→HTML translation. These are deterministic and worth locking down.
- **Manual verification steps in the running app** for the injected-JS behavior (completion popup, doc panel, hover tooltip, language-gating). Each such step says exactly what to do and what you must observe. Do not skip them — they are the only real test of the JS.

Run the app with: `uv run haywire` (from repo root). Open the **Component Source** editor (right slot) for a node, and the **Code** editor for a file.

---

## Task 1: Declare markdown2 + pygments as core dependencies

The element will `import markdown2` (and pygments is pulled by markdown2's fenced-code-blocks). Core currently gets both transitively via nicegui — relying on that is fragile and `/haywire-dep-check` would flag it.

**Files:**
- Modify: `packages/haywire-core/pyproject.toml`

- [ ] **Step 1: Add the dependencies**

In `packages/haywire-core/pyproject.toml`, change the `dependencies` list from:

```toml
dependencies = [
    "nicegui>=3.12.1",
    "watchdog>=6.0.0",
    "injector>=0.22.0",
    "attrs==25.4.0",
    "cattrs==25.3.0",
    "toml>=0.10.2",
    "packaging",
    "typing_extensions",
]
```

to (add the two lines):

```toml
dependencies = [
    "nicegui>=3.12.1",
    "watchdog>=6.0.0",
    "injector>=0.22.0",
    "attrs==25.4.0",
    "cattrs==25.3.0",
    "toml>=0.10.2",
    "packaging",
    "typing_extensions",
    "markdown2>=2.5",
    "pygments>=2.18",
]
```

- [ ] **Step 2: Verify they resolve and import**

Run: `uv run python -c "import markdown2, pygments; print('ok', markdown2.__version__, pygments.__version__)"`
Expected: `ok 2.5.4 2.20.0` (or newer)

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/pyproject.toml
git commit -m "build(core): declare markdown2 + pygments as explicit deps"
```

---

## Task 2: Element-side CM-translation helpers (TDD)

These pure functions move from the studio prototype into the **element** (core), because all CodeMirror knowledge lives in the element now. They turn jedi's vocabulary into CodeMirror's: `kind`→`type`, name→`boost`, and `(signature, docstring)`→HTML.

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/components/codemirror/__init__.py`
- Create: `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py`
- Test: `tests/ui/components/codemirror/test_code_intelligence_translation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/components/codemirror/test_code_intelligence_translation.py`:

```python
"""Unit tests for the element-side CodeMirror translation helpers."""

from __future__ import annotations

import haywire.core.graph.editor  # noqa: F401  (import-order guard per CLAUDE.md)

from haywire.ui.components.codemirror.code_intelligence import (
    _jedi_kind_to_cm_type,
    _boost,
    _render_doc_html,
)


def test_jedi_kind_maps_known_types():
    assert _jedi_kind_to_cm_type("function") == "function"
    assert _jedi_kind_to_cm_type("class") == "class"
    assert _jedi_kind_to_cm_type("module") == "namespace"
    assert _jedi_kind_to_cm_type("instance") == "variable"


def test_jedi_kind_unknown_falls_back_to_text():
    assert _jedi_kind_to_cm_type("nonsense") == "text"


def test_boost_orders_public_over_private_over_dunder():
    assert _boost("add") == 1
    assert _boost("_internal") == -1
    assert _boost("__dunder__") == -2


def test_render_doc_html_wraps_signature_in_python_codeblock():
    html = _render_doc_html("add(spec) -> DataPort", "Add a port.")
    # signature becomes a fenced python block -> pygments codehilite wrapper
    assert "codehilite" in html
    assert "Add a port." in html


def test_render_doc_html_empty_returns_empty_string():
    assert _render_doc_html(None, None) == ""


def test_render_doc_html_preserves_docstring_line_structure():
    # break-on-newline keeps Args:/bullets on their own lines
    doc = "Summary.\n\nArgs:\n    spec: the spec\n- bullet one\n- bullet two"
    html = _render_doc_html(None, doc)
    assert "<br" in html  # single newlines became <br/>


def test_render_doc_html_does_not_italicize_underscored_identifiers():
    # code-friendly extra: as_inlet must NOT become as<em>inlet
    html = _render_doc_html(None, "Uses FLOAT.as_inlet() here.")
    assert "as_inlet" in html
    assert "as<em>inlet" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/components/codemirror/test_code_intelligence_translation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.ui.components.codemirror'`

- [ ] **Step 3: Create the package `__init__.py`**

Create `packages/haywire-core/src/haywire/ui/components/codemirror/__init__.py`:

```python
from haywire.ui.components.codemirror.code_intelligence import attach_code_intelligence

__all__ = ["attach_code_intelligence"]
```

- [ ] **Step 4: Write the translation helpers**

Create `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py` with the pure helpers (the `attach_code_intelligence` function is added in Task 4 — for now define a placeholder so the `__init__` import succeeds):

```python
"""Reusable CodeMirror code-intelligence aspect.

Attaches jedi-backed completion + hover documentation to any ``ui.codemirror``
element by injecting CodeMirror autocomplete + hoverTooltip extensions that call
an editor-agnostic HTTP provider. ALL CodeMirror-specific knowledge lives here:
jedi-kind -> CM completion ``type``, the ``boost`` sort policy, markdown -> HTML
doc rendering, and the ``hw-cm-doc`` panel class. The provider returns only plain
data in jedi's own vocabulary.

The completion/hover sources read the editor's live language and no-op unless it
is in ``language_filter`` (default ``("Python",)``), so this is safe to attach to
a polymorphic editor that also opens TOML/JSON/Markdown/plain-text files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import markdown2

if TYPE_CHECKING:
    from nicegui import ui

# break-on-newline keeps the line structure of plain-text Python docstrings
# (Args:/Returns:/bullets on their own lines); code-friendly stops underscores
# in identifiers (as_inlet) being parsed as emphasis.
_MD_EXTRAS = ["fenced-code-blocks", "tables", "code-friendly", "break-on-newline"]


def _jedi_kind_to_cm_type(kind: str) -> str:
    """Map a jedi ``Completion.type`` string to a CodeMirror completion type."""
    return {
        "function": "function",
        "class": "class",
        "module": "namespace",
        "instance": "variable",
        "keyword": "keyword",
        "property": "property",
        "param": "variable",
        "path": "text",
        "statement": "variable",
    }.get(kind, "text")


def _boost(name: str) -> int:
    """CodeMirror sort hint: public > private > dunder."""
    if name.startswith("__"):
        return -2
    if name.startswith("_"):
        return -1
    return 1


def _render_doc_html(signature: str | None, docstring: str | None) -> str:
    """Render a signature + docstring into highlighted HTML for the doc panel.

    The signature is wrapped in a fenced Python block so markdown2's
    fenced-code-blocks extra (with pygments) highlights it; the docstring is
    rendered as markdown prose.
    """
    parts: list[str] = []
    if signature:
        parts.append(f"```python\n{signature}\n```")
    if docstring:
        parts.append(docstring)
    if not parts:
        return ""
    return markdown2.markdown("\n\n".join(parts), extras=_MD_EXTRAS)


def attach_code_intelligence(
    editor: "ui.codemirror",
    *,
    completion_url: str = "/api/code-intel/complete",
    info_url: str = "/api/code-intel/info",
    hover_url: str = "/api/code-intel/hover",
    language_filter: Sequence[str] = ("Python",),
    path: str | None = None,
) -> None:
    """Placeholder — real implementation added in Task 4."""
    raise NotImplementedError
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/components/codemirror/test_code_intelligence_translation.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/codemirror/ tests/ui/components/codemirror/
git commit -m "feat(core): add CodeMirror translation helpers for code intelligence"
```

---

## Task 3: Rewrite the provider as editor-agnostic `code_intelligence` (TDD)

Replace the studio prototype with a provider that returns **plain jedi data**: no CM `type`, no `boost`, no HTML. Pure helper `_signature_and_doc` is unit-tested; endpoints are thin wrappers over jedi.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/code_intelligence.py`
- Test: `tests/studio/test_code_intelligence_provider.py`
- (Delete `completion.py` happens in Task 5 after app.py is switched.)

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_code_intelligence_provider.py`:

```python
"""Unit tests for the jedi-backed code-intelligence provider helpers."""

from __future__ import annotations

import jedi

from haywire_studio.code_intelligence import _signature_and_doc, _completion_payload


def test_completion_payload_returns_plain_jedi_vocabulary():
    code = "import os\nos."
    script = jedi.Script(code)
    completions = script.complete(2, 3)
    payload = _completion_payload(completions, explicit=False)
    assert payload  # os has many attributes
    first = payload[0]
    # plain data only: name + kind + signature + docstring, NO type/boost/html
    assert set(first.keys()) == {"name", "kind", "signature", "docstring"}
    assert "<" not in first["docstring"]  # not HTML


def test_completion_payload_filters_dunders_when_not_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=False)}
    assert not any(n.startswith("__") for n in names)


def test_completion_payload_keeps_dunders_when_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=True)}
    assert any(n.startswith("__") for n in names)


def test_signature_and_doc_returns_plain_text():
    code = "def greet(name: str) -> str:\n    '''Say hello.'''\n    return name\ngreet"
    names = jedi.Script(code).help(4, 5)
    sig, doc = _signature_and_doc(names[0])
    assert "greet(name" in sig
    assert "Say hello." in doc
    assert "<" not in sig and "<" not in doc  # plain text, not HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/studio/test_code_intelligence_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.code_intelligence'`

- [ ] **Step 3: Write the provider**

Create `packages/haywire-studio/src/haywire_studio/code_intelligence.py`:

```python
"""Jedi-backed code-intelligence provider (editor-agnostic).

Registers three HTTP endpoints that take editor text + cursor position and
return PLAIN structured data in jedi's own vocabulary. NO CodeMirror types,
NO boost, NO HTML — all of that is the consuming element's concern (see
haywire.ui.components.codemirror).
"""

from __future__ import annotations

import logging
from typing import Any

import jedi
from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app

logger = logging.getLogger(__name__)


def _signature_and_doc(name: "jedi.api.classes.BaseName") -> tuple[str, str]:
    """Extract a plain-text signature + docstring from a jedi name."""
    signatures = [s.to_string() for s in name.get_signatures()]
    signature = "\n".join(signatures) if signatures else (name.description or "")
    doc = name.docstring(raw=True) or ""
    return signature, doc


def _completion_payload(
    completions: "list[jedi.api.classes.Completion]", *, explicit: bool
) -> list[dict[str, str]]:
    """Turn jedi completions into plain data; filter dunders unless explicit."""
    if not explicit:
        completions = [c for c in completions if not c.name.startswith("__")]
    payload: list[dict[str, str]] = []
    for c in completions:
        signatures = [s.to_string() for s in c.get_signatures()]
        payload.append(
            {
                "name": c.name,
                "kind": c.type,  # jedi's raw type string
                "signature": "\n".join(signatures),
                "docstring": c.docstring(raw=True) or "",
            }
        )
    return payload


def register_code_intelligence_endpoints() -> None:
    @app.post("/api/code-intel/complete")
    async def complete(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            script = jedi.Script(body.get("code", ""), path=body.get("path"))
            completions = script.complete(
                int(body.get("line", 1)), int(body.get("column", 0)), fuzzy=False
            )
            return JSONResponse(
                {"completions": _completion_payload(completions, explicit=bool(body.get("explicit")))}
            )
        except Exception:
            logger.debug("code-intel complete failed", exc_info=True)
            return JSONResponse({"completions": []})

    @app.post("/api/code-intel/info")
    async def info(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            script = jedi.Script(body.get("code", ""), path=body.get("path"))
            label = body.get("label", "")
            for c in script.complete(
                int(body.get("line", 1)), int(body.get("column", 0)), fuzzy=False
            ):
                if c.name == label:
                    sig, doc = _signature_and_doc(c)
                    return JSONResponse({"signature": sig, "docstring": doc})
            return JSONResponse({"signature": "", "docstring": ""})
        except Exception:
            logger.debug("code-intel info failed", exc_info=True)
            return JSONResponse({"signature": "", "docstring": ""})

    @app.post("/api/code-intel/hover")
    async def hover(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            script = jedi.Script(body.get("code", ""), path=body.get("path"))
            names = script.help(int(body.get("line", 1)), int(body.get("column", 0)))
            if not names:
                return JSONResponse({"signature": "", "docstring": ""})
            sig, doc = _signature_and_doc(names[0])
            return JSONResponse({"signature": sig, "docstring": doc})
        except Exception:
            logger.debug("code-intel hover failed", exc_info=True)
            return JSONResponse({"signature": "", "docstring": ""})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/studio/test_code_intelligence_provider.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/code_intelligence.py tests/studio/test_code_intelligence_provider.py
git commit -m "feat(studio): editor-agnostic jedi code-intelligence provider"
```

---

## Task 4: Implement `attach_code_intelligence` (the injected-JS helper)

Replace the placeholder from Task 2 with the real injection. This is the JS that was inline in `ComponentSourceEditor`, now: (a) parameterized by endpoint URLs, (b) using the element-side `_jedi_kind_to_cm_type` / `_boost` / `_render_doc_html` to build CM options server-of-the-element-side **in Python** before injection where possible, and (c) **language-gated** — the completion source and hover source read the live CM language and bail unless it's in `language_filter`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py` (replace the `attach_code_intelligence` placeholder)

- [ ] **Step 1: Replace the placeholder implementation**

In `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py`, replace the entire placeholder `attach_code_intelligence` function (the one that does `raise NotImplementedError`) with:

```python
def attach_code_intelligence(
    editor: "ui.codemirror",
    *,
    completion_url: str = "/api/code-intel/complete",
    info_url: str = "/api/code-intel/info",
    hover_url: str = "/api/code-intel/hover",
    language_filter: Sequence[str] = ("Python",),
    path: str | None = None,
) -> None:
    """Attach jedi-backed completion + hover documentation to ``editor``.

    The injected sources read the editor's live language name and no-op unless
    it is in ``language_filter``. ``path`` (the file path of the edited buffer)
    is forwarded to the provider so jedi can resolve imports relative to it.

    Must be called after ``editor`` is constructed (typically right after, in the
    same draw); the JS polls for the element + its ``editorPromise`` before
    wiring, so it tolerates being called before the client has mounted it.
    """
    from nicegui import ui

    editor_id = editor.id
    path_js = "null" if path is None else f'"{path}"'
    # JSON array of allowed CodeMirror language names, e.g. ["Python"].
    import json

    langs_js = json.dumps(list(language_filter))

    ui.run_javascript(_INJECTION_JS.format(
        editor_id=editor_id,
        completion_url=completion_url,
        info_url=info_url,
        hover_url=hover_url,
        path_js=path_js,
        langs_js=langs_js,
    ))
```

- [ ] **Step 2: Add the injection JS template at module bottom**

Append to the same file. Note: this template uses **doubled braces** `{{ }}` for literal JS braces because it is consumed by `str.format()`; the only single-brace fields are `{editor_id}`, `{completion_url}`, `{info_url}`, `{hover_url}`, `{path_js}`, `{langs_js}`.

```python
# CodeMirror autocomplete + hoverTooltip injection. Consumed by str.format();
# literal JS braces are doubled. The completion/hover sources read the live
# language from the editor's syntax tree config and no-op unless it is one of
# {langs_js}. The provider returns plain {{name, kind, signature, docstring}};
# this JS does the CM translation client-side (type via a small inline map,
# boost via public/private/dunder, doc HTML is requested from /info lazily).
_INJECTION_JS = r"""
const CM = await import('nicegui-codemirror');
let el;
for (let i = 0; i < 50; i++) {{
    el = getElement({editor_id});
    if (el) break;
    await new Promise(r => setTimeout(r, 100));
}}
if (!el) return;
const editor = await el.editorPromise;

const ALLOWED_LANGS = {langs_js};
const KIND_TO_TYPE = {{
    function: 'function', class: 'class', module: 'namespace',
    instance: 'variable', keyword: 'keyword', property: 'property',
    param: 'variable', path: 'text', statement: 'variable',
}};
function boost(name) {{
    if (name.startsWith('__')) return -2;
    if (name.startsWith('_')) return -1;
    return 1;
}}
// Read the active language display name from the loaded CM language facet.
function activeLanguageName(state) {{
    const lang = state.facet(CM.language);
    return lang && lang.name ? lang.name : null;
}}
function languageAllowed(state) {{
    // CM language facet names are lowercase (e.g. "python"); compare loosely.
    const name = activeLanguageName(state);
    if (!name) return false;
    return ALLOWED_LANGS.some(l => l.toLowerCase() === name.toLowerCase());
}}

async function haywireComplete(context) {{
    if (!languageAllowed(context.state)) return null;
    const word = context.matchBefore(/\w*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;

    const state = editor.state;
    const pos = state.selection.main.head;
    const doc = state.doc;
    const line = doc.lineAt(pos);

    const resp = await fetch('{completion_url}', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            code: doc.toString(), line: line.number,
            column: pos - line.from, path: {path_js}, explicit: context.explicit,
        }})
    }});
    const data = await resp.json();
    if (!data.completions || !data.completions.length) return null;

    const reqLine = line.number;
    const reqCol = pos - line.from;
    const options = data.completions.map(c => ({{
        label: c.name,
        type: KIND_TO_TYPE[c.kind] || 'text',
        detail: c.signature || '',
        boost: boost(c.name),
        info: async () => {{
            const r = await fetch('{info_url}', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    code: doc.toString(), line: reqLine, column: reqCol,
                    path: {path_js}, label: c.name,
                }})
            }});
            const j = await r.json();
            return renderDocPanel(j.signature, j.docstring);
        }},
    }}));
    return {{ from: word.from, options }};
}}

const haywireHover = CM.hoverTooltip(async (view, pos, side) => {{
    if (!languageAllowed(view.state)) return null;
    const doc = view.state.doc;
    const lineObj = doc.lineAt(pos);
    const text = doc.toString();
    let start = pos, end = pos;
    while (start > 0 && /[\w.]/.test(text[start - 1])) start--;
    while (end < text.length && /[\w]/.test(text[end])) end++;
    if (start === end) return null;

    const resp = await fetch('{hover_url}', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            code: text, line: lineObj.number,
            column: pos - lineObj.from, path: {path_js},
        }})
    }});
    const j = await resp.json();
    const panel = renderDocPanel(j.signature, j.docstring);
    if (!panel) return null;
    return {{ pos: start, end, above: true, create: () => ({{ dom: panel }}) }};
}});

// Build the doc panel DOM. The HTML is rendered server-side by the /info and
// /hover endpoints? NO — those return plain text. We render markdown here would
// require a JS markdown lib, which we don't bundle. So the element requests
// pre-rendered HTML from a dedicated render path. See NOTE in the plan: the
// element keeps rendering in Python, so /info and /hover must return HTML.
function renderDocPanel(signature, docstring) {{
    if (!signature && !docstring) return null;
    const dom = document.createElement('div');
    dom.className = 'hw-cm-doc';
    dom.innerHTML = (signature ? signature : '') + (docstring ? docstring : '');
    return dom;
}}

const langExt = CM.languages.find(l => ALLOWED_LANGS.some(
    a => a.toLowerCase() === l.name.toLowerCase()));
if (langExt) {{
    const ext = await langExt.load();
    editor.dispatch({{
        effects: CM.StateEffect.appendConfig.of([
            ext.language.data.of({{ autocomplete: haywireComplete }}),
            haywireHover,
        ])
    }});
}}
"""
```

> **STOP — design contradiction surfaced during implementation.** The JS `renderDocPanel` cannot render markdown (no JS markdown lib is bundled). But the design (decision A) put `_render_doc_html` in the **element** (Python) and made the provider return **plain text**. These conflict: the Python `_render_doc_html` lives server-side-of-the-element but the panel is built in injected JS that can't call it per-keystroke without a round-trip. Resolve before continuing — see Task 4a.

- [ ] **Step 3: Do NOT run yet — proceed to Task 4a to resolve the rendering seam.**

---

## Task 4a: Element-owned render endpoint (Resolution X — settled)

The doc-panel HTML is produced by Python's `_render_doc_html` (markdown2+pygments) but consumed inside injected JS that cannot call Python per-keystroke. **Settled resolution (X):** the *element* (core) registers its own render route `POST /api/code-intel/render` that takes `{signature, docstring}` and returns `{html}`. The JS `info`/hover callbacks fetch `/info` (plain text from the studio provider) → then `/render` (html from the core element). This preserves every design decision: the studio provider stays plain-data, all rendering stays in core, and the extra round-trip is lazy (per *highlighted* item, not per keystroke).

- [ ] **Step 1: Implement the render endpoint in core**

In `packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py`, add near the top of `attach_code_intelligence` (so it is registered when first attached; guard against double-registration with a module flag):

```python
_RENDER_ROUTE_REGISTERED = False


def _ensure_render_route() -> None:
    global _RENDER_ROUTE_REGISTERED
    if _RENDER_ROUTE_REGISTERED:
        return
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from nicegui import app

    @app.post("/api/code-intel/render")
    async def render(request: Request) -> JSONResponse:
        body = await request.json()
        html = _render_doc_html(body.get("signature") or None, body.get("docstring") or None)
        return JSONResponse({"html": html})

    _RENDER_ROUTE_REGISTERED = True
```

Call `_ensure_render_route()` as the first line inside `attach_code_intelligence`.

- [ ] **Step 2: Update the JS `info`/hover to fetch render**

Change `renderDocPanel` and the two callers so the panel HTML comes from `/api/code-intel/render`. Replace the `info:` callback body and the hover panel build to:

```javascript
// info callback:
info: async () => {{
    const r = await fetch('{info_url}', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ code: doc.toString(), line: reqLine,
            column: reqCol, path: {path_js}, label: c.name }})
    }});
    const j = await r.json();
    return await renderDocPanel(j.signature, j.docstring);
}},
```

```javascript
async function renderDocPanel(signature, docstring) {{
    if (!signature && !docstring) return null;
    const rr = await fetch('{render_url}', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ signature, docstring }})
    }});
    const html = (await rr.json()).html;
    if (!html) return null;
    const dom = document.createElement('div');
    dom.className = 'hw-cm-doc';
    dom.innerHTML = html;
    return dom;
}}
```

Add `render_url` to the `_INJECTION_JS.format(...)` kwargs and the function signature (`render_url: str = "/api/code-intel/render"`).

- [ ] **Step 3: Verify the module imports cleanly**

Run: `uv run python -c "import haywire.core.graph.editor; from haywire.ui.components.codemirror import attach_code_intelligence; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Re-run the translation unit tests (still green)**

Run: `uv run pytest tests/ui/components/codemirror/test_code_intelligence_translation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/codemirror/code_intelligence.py
git commit -m "feat(core): attach_code_intelligence helper with language gating + render route"
```

---

## Task 5: Switch the app to register the new provider; delete the prototype

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Delete: `packages/haywire-studio/src/haywire_studio/completion.py`

- [ ] **Step 1: Update the import + call in app.py**

In `packages/haywire-studio/src/haywire_studio/app.py`, replace:

```python
from haywire_studio.completion import register_completion_endpoint
```
with:
```python
from haywire_studio.code_intelligence import register_code_intelligence_endpoints
```

and replace the call (currently `register_completion_endpoint()`, near the top of `HaywireApp.__init__`) with:

```python
        register_code_intelligence_endpoints()
```

- [ ] **Step 2: Delete the prototype provider**

Run: `git rm packages/haywire-studio/src/haywire_studio/completion.py`

- [ ] **Step 3: Verify no stale references to the old names**

Run: `grep -rn "register_completion_endpoint\|haywire_studio.completion\|/api/complete\b\|/api/hover\b" packages/ barn/ --include="*.py"`
Expected: no output (the old `/api/complete*` + `/api/hover` strings only remain inside the old `component_source_editor` injection, which Task 6 replaces — if grep shows ONLY that file, that is expected and fixed next).

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor(studio): register code_intelligence endpoints; drop completion.py prototype"
```

---

## Task 6: Rewire `ComponentSourceEditor` to use the helper

Gut `_inject_completions` (the ~110-line JS blob) and replace with a one-line helper call. Source is always Python here, so the default `language_filter=("Python",)` is correct.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/component_source_editor.py`

- [ ] **Step 1: Replace the `_inject_completions` method**

In `barn/haybale-studio/haybale_studio/editors/component_source_editor.py`, replace the **entire** `_inject_completions` method (everything from `def _inject_completions(self) -> None:` through the end of its injected JS string) with:

```python
    def _inject_completions(self) -> None:
        if self._editor is None:
            return
        from haywire.ui.components.codemirror import attach_code_intelligence

        attach_code_intelligence(
            self._editor,
            language_filter=("Python",),
            path=str(self._path) if self._path is not None else None,
        )
```

- [ ] **Step 2: Verify the file imports and lints**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/component_source_editor.py`
Expected: `All checks passed!`

Run: `grep -n "run_javascript\|/api/complete\|/api/hover\|haywireComplete\|hoverTooltip" barn/haybale-studio/haybale_studio/editors/component_source_editor.py`
Expected: no output (all injected JS removed).

- [ ] **Step 3: MANUAL verification in the app**

Run: `uv run haywire`
Then:
1. Open the **Component Source** editor (right slot) on any node.
2. Click into the editor, type `self.` on a new line inside a method.
3. **Observe:** a completion dropdown appears with public methods first (e.g. `add`), private (`_x`) below, dunders hidden.
4. Arrow to a method → **observe** a doc panel beside it with the signature in a highlighted code block + docstring rendered as markdown (Args:/bullets on their own lines).
5. Hover the mouse over a method name in the code → **observe** a tooltip with signature + docstring after a short delay.
6. Open the browser devtools Network tab → confirm calls go to `/api/code-intel/complete`, `/api/code-intel/info`, `/api/code-intel/render`, `/api/code-intel/hover`.

Expected: all six observations hold. If the dropdown never appears, check the console for errors from the injected JS (e.g. a language-facet read failing) and confirm the NiceGUI bundle exports `autocompletion`/`hoverTooltip` (out-of-scope prerequisite).

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/component_source_editor.py
git commit -m "refactor(studio): ComponentSourceEditor uses attach_code_intelligence helper"
```

---

## Task 7: Wire the helper into `CodeEditor` (validates language gating)

`CodeEditor` is polymorphic (Python/JSON/TOML/Markdown/plain). Attaching once with the default Python filter must (a) give completion on `.py` files and (b) stay silent on `.toml`/`.json`/`.md`.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/code_editor.py:228-236` (the `_make_codemirror` method)

- [ ] **Step 1: Attach intelligence in `_make_codemirror`**

In `barn/haybale-studio/haybale_studio/editors/code_editor.py`, change `_make_codemirror` from:

```python
    def _make_codemirror(self, context: "SessionContext", language: Optional[CmLanguage]) -> ui.codemirror:
        return ui.codemirror(
            value=self._content,
            language=language,
            theme=self._codemirror_theme(context),
            line_wrapping=True,
            on_change=lambda e: self._on_text_changed(e.value),
        ).style("flex: 1; min-height: 0; width: 100%; height: 100%;")
```

to:

```python
    def _make_codemirror(self, context: "SessionContext", language: Optional[CmLanguage]) -> ui.codemirror:
        from haywire.ui.components.codemirror import attach_code_intelligence

        cm = ui.codemirror(
            value=self._content,
            language=language,
            theme=self._codemirror_theme(context),
            line_wrapping=True,
            on_change=lambda e: self._on_text_changed(e.value),
        ).style("flex: 1; min-height: 0; width: 100%; height: 100%;")
        # Intelligence self-silences for non-Python languages (the JS source
        # reads the live language and no-ops unless it is in language_filter).
        attach_code_intelligence(
            cm,
            language_filter=("Python",),
            path=str(self._resolve_path()) if self._resolve_path() is not None else None,
        )
        return cm
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/code_editor.py`
Expected: `All checks passed!`

- [ ] **Step 3: MANUAL verification — Python file (intelligence ON)**

Run: `uv run haywire`
1. Open a `.py` file in the **Code** editor.
2. Type `import os` then on the next line `os.` → **observe** completion dropdown + doc panel + hover, same as Task 6.

Expected: full intelligence works.

- [ ] **Step 4: MANUAL verification — non-Python files (intelligence OFF, no wasted calls)**

1. Open a `.toml` file (e.g. any `pyproject.toml`) in the Code editor. Type a few characters.
2. **Observe:** NO completion dropdown appears. In the Network tab, confirm **zero** calls to `/api/code-intel/*` while editing the TOML.
3. Repeat for a `.json` file and a `.md` file.

Expected: no dropdown, no network calls for non-Python files. This validates the language-gating design (the whole reason `CodeEditor` is in scope).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/code_editor.py
git commit -m "feat(studio): CodeEditor opts into code intelligence (Python-gated)"
```

---

## Task 8: Full quality gate

**Files:** none (verification only)

- [ ] **Step 1: Lint + format the whole repo**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and no format drift. If format drift: `uv run ruff format .` then re-commit.

- [ ] **Step 2: Type-check the touched packages**

Run:
```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-studio/haybale_studio/
```
Expected: no NEW errors versus the pre-change baseline. (Per CLAUDE.md the baseline is clean; anything new is yours to fix.)

- [ ] **Step 3: Run the unit + integration suites**

Run: `uv run pytest -m "not integration"` then `uv run pytest -m integration`
Expected: all pass.

- [ ] **Step 4: Dependency audit**

Run the `/haywire-dep-check` skill (or manually confirm `markdown2`/`pygments` are declared in `haywire-core/pyproject.toml` and not imported anywhere they're undeclared).
Expected: no dependency mismatches.

- [ ] **Step 5: Final commit if anything changed**

```bash
git add -A
git commit -m "chore: code-intelligence extraction — quality gate fixes"
```

---

## Self-Review notes (for the implementer)

- **The one live decision:** Task 4a (where `_render_doc_html` runs). Resolution X is pre-filled and preserves every design decision; do not start Task 4's JS until 4a is confirmed, because the JS shape depends on it.
- **Out-of-scope prerequisite:** the NiceGUI bundle must export `autocompletion` + `hoverTooltip` (it does in this dev env via the local fork + `cp -r`). If completion silently does nothing and the console shows `CM.hoverTooltip is not a function` or similar, that prerequisite regressed — fix the bundle, not this code.
- **Language-facet read (`state.facet(CM.language)`):** this is the one piece of injected JS whose API should be confirmed against the bundled CodeMirror version at implementation time. If `.name` is not present on the facet value, fall back to comparing the loaded `LanguageDescription` used in `appendConfig`. Verify during Task 7 Step 4 (the non-Python silence test is the proof it works).
- **No `ui.codemirror` subclass** was introduced — `attach_code_intelligence` is a free function, by design. Do not "improve" it into a subclass.
