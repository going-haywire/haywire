"""Unit tests for the studio sidecar identity file (<workspace>/.haywire/studio.json)."""

import json
import os
from pathlib import Path

import pytest

from haywire_studio.farmhand.identity import (
    IDENTITY_FILENAME,
    identity_status,
    read_identity,
    write_identity,
)

pytestmark = pytest.mark.unit


def test_write_creates_sidecar_with_expected_fields(tmp_path):
    ident = write_identity(tmp_path, port=8124)
    sidecar = tmp_path / ".haywire" / IDENTITY_FILENAME
    assert sidecar.exists()
    on_disk = json.loads(sidecar.read_text(encoding="utf-8"))
    assert on_disk == ident
    assert ident["pid"] == os.getpid()
    assert ident["port"] == 8124
    assert ident["project_path"] == str(Path(tmp_path).resolve())
    assert ident["project"] == Path(tmp_path).resolve().name
    assert ident["url"] == "http://127.0.0.1:8124"
    assert ident["role"] == "haywire-studio"
    assert isinstance(ident["started_at"], float)


def test_write_gitignores_the_sidecar(tmp_path):
    write_identity(tmp_path, port=8124)
    gitignore = (tmp_path / ".haywire" / ".gitignore").read_text(encoding="utf-8")
    assert IDENTITY_FILENAME in gitignore


def test_write_accepts_str_workspace(tmp_path):
    ident = write_identity(str(tmp_path), port=9000)
    assert ident["port"] == 9000
    assert (tmp_path / ".haywire" / IDENTITY_FILENAME).exists()


def test_read_returns_none_when_absent(tmp_path):
    assert read_identity(tmp_path) is None


def test_read_returns_none_on_garbage(tmp_path):
    haywire = tmp_path / ".haywire"
    haywire.mkdir(parents=True)
    (haywire / IDENTITY_FILENAME).write_text("not json{", encoding="utf-8")
    assert read_identity(tmp_path) is None


def test_read_round_trips_write(tmp_path):
    written = write_identity(tmp_path, port=8124)
    assert read_identity(tmp_path) == written


def test_status_alive_for_current_process(tmp_path):
    ident = write_identity(tmp_path, port=8124)  # pid == this test process
    # write_identity stamps started_at with the write-time wall clock, not this
    # process's actual create_time — fine for a real studio (written once near
    # launch) but wrong here since pytest has been running for a while. Align it
    # so the psutil recycled-pid check compares against the true create_time.
    psutil = pytest.importorskip("psutil")
    ident["started_at"] = psutil.Process(os.getpid()).create_time()
    assert identity_status(ident) == "alive"


def test_status_dead_for_unused_pid(tmp_path):
    ident = write_identity(tmp_path, port=8124)
    ident["pid"] = 999999  # not a live pid
    assert identity_status(ident) == "dead"


def test_identity_records_auth_required(tmp_path):
    ident = write_identity(tmp_path, 8124, auth_required=True)
    assert ident["auth_required"] is True
    assert json.loads((tmp_path / ".haywire" / "studio.json").read_text())["auth_required"] is True


def test_identity_defaults_auth_required_false(tmp_path):
    assert write_identity(tmp_path, 8124)["auth_required"] is False
