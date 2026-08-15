"""Jedi-backed code-intelligence provider (editor-agnostic).

Registers three HTTP endpoints that take editor text + cursor position and
return PLAIN structured data in jedi's own vocabulary. NO CodeMirror types,
NO boost, NO HTML — all of that is the consuming element's concern (see
haywire.ui.extends.codemirror).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jedi
from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app

if TYPE_CHECKING:
    from jedi.api.classes import BaseName, Completion

logger = logging.getLogger(__name__)

# sys.path is fixed for the life of the interpreter for our purposes here, so
# resolve it once at import time rather than on every request. The workspace
# root is read fresh per call (via get_workspace_root()) since it is not set
# until HaywireApp.__init__ runs, which happens after this module is imported.
_SYS_PATH_ROOTS: tuple[Path, ...] = tuple(Path(entry).resolve() for entry in sys.path if entry)


def _confined_path(raw: str | None) -> str | None:
    """Return *raw* if it resolves inside an allowed root, else None.

    Allowed roots: the workspace root plus every sys.path entry — i.e. exactly
    what this interpreter could import anyway, so confinement grants no new
    disclosure while closing arbitrary-path probing.
    """
    if raw is None:
        return None
    try:
        resolved = Path(raw).resolve()
    except (OSError, ValueError):
        logger.warning("code-intel: rejected unresolvable path %r", raw)
        return None

    roots = _SYS_PATH_ROOTS
    try:
        from haywire.core.di.context import get_workspace_root

        roots = (get_workspace_root().resolve(), *roots)
    except RuntimeError:
        # Workspace root not set yet (e.g. module imported before HaywireApp
        # init) — fall back to sys.path roots only.
        pass

    if any(resolved.is_relative_to(root) for root in roots):
        return raw

    logger.warning("code-intel: rejected out-of-bounds path %r", raw)
    return None


def _signature_and_doc(name: "BaseName") -> tuple[str, str]:
    """Extract a plain-text signature + docstring from a jedi name."""
    signatures = [s.to_string() for s in name.get_signatures()]
    signature = "\n".join(signatures) if signatures else (name.description or "")
    doc = name.docstring(raw=True) or ""
    return signature, doc


def _completion_payload(completions: "list[Completion]", *, explicit: bool) -> list[dict[str, str]]:
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
            script = jedi.Script(body.get("code", ""), path=_confined_path(body.get("path")))
            completions = script.complete(int(body.get("line", 1)), int(body.get("column", 0)), fuzzy=False)
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
            script = jedi.Script(body.get("code", ""), path=_confined_path(body.get("path")))
            label = body.get("label", "")
            for c in script.complete(int(body.get("line", 1)), int(body.get("column", 0)), fuzzy=False):
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
            script = jedi.Script(body.get("code", ""), path=_confined_path(body.get("path")))
            names = script.help(int(body.get("line", 1)), int(body.get("column", 0)))
            if not names:
                return JSONResponse({"signature": "", "docstring": ""})
            sig, doc = _signature_and_doc(names[0])
            return JSONResponse({"signature": sig, "docstring": doc})
        except Exception:
            logger.debug("code-intel hover failed", exc_info=True)
            return JSONResponse({"signature": "", "docstring": ""})
