"""dev/scripts/studio.py: which command starts, stops or reports a folder's studio."""

from __future__ import annotations

from scripts.studio import FULL, OWN, command

UMBRELLA = "/home/me/.local/bin/haywire-studio"


def test_start_runs_the_full_studio_when_the_umbrella_s_command_is_on_the_path():
    argv, note = command("start", ["--browser"], UMBRELLA)
    assert argv == [UMBRELLA, "studio", "start", "--browser"]
    assert note == FULL


def test_start_falls_back_to_the_checkout_s_own_environment_and_says_so():
    argv, note = command("start", ["--browser"], None)
    assert argv == ["uv", "run", "--frozen", "haywire", "studio", "start", "--browser"]
    assert note == OWN
    assert "libraries from other repositories are missing" in OWN


def test_stop_and_status_use_the_checkout_s_own_environment_either_way():
    for action in ("stop", "status"):
        for umbrella in (UMBRELLA, None):
            own = ["uv", "run", "--frozen", "haywire", "studio", action]
            assert command(action, [], umbrella) == (own, None)
