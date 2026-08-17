"""``--no-browser`` top-level CLI flag (Task 2c): argparse -> run_app ->
HaywireApp.run -> ui.run(show=...)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from haywire_studio.app import main, run_app

pytestmark = pytest.mark.unit


# --- main() parses the flag and threads it through -------------------------


def test_no_browser_flag_threads_open_browser_false(monkeypatch):
    monkeypatch.setattr("sys.argv", ["haywire", "--no-browser"])

    with patch("haywire_studio.app.run_app", return_value=0) as mock_run_app:
        with pytest.raises(SystemExit) as exc_info:
            main()

    mock_run_app.assert_called_once_with(open_browser=False)
    assert exc_info.value.code == 0


def test_absence_of_flag_defaults_to_open_browser_true(monkeypatch):
    monkeypatch.setattr("sys.argv", ["haywire"])

    with patch("haywire_studio.app.run_app", return_value=0) as mock_run_app:
        with pytest.raises(SystemExit):
            main()

    mock_run_app.assert_called_once_with(open_browser=True)


def test_no_browser_is_top_level_not_a_subcommand(monkeypatch):
    """--no-browser must parse alongside the no-subcommand launch path, not
    require or conflict with a subcommand."""
    monkeypatch.setattr("sys.argv", ["haywire", "--no-browser"])

    with patch("haywire_studio.app.run_app", return_value=0):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0


# --- run_app() threads through to HaywireApp.run ----------------------------


def test_run_app_threads_open_browser_to_app_instance_run():
    with (
        patch("haywire_studio.app.get_stdout_tee"),
        patch("haywire_studio.app.HaywireApp") as MockHaywireApp,
        patch("haywire_studio.app.app"),
        patch("haywire.core.update.confirmed.exit_code", return_value=0),
    ):
        run_app(open_browser=False)

    instance = MockHaywireApp.return_value
    instance.run.assert_called_once_with(open_browser=False)


def test_run_app_defaults_open_browser_true():
    with (
        patch("haywire_studio.app.get_stdout_tee"),
        patch("haywire_studio.app.HaywireApp") as MockHaywireApp,
        patch("haywire_studio.app.app"),
        patch("haywire.core.update.confirmed.exit_code", return_value=0),
    ):
        run_app()

    instance = MockHaywireApp.return_value
    instance.run.assert_called_once_with(open_browser=True)


# --- HaywireApp.run threads open_browser to ui.run(show=...) ---------------


def test_haywire_app_run_threads_open_browser_to_ui_run_show(monkeypatch):
    from haywire_studio.app import HaywireApp
    from haywire_studio.security.document import SecurityDocument

    instance = HaywireApp.__new__(HaywireApp)
    instance._is_shutting_down = True
    monkeypatch.setattr(instance, "create_ui", lambda: None)
    monkeypatch.setattr(instance, "setup_farmhand", lambda port, document, *, tls=False: None)
    monkeypatch.setattr(instance, "_install_auth", lambda document: False)
    monkeypatch.setattr(instance, "_load_security_document", lambda: SecurityDocument())

    with (
        patch("haywire_studio.network.settings.NetworkSettings") as MockSettings,
        patch("haywire_studio.app.ui") as mock_ui,
    ):
        MockSettings.return_value.port = 8124
        instance.run(open_browser=False)

    assert mock_ui.run.call_args.kwargs["show"] is False
