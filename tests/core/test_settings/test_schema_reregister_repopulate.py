"""Schema re-registration restores TOML values for the schema's fields.

When a LibrarySettings / FrameworkSettings schema is unregistered (library
disable, or hot-reload's intermediate teardown) and then re-registered,
``_unregister_schema_fields`` wipes the in-memory tier values for that
schema's fields. Without M3, the on-disk TOML keeps its values but the
re-registered schema reads through to defaults — the stored value is
effectively lost until a full restart.

These tests verify SettingsRegistry._register_class re-reads both TOML
files (global + workspace) for the schema's fields, restoring the
on-disk values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.settings import setting
from haywire.core.settings.enums import SettingMode
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.schema import LibrarySettings


@pytest.fixture
def workspace_toml(tmp_path: Path) -> Path:
    """A workspace TOML with a haystack-style value for tests."""
    path = tmp_path / "settings.toml"
    path.write_text('[testlib]\nlast_name = "my-session"\n')
    return path


def _make_schema(_namespace_label: str = "testlib"):
    """Fresh schema class per test so re-registration isn't masked by cached state."""

    class TestlibSettings(LibrarySettings, namespace=_namespace_label):
        last_name = setting[str]("", label="Last")

    return TestlibSettings


class TestRegisterClassRepopulatesFromToml:
    def test_workspace_value_survives_disable_reenable(self, workspace_toml: Path):
        registry = SettingsRegistry()
        registry.load_from_toml(workspace_toml, tier="workspace")

        Schema = _make_schema()

        # First registration: workspace TOML value is loaded.
        key = registry.register_schema(Schema)
        assert Schema().last_name == "my-session"
        assert key is not None

        # Disable: unregister the schema's fields.
        registry._unregister_class(key)
        # After unregister, the tier dict has dropped the key entirely
        # (verified by reading the underlying dict directly).
        assert "testlib.last_name" not in registry._workspace_tier_values

        # Re-enable: re-register. Without the fix, last_name would read "".
        registry.register_schema(Schema)
        assert Schema().last_name == "my-session", (
            "After re-registration, the workspace TOML value must be restored. "
            "If this fails, _register_class is not calling "
            "_repopulate_from_toml_for_keys."
        )

    def test_global_value_survives_disable_reenable(self, tmp_path: Path):
        global_path = tmp_path / "global.toml"
        global_path.write_text('[testlib]\nlast_name = "from-global"\n')

        registry = SettingsRegistry()
        registry.load_from_toml(global_path, tier="global")

        Schema = _make_schema()
        key = registry.register_schema(Schema)
        assert Schema().last_name == "from-global"
        assert key is not None

        registry._unregister_class(key)
        registry.register_schema(Schema)
        assert Schema().last_name == "from-global"

    def test_repopulate_does_not_touch_other_schemas(self, tmp_path: Path):
        """Re-registering schema A must NOT clobber schema B's tier values."""
        workspace_path = tmp_path / "settings.toml"
        workspace_path.write_text('[alpha]\nfield = "a-value"\n[beta]\nfield = "b-value"\n')

        registry = SettingsRegistry()
        registry.load_from_toml(workspace_path, tier="workspace")

        class Alpha(LibrarySettings, namespace="alpha"):
            field = setting[str]("", label="Alpha")

        class Beta(LibrarySettings, namespace="beta"):
            field = setting[str]("", label="Beta")

        alpha_key = registry.register_schema(Alpha)
        beta_key = registry.register_schema(Beta)
        assert alpha_key is not None
        assert beta_key is not None

        # Set a non-TOML override on Beta (in-memory only — not in the TOML).
        # This proves the repopulate doesn't reload the whole file.
        registry.set_global("beta.field", "b-override", SettingMode.EXPLICIT)
        assert Beta().field == "b-override"

        # Disable + re-enable Alpha. Beta's in-memory override must survive.
        registry._unregister_class(alpha_key)
        registry.register_schema(Alpha)

        assert Alpha().field == "a-value"  # restored from TOML
        assert Beta().field == "b-override"  # in-memory override untouched

    def test_no_toml_paths_is_a_noop(self):
        """If neither global_path nor workspace_path is set, re-registration
        is still safe — repopulate just skips both."""
        registry = SettingsRegistry()  # no load_from_toml calls

        Schema = _make_schema()
        key = registry.register_schema(Schema)
        assert key is not None
        registry._unregister_class(key)

        # Should not raise; schema re-registers cleanly with default value.
        registry.register_schema(Schema)
        assert Schema().last_name == ""

    def test_missing_toml_file_is_a_noop(self, tmp_path: Path):
        """If the TOML path is set but the file doesn't exist, repopulate
        is a no-op rather than an error."""
        nonexistent = tmp_path / "does-not-exist.toml"

        registry = SettingsRegistry()
        registry._workspace_path = nonexistent  # set path but file is absent

        Schema = _make_schema()
        # Should not raise — _repopulate is gated on path.exists().
        key = registry.register_schema(Schema)
        assert key is not None
        registry._unregister_class(key)
        registry.register_schema(Schema)


class TestRepopulateHelperDirect:
    """Targeted tests for SettingsRegistry._repopulate_from_toml_for_keys."""

    def test_only_listed_keys_are_applied(self, tmp_path: Path):
        path = tmp_path / "settings.toml"
        path.write_text('[alpha]\nfield = "a"\n[beta]\nfield = "b"\n[gamma]\nfield = "g"\n')

        registry = SettingsRegistry()
        registry.load_from_toml(path, tier="workspace")

        # Register two schemas; pretend their fields' tier values are wiped.
        class Alpha(LibrarySettings, namespace="alpha"):
            field = setting[str]("", label="A")

        class Beta(LibrarySettings, namespace="beta"):
            field = setting[str]("", label="B")

        registry.register_schema(Alpha)
        registry.register_schema(Beta)

        # Wipe both tier values directly.
        registry._workspace_tier_values["alpha.field"] = registry._workspace_tier_values[
            "alpha.field"
        ].__class__(mode=SettingMode.INHERIT)
        registry._workspace_tier_values["beta.field"] = registry._workspace_tier_values[
            "beta.field"
        ].__class__(mode=SettingMode.INHERIT)

        # Re-populate ONLY alpha.field.
        registry._repopulate_from_toml_for_keys({"alpha.field"}, path, tier="workspace")

        assert Alpha().field == "a"
        # Beta still inheriting since we didn't repopulate it.
        assert Beta().field == ""

    def test_unparseable_toml_does_not_raise(self, tmp_path: Path, caplog):
        path = tmp_path / "bad.toml"
        path.write_text("not = valid = toml = at all")

        registry = SettingsRegistry()
        # Should log + return, not raise.
        with caplog.at_level("ERROR"):
            registry._repopulate_from_toml_for_keys({"anything"}, path, tier="workspace")
        assert any("repopulate" in rec.message.lower() for rec in caplog.records)
