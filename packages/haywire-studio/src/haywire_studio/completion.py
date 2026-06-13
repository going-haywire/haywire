"""Jedi-backed code completion endpoint for the component source editor."""

from __future__ import annotations

import logging
from typing import Any

import jedi
import markdown2
from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app

logger = logging.getLogger(__name__)

# break-on-newline keeps the line structure of plain-text Python docstrings
# (Args:/Returns:/bullets on their own lines); code-friendly stops underscores
# in identifiers (as_inlet) being parsed as emphasis.
_MD_EXTRAS = ["fenced-code-blocks", "tables", "code-friendly", "break-on-newline"]


def _render_doc_html(signature: str | None, doc: str | None) -> str:
    """Render a jedi signature + docstring into highlighted HTML.

    The signature is wrapped in a fenced Python block so markdown2's
    fenced-code-blocks extra (with pygments) highlights it. The docstring
    body is rendered as markdown prose.
    """
    parts: list[str] = []
    if signature:
        parts.append(f"```python\n{signature}\n```")
    if doc:
        parts.append(doc)
    if not parts:
        return ""
    return markdown2.markdown("\n\n".join(parts), extras=_MD_EXTRAS)


def register_completion_endpoint() -> None:
    @app.post("/api/complete")
    async def complete(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            code: str = body.get("code", "")
            line: int = int(body.get("line", 1))
            column: int = int(body.get("column", 0))
            path: str | None = body.get("path")

            explicit: bool = bool(body.get("explicit", False))
            script = jedi.Script(code, path=path)
            completions = script.complete(line, column, fuzzy=False)
            if not explicit:
                completions = [c for c in completions if not c.name.startswith("__")]

            def _boost(name: str) -> int:
                if name.startswith("__"):
                    return -2
                if name.startswith("_"):
                    return -1
                return 1

            results = [
                {
                    "label": c.name,
                    "type": _jedi_type_to_cm(c.type),
                    "detail": c.description,
                    "boost": _boost(c.name),
                }
                for c in completions
            ]
            return JSONResponse({"completions": results})
        except Exception:
            logger.debug("jedi completion failed", exc_info=True)
            return JSONResponse({"completions": []})

    @app.post("/api/complete/info")
    async def complete_info(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            code: str = body.get("code", "")
            line: int = int(body.get("line", 1))
            column: int = int(body.get("column", 0))
            path: str | None = body.get("path")
            label: str = body.get("label", "")

            script = jedi.Script(code, path=path)
            for c in script.complete(line, column, fuzzy=False):
                if c.name == label:
                    signatures = [s.to_string() for s in c.get_signatures()]
                    header = "\n".join(signatures) or None
                    doc = c.docstring(raw=True)
                    return JSONResponse({"info": _render_doc_html(header, doc)})
            return JSONResponse({"info": ""})
        except Exception:
            logger.debug("jedi docstring lookup failed", exc_info=True)
            return JSONResponse({"info": ""})

    @app.post("/api/hover")
    async def hover(request: Request) -> JSONResponse:
        try:
            body: dict[str, Any] = await request.json()
            code: str = body.get("code", "")
            line: int = int(body.get("line", 1))
            column: int = int(body.get("column", 0))
            path: str | None = body.get("path")

            script = jedi.Script(code, path=path)
            names = script.help(line, column)
            if not names:
                return JSONResponse({"info": ""})

            name = names[0]
            signatures = [s.to_string() for s in name.get_signatures()]
            header = "\n".join(signatures) if signatures else name.description
            doc = name.docstring(raw=True)
            return JSONResponse({"info": _render_doc_html(header, doc)})
        except Exception:
            logger.debug("jedi hover lookup failed", exc_info=True)
            return JSONResponse({"info": ""})


def _jedi_type_to_cm(jedi_type: str) -> str:
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
    }.get(jedi_type, "text")
