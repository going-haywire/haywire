"""Test runs must not write into a developer's own settings files.

The workspace tier is the one the app WRITES back to: a settings descriptor's
``__set__`` calls ``registry.save_to_json_debounced()``. Its path is derived
from ``workspace_root``, which the conftest fixtures pass as the real repo root
so library discovery works — so before ``workspace_settings_path`` existed, any
test writing a mirrored setting persisted into
``<repo>/.haywire/settings.json``.

That is how ``ui.node.default.skin.studio_skin = "skin-fw"`` — a value that
exists only in test files — ended up in a real workspace, leaving every node in
the studio falling back to the error skin.
"""

from pathlib import Path

import pytest

from haywire.core.di.config import HaywireModule
from haywire.core.di.test_config import create_test_injector
from haywire.core.settings.registry import SettingsRegistry


@pytest.fixture
def registry_for(project_root: Path):
    """A registry from a test injector rooted at the real repo, as fixtures do."""

    def _build(**kwargs) -> SettingsRegistry:
        injector = create_test_injector(
            workspace_root=str(project_root), enable_file_watching=False, **kwargs
        )
        return injector.get(SettingsRegistry)

    return _build


class TestTestInjectorIsolation:
    def test_workspace_tier_is_not_the_real_workspace_file(self, registry_for, project_root):
        registry = registry_for()
        real = (project_root / ".haywire" / "settings.json").resolve()
        assert registry._workspace_path != real

    def test_global_tier_is_not_the_real_user_file(self, registry_for):
        registry = registry_for()
        assert registry._global_path != (Path.home() / ".haywire" / "settings.json").resolve()

    def test_both_tiers_are_redirected_to_temp(self, registry_for):
        registry = registry_for()
        temp_root = Path(__import__("tempfile").gettempdir()).resolve()
        for path in (registry._global_path, registry._workspace_path):
            assert path is not None
            assert temp_root in path.parents, f"{path} is not under {temp_root}"

    def test_the_two_tiers_do_not_share_one_file(self, registry_for):
        """Sharing would let a workspace write clobber the global tier."""
        registry = registry_for()
        assert registry._global_path != registry._workspace_path

    def test_an_explicit_workspace_settings_path_is_honoured(self, registry_for, tmp_path):
        target = tmp_path / "explicit.json"
        registry = registry_for(workspace_settings_path=str(target))
        assert registry._workspace_path == target.resolve()


class TestModuleDefaults:
    """The production default is unchanged — only tests opt out."""

    def test_workspace_settings_default_to_the_workspace_root(self, tmp_path):
        module = HaywireModule(workspace_root=str(tmp_path))
        assert module.workspace_settings_path == tmp_path / ".haywire" / "settings.json"

    def test_an_explicit_path_overrides_the_workspace_root(self, tmp_path):
        target = tmp_path / "elsewhere" / "settings.json"
        module = HaywireModule(workspace_root=str(tmp_path), workspace_settings_path=str(target))
        assert module.workspace_settings_path == target.resolve()


class TestWritesStayContained:
    def test_saving_does_not_touch_the_real_workspace_file(self, registry_for, project_root):
        """The end-to-end guarantee: a save writes to temp, not to the repo."""
        real = (project_root / ".haywire" / "settings.json").resolve()
        before = real.read_bytes() if real.exists() else None

        registry = registry_for()
        registry.save_to_json()

        assert registry._workspace_path is not None
        assert registry._workspace_path.exists(), "the save went somewhere unexpected"
        after = real.read_bytes() if real.exists() else None
        assert after == before, "a test save modified the real workspace settings file"
