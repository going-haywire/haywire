"""GET/POST /login — plain FastAPI, no NiceGUI, so the socket stays gated."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from haywire.core.access import AccessTier
from haywire_studio.auth import login as login_module
from haywire_studio.auth.cookies import COOKIE_NAME, verify_session
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.login import login_page_html, register_login_routes
from haywire_studio.auth.operations import add_user, enable_auth

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    target = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=target)
    enable_auth("alice", STRONG, path=target)
    return target


@pytest.fixture
def client(path, monkeypatch):
    monkeypatch.setattr(login_module, "LOGIN_FAILURE_DELAY_SECONDS", 0.0)
    app = FastAPI()
    register_login_routes(cache=RosterCache(path), secret=SECRET, app=app)
    return TestClient(app)


def test_get_login_returns_html(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<form" in response.text


def test_login_page_is_self_contained(client):
    """No external hosts, no NiceGUI assets — the gate exempts only /login itself."""
    body = client.get("/login").text
    assert "http://" not in body.replace('action="/login"', "")
    assert "/_nicegui" not in body


def test_successful_post_sets_the_cookie_and_redirects(client):
    response = client.post("/login", data={"username": "alice", "password": STRONG}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert verify_session(response.cookies[COOKIE_NAME], secret=SECRET) == "alice"


def test_cookie_is_httponly_samesite_lax_and_not_secure_over_http(client):
    response = client.post("/login", data={"username": "alice", "password": STRONG}, follow_redirects=False)
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.lower().replace("samesite=lax", "SameSite=lax")
    assert "Secure" not in header


def test_wrong_password_returns_401_html_with_no_cookie(client):
    response = client.post("/login", data={"username": "alice", "password": "nope"})
    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies
    assert "form" in response.text


def test_unknown_user_returns_401(client):
    response = client.post("/login", data={"username": "ghost", "password": STRONG})
    assert response.status_code == 401


def test_error_message_does_not_reveal_whether_the_user_exists(client):
    unknown = client.post("/login", data={"username": "ghost", "password": STRONG}).text
    wrong = client.post("/login", data={"username": "alice", "password": "nope"}).text
    assert unknown == wrong


def test_logout_clears_the_cookie(client):
    client.post("/login", data={"username": "alice", "password": STRONG})
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert (
        "Max-Age=0" in response.headers["set-cookie"]
        or 'haywire_session=""' in response.headers["set-cookie"]
    )


def test_html_escapes_the_error_text():
    assert "<script>" not in login_page_html("<script>alert(1)</script>")
