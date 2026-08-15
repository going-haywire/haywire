"""``GET /login`` and ``POST /login`` — plain FastAPI, deliberately not NiceGUI.

A NiceGUI login page would run its submit handler *server-side over the
websocket*, so unauthenticated clients would need ``/_nicegui_ws/`` open in
order to log in — the exact transport carrying the entire application. The
exemption would swallow the gate. Plain HTTP keeps the unauthenticated surface
to these two routes.

Consequence: this is the one place in the codebase that hardcodes colours
instead of using ``--hw-*`` tokens, because the theme system, ``hui`` and every
NiceGUI element only exist after the socket connects. The values below are
lifted from the dark workbench theme so the page does not look foreign.
"""

from __future__ import annotations

import asyncio
import html
import logging

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from haywire_studio.auth.cookies import COOKIE_NAME, sign_session
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import authenticate

logger = logging.getLogger(__name__)

#: Fixed delay on a failed attempt. A speed bump, not a defence — with the
#: password policy in force, online guessing is already infeasible, and account
#: lockout is a self-denial-of-service vector (anyone who can reach /login could
#: lock out the admin trying to fix a show).
LOGIN_FAILURE_DELAY_SECONDS = 1.0

#: Deliberately identical for "no such user" and "wrong password", so the page
#: cannot be used to enumerate the roster.
_GENERIC_ERROR = "Incorrect username or password."


def login_page_html(error: str = "") -> str:
    """The whole login page: one file, no external requests, no scripts."""
    banner = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haywire — Sign in</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: #17191c; color: #d8dbe0;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  form {{
    background: #1e2126; border: 1px solid #2c3037; border-radius: 8px;
    padding: 2rem; width: min(22rem, 90vw); display: grid; gap: 1rem;
  }}
  h1 {{ margin: 0 0 .5rem; font-size: 1.25rem; font-weight: 600; }}
  label {{ display: grid; gap: .35rem; font-size: .8rem; color: #9aa0aa; }}
  input {{
    background: #14161a; border: 1px solid #2c3037; border-radius: 4px;
    padding: .55rem .7rem; color: #d8dbe0; font-size: .95rem;
  }}
  input:focus {{ outline: 2px solid #4a9eff; outline-offset: 0; }}
  button {{
    background: #4a9eff; border: 0; border-radius: 4px; padding: .6rem;
    color: #0d0f12; font-size: .95rem; font-weight: 600; cursor: pointer;
  }}
  .error {{ margin: 0; color: #ff6b6b; font-size: .85rem; }}
</style>
</head>
<body>
<form method="post" action="/login">
  <h1>Haywire</h1>
  {banner}
  <label>Username<input name="username" autocomplete="username" autofocus required></label>
  <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
  <button type="submit">Sign in</button>
</form>
</body>
</html>
"""


def register_login_routes(*, cache: RosterCache, secret: bytes, app=None) -> None:
    """Register ``/login`` (GET, POST) and ``/logout`` (POST) on ``app``.

    ``app`` defaults to ``nicegui.app``; tests pass a bare FastAPI instance.
    """
    if app is None:
        from nicegui import app as nicegui_app

        app = nicegui_app

    @app.get("/login", response_class=HTMLResponse)
    async def _login_form() -> HTMLResponse:
        return HTMLResponse(login_page_html())

    @app.post("/login")
    async def _login_submit(
        request: Request,
        username: str = Form(""),
        password: str = Form(""),
    ):
        principal = authenticate(username, password, path=cache.path)
        if principal is None:
            logger.warning("Failed login for %r from %s", username, request.client)
            if LOGIN_FAILURE_DELAY_SECONDS:
                await asyncio.sleep(LOGIN_FAILURE_DELAY_SECONDS)
            return HTMLResponse(login_page_html(_GENERIC_ERROR), status_code=401)

        days = cache.roster().session_days
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            sign_session(principal.name, secret=secret, days=days),
            max_age=None if days == 0 else days * 86400,
            httponly=True,
            samesite="lax",
            # Only under real TLS: an unconditional Secure flag would make the
            # cookie silently unusable on loopback HTTP, which is how the studio
            # is normally run.
            secure=request.url.scheme == "https",
            path="/",
        )
        return response

    @app.post("/logout")
    async def _logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response
