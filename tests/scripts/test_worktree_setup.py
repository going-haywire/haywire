"""The pure parts of scripts/worktree_setup.py: picking a studio port and writing it."""

from scripts.worktree_setup import FIRST_WORKTREE_PORT, choose_studio_port, studio_port, with_studio_port


def test_first_free_port_above_the_main_studio():
    assert choose_studio_port(claimed=set(), busy=lambda port: False) == FIRST_WORKTREE_PORT
    assert FIRST_WORKTREE_PORT == 8125


def test_skips_ports_other_worktrees_claimed_or_something_listens_on():
    port = choose_studio_port(claimed={8125, 8127}, busy=lambda port: port == 8126)
    assert port == 8128


def test_port_is_written_beside_the_existing_settings():
    settings = {
        "network": {"allowed_remote_ranges": {"value": "10.0.0.0/8"}},
        "ui": {"theme": {"value": "dark"}},
    }
    updated = with_studio_port(settings, 8126)
    assert studio_port(updated) == 8126
    assert updated["network"]["allowed_remote_ranges"] == {"value": "10.0.0.0/8"}
    assert updated["ui"] == {"theme": {"value": "dark"}}
    assert "port" not in settings["network"]


def test_no_port_in_empty_or_partial_settings():
    assert studio_port({}) is None
    assert studio_port({"network": {}}) is None
    assert studio_port(with_studio_port({}, 8125)) == 8125
