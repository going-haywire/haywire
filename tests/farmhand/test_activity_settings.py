"""ActivitySettings — history size and audit-log destination."""

import pytest

pytestmark = pytest.mark.unit


def test_namespace_is_farmhand_activity():
    from haywire_studio.farmhand.settings import ActivitySettings

    assert ActivitySettings()._namespace == "farmhand.activity"


def test_history_size_defaults_to_fifty():
    from haywire_studio.farmhand.settings import ActivitySettings

    assert ActivitySettings().history_size == 50


def test_log_path_defaults_to_empty_meaning_off():
    from haywire_studio.farmhand.settings import ActivitySettings

    assert ActivitySettings().log_path == ""


def test_log_path_can_be_set_to_a_relative_path():
    from haywire_studio.farmhand.settings import ActivitySettings

    settings = ActivitySettings()
    settings.log_path = ".haywire/activity.jsonl"
    assert settings.log_path == ".haywire/activity.jsonl"
    settings.log_path = ""  # leave shared global state clean for other tests
