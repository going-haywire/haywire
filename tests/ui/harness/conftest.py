"""
Pytest fixtures for the settings UI harness tests.

harness (session-scoped):
    Starts HarnessApp as a subprocess, polls /status until ready, yields base URL.
    Terminates the subprocess on teardown.

reset_setting (function-scoped):
    Yields a callable reset(key, original_value) that POSTs /api/set to restore
    a setting to its original value after a test that mutated it.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest
import requests

_BASE_URL = "http://localhost:8090"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture(scope="session")
def harness():
    """Start the harness app subprocess and wait until it is ready."""
    # Strip PYTEST_CURRENT_TEST so NiceGUI's is_pytest() check doesn't fire inside
    # the subprocess — otherwise ui.run() reads NICEGUI_SCREEN_TEST_PORT and crashes.
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    proc = subprocess.Popen(
        ["uv", "run", "python", "tests/ui/harness/app.py"],
        cwd=str(_REPO_ROOT),
        env=env,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            r = requests.get(f"{_BASE_URL}/status", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.4)
    else:
        proc.terminate()
        raise RuntimeError("Harness did not become ready within 20s")
    yield _BASE_URL
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def reset_setting(harness):
    """
    Fixture that provides a callable to reset a registry key after a test.

    Usage in a test:
        def test_something(page, harness, reset_setting):
            reset_setting("testing.default_intensity", 0.5)
            # test body that changes testing.default_intensity
            # after the test, the fixture resets it back to 0.5
    """
    resets = []

    def _schedule_reset(key: str, original_value):
        resets.append((key, original_value))

    yield _schedule_reset

    for key, val in resets:
        try:
            requests.post(f"{harness}/api/set", params={"key": key, "value": str(val)}, timeout=2)
        except Exception:
            pass
