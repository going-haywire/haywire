"""``haywire studio start|stop|status`` against a fake studio process."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
import pytest

from haywire_studio.cli import studiocmd

# A stand-in for the studio: listens on the folder's port, writes studio.json, stops on SIGINT.
FAKE_STUDIO = textwrap.dedent(
    """
    import json, signal, socket, sys
    from pathlib import Path
    from haywire_studio.farmhand.identity import write_identity

    path = Path(".haywire/settings.json")
    settings = json.loads(path.read_text()) if path.exists() else {}
    port = settings.get("network", {}).get("port", {}).get("value", 8124)
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen()
    write_identity(Path.cwd(), port)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    while True:
        server.accept()[0].close()
    """
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def project(tmp_path, monkeypatch):
    folder = tmp_path / "proj"
    (folder / ".haywire").mkdir(parents=True)
    studiocmd.save_port(folder, _free_port())
    script = tmp_path / "fake_studio.py"
    script.write_text(FAKE_STUDIO, encoding="utf-8")
    monkeypatch.setattr(studiocmd, "studio_command", lambda _project, browser: [sys.executable, str(script)])
    yield folder
    ident = studiocmd.read_identity(folder)
    if ident and psutil.pid_exists(ident["pid"]):
        psutil.Process(ident["pid"]).kill()


def _run(handler, project: Path, **extra) -> int:
    return handler(argparse.Namespace(project=str(project), **extra))


def test_start_waits_until_the_studio_answers_then_stop_stops_it(project, capsys):
    port, _ = studiocmd.folder_port(project)
    assert _run(studiocmd._start, project, timeout=20.0, browser=False) == 0
    assert f"is up: http://127.0.0.1:{port}" in capsys.readouterr().out
    assert studiocmd.port_state(project, port).holder == "this folder"

    _run(studiocmd._status, project)
    assert "started by 'haywire studio start'" in capsys.readouterr().out

    assert _run(studiocmd._stop, project, force=False) == 0
    assert not studiocmd.listening(port)


def test_start_reuses_a_running_studio(project, capsys):
    assert _run(studiocmd._start, project, timeout=20.0, browser=False) == 0
    first = studiocmd.read_identity(project)
    assert _run(studiocmd._start, project, timeout=20.0, browser=False) == 0
    assert "already up" in capsys.readouterr().out
    again = studiocmd.read_identity(project)
    assert first is not None
    assert again is not None
    assert again["pid"] == first["pid"]


def test_start_takes_and_keeps_a_free_port_when_another_process_holds_the_folder_s(project, capsys):
    port, _ = studiocmd.folder_port(project)
    with socket.socket() as squatter:
        squatter.bind(("127.0.0.1", port))
        squatter.listen()
        assert _run(studiocmd._start, project, timeout=20.0, browser=False) == 0
    new, source = studiocmd.folder_port(project)
    assert new != port
    assert source == ".haywire/settings.json"
    assert f"this folder now uses {new}" in capsys.readouterr().out
    assert studiocmd.port_state(project, new).holder == "this folder"


def test_stop_leaves_a_studio_started_by_hand_unless_forced(project, tmp_path, capsys):
    port, _ = studiocmd.folder_port(project)
    by_hand = subprocess.Popen([sys.executable, str(tmp_path / "fake_studio.py")], cwd=project)
    try:
        deadline = time.monotonic() + 20
        while studiocmd.port_state(project, port).holder != "this folder":
            assert by_hand.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.1)
        assert _run(studiocmd._stop, project, force=False) == 1
        assert "not started by 'haywire studio start'" in capsys.readouterr().out
        assert _run(studiocmd._stop, project, force=True) == 0
    finally:
        by_hand.kill()
        by_hand.wait()


def test_status_reports_a_free_port(project, capsys):
    assert _run(studiocmd._status, project) == 0
    out = capsys.readouterr().out
    assert "Studio: not running" in out
    assert "(.haywire/settings.json)" in out


def test_the_default_port_is_used_without_settings(tmp_path):
    assert studiocmd.folder_port(tmp_path) == (8124, "the default")


def test_save_port_keeps_other_settings(tmp_path):
    (tmp_path / ".haywire").mkdir()
    (tmp_path / ".haywire" / "settings.json").write_text(json.dumps({"debug": {"x": 1}}))
    studiocmd.save_port(tmp_path, 8200)
    assert json.loads((tmp_path / ".haywire" / "settings.json").read_text()) == {
        "debug": {"x": 1},
        "network": {"port": {"value": 8200}},
    }
