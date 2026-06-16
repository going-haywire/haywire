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
from fastapi import Request
from fastapi.responses import JSONResponse

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


_RENDER_ROUTE = "/api/code-intel/render"


def register_code_intelligence_render_endpoint() -> None:
    """Register the core-owned doc-render endpoint.

    MUST be called at app startup, BEFORE ``ui.run()`` — NiceGUI/Starlette
    freezes the route table when the server starts, so a route added later
    (e.g. lazily during a page draw) 404s. Call this alongside the provider's
    ``register_code_intelligence_endpoints()`` in the app bootstrap.

    Resolution X: the *element* (core) owns markdown -> HTML rendering, but the
    HTML is consumed inside injected JS that cannot call Python per-keystroke.
    So the element exposes its own route that turns the provider's plain
    ``{signature, docstring}`` into the highlighted HTML the ``hw-cm-doc`` panel
    expects. The provider (studio) stays plain-data; rendering stays in core.
    """
    from nicegui import app

    @app.post(_RENDER_ROUTE)
    async def render(request: Request) -> JSONResponse:
        body = await request.json()
        html = _render_doc_html(body.get("signature") or None, body.get("docstring") or None)
        return JSONResponse({"html": html})


def attach_code_intelligence(
    editor: "ui.codemirror",
    *,
    completion_url: str = "/api/code-intel/complete",
    info_url: str = "/api/code-intel/info",
    hover_url: str = "/api/code-intel/hover",
    render_url: str = _RENDER_ROUTE,
    language_filter: Sequence[str] = ("Python",),
    path: str | None = None,
) -> None:
    """Attach jedi-backed completion + hover documentation to ``editor``.

    The injected sources read the editor's live language name and no-op unless
    it is in ``language_filter``. ``path`` (the file path of the edited buffer)
    is forwarded to the provider so jedi can resolve imports relative to it.

    Requires ``register_code_intelligence_render_endpoint()`` to have been called
    at app startup (the doc panel + hover fetch ``render_url``).

    Call this right after constructing ``editor`` in the draw. Timing is handled
    internally: the ``run_javascript`` is deferred one tick via ``ui.timer`` so
    the client connection can receive it, and the injected JS then polls
    ``getElement()`` + awaits ``editorPromise`` before wiring. Callers do NOT
    need their own timer/mount-event — earlier attempts to trigger on
    ``.on("vue:mounted")`` silently failed because the codemirror element does
    not emit that event.
    """
    import json

    from nicegui import ui

    js = _INJECTION_JS.format(
        editor_id=editor.id,
        completion_url=completion_url,
        info_url=info_url,
        hover_url=hover_url,
        render_url=render_url,
        path_js="null" if path is None else json.dumps(path),
        langs_js=json.dumps(list(language_filter)),
    )
    ui.timer(0.1, lambda: ui.run_javascript(js), once=True)


# CodeMirror autocomplete + hoverTooltip injection. Consumed by str.format();
# literal JS braces are doubled. The completion/hover sources read the live
# language from the editor's language facet and no-op unless it is one of the
# allowed languages. The provider returns plain {name, kind, signature,
# docstring}; this JS does the CM translation client-side (type via inline map,
# boost via public/private/dunder) and fetches doc HTML lazily: /info (plain
# text) -> /render (html) only for the highlighted/hovered item.
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
function activeLanguageName(state) {{
    const lang = state.facet(CM.language);
    return lang && lang.name ? lang.name : null;
}}
function languageAllowed(state) {{
    const name = activeLanguageName(state);
    if (!name) return false;
    return ALLOWED_LANGS.some(l => l.toLowerCase() === name.toLowerCase());
}}

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
            return await renderDocPanel(j.signature, j.docstring);
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
    const panel = await renderDocPanel(j.signature, j.docstring);
    if (!panel) return null;
    return {{ pos: start, end, above: true, create: () => ({{ dom: panel }}) }};
}});

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
