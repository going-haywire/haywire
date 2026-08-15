"""The whole gate, end to end, against a real ASGI app."""

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from haywire.core.access import AccessTier
from haywire_studio.auth import login as login_module
from haywire_studio.auth.gate import AuthGateMiddleware
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.login import register_login_routes
from haywire_studio.auth.operations import add_user, enable_auth

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(login_module, "LOGIN_FAILURE_DELAY_SECONDS", 0.0)
    path = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)

    app = FastAPI()

    @app.get("/")
    async def _index():
        return PlainTextResponse("studio")

    cache = RosterCache(path)
    register_login_routes(cache=cache, secret=SECRET, app=app)
    app.add_middleware(AuthGateMiddleware, cache=cache, secret=SECRET)
    return TestClient(app), path


def test_anonymous_navigation_redirects_to_login(client):
    api, _ = client
    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_then_reach_the_studio(client):
    api, _ = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    assert api.get("/").text == "studio"


def test_removing_the_principal_locks_out_an_existing_cookie(client):
    api, path = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    assert api.get("/").status_code == 200

    from haywire_studio.auth.operations import add_user as add, remove_principal

    add("root", STRONG + "z", AccessTier.ADMIN, path=path)
    remove_principal("alice", path=path)

    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303


def test_logout_then_locked_out(client):
    api, _ = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    api.post("/logout")
    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
