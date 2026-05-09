"""HaystackSettings — per-workspace settings for haystack scalars."""

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_default_last_haystack_name_is_empty():
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    s = HaystackSettings()
    assert s.last_haystack_name == ""


def test_default_new_counter_starts_at_one():
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    s = HaystackSettings()
    assert s.new_counter == 1


def test_settings_class_subclasses_library_settings():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haywire.core.settings.schema import LibrarySettings

    assert issubclass(HaystackSettings, LibrarySettings)


def test_can_set_and_read_last_haystack_name():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haywire.core.settings.registry import SettingsRegistry

    # LibrarySettings needs a registry wired so __get__/__set__ use the same key.
    registry = SettingsRegistry()
    registry.register_schema(HaystackSettings)
    HaystackSettings._registry = registry

    try:
        s = HaystackSettings()
        s.last_haystack_name = "my_session"
        assert s.last_haystack_name == "my_session"
    finally:
        HaystackSettings._registry = None
