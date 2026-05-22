"""Tests for the `haywire init` project scaffolding command."""

from pathlib import Path

import pytest
import toml


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect Path.home() to a tmp dir so user-global config writes are sandboxed.

    Also patches haywire_studio.config.GLOBAL_CONFIG_DIR which is captured
    at module-import time from Path.home() — without this patch, the module
    keeps pointing at the real home directory.
    """
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr("pathlib.Path.home", lambda: fake)
    import haywire_studio.config as cfg

    monkeypatch.setattr(cfg, "GLOBAL_CONFIG_DIR", fake / ".haywire")
    return fake


@pytest.fixture
def scaffold_project(tmp_path, monkeypatch, fake_home):
    """Scaffold a project in a temp directory and return the project path."""
    monkeypatch.chdir(tmp_path)

    from haywire_studio.init import init_project

    init_project("test-project", auto_sync=False)

    return tmp_path / "test-project"


@pytest.fixture
def scaffold_project_dev(tmp_path, monkeypatch, fake_home):
    """Scaffold a project with --dev pointing to this repo."""
    monkeypatch.chdir(tmp_path)

    from haywire_studio.init import init_project, _get_dev_repo_root

    init_project("test-project-dev", auto_sync=False, dev_repo=_get_dev_repo_root())

    return tmp_path / "test-project-dev"


@pytest.fixture
def scaffold_project_with_fake_home(tmp_path, monkeypatch, fake_home):
    """Like scaffold_project, but with a sandboxed user-global home."""
    monkeypatch.chdir(tmp_path)
    from haywire_studio.init import init_project

    init_project("test-project", auto_sync=False)
    return tmp_path / "test-project"


class TestProjectStructure:
    """Verify that all expected directories and files are created."""

    def test_project_dir_exists(self, scaffold_project):
        assert scaffold_project.is_dir()

    def test_graphs_dir_exists(self, scaffold_project):
        assert (scaffold_project / "graphs").is_dir()

    def test_haywire_config_dir_exists(self, scaffold_project):
        assert (scaffold_project / ".haywire").is_dir()

    def test_haywire_config_file_exists(self, scaffold_project):
        assert (scaffold_project / ".haywire" / "config.toml").is_file()

    def test_project_pyproject_exists(self, scaffold_project):
        assert (scaffold_project / "pyproject.toml").is_file()

    def test_library_dir_exists(self, scaffold_project):
        assert (scaffold_project / "barn" / "haybale-test-project").is_dir()

    def test_library_pyproject_exists(self, scaffold_project):
        assert (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").is_file()

    def test_library_init_exists(self, scaffold_project):
        assert (
            scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project" / "__init__.py"
        ).is_file()


class TestComponentFolders:
    """Verify that all 5 component folders are created with __init__.py."""

    @pytest.mark.parametrize("folder", ["nodes", "types", "widgets", "skins", "adapters"])
    def test_component_folder_exists(self, scaffold_project, folder):
        pkg_dir = scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project"
        assert (pkg_dir / folder).is_dir()

    @pytest.mark.parametrize("folder", ["nodes", "types", "widgets", "skins", "adapters"])
    def test_component_folder_has_init(self, scaffold_project, folder):
        pkg_dir = scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project"
        assert (pkg_dir / folder / "__init__.py").is_file()


class TestProjectPyproject:
    """Verify the generated project pyproject.toml content."""

    def test_project_name(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        assert data["project"]["name"] == "test-project"

    def test_python_version(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        assert data["project"]["requires-python"] == ">=3.10"

    def test_dependencies(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        deps = data["project"]["dependencies"]
        assert "haywire-studio~=0.0.1" in deps
        assert "haybale-core>=1.0.0" not in deps

    def test_workspace_members(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        assert data["tool"]["uv"]["workspace"]["members"] == ["barn/*"]


class TestLibraryPyproject:
    """Verify the generated library pyproject.toml content."""

    def test_library_name(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert data["project"]["name"] == "haybale-test-project"

    def test_library_dependency(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert "haywire-core~=0.0.1" in data["project"]["dependencies"]

    def test_entry_point(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        eps = data["project"]["entry-points"]["haywire.libraries"]
        assert eps["test-project"] == "haybale_test_project:Library"

    def test_hatchling_backend(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert data["build-system"]["build-backend"] == "hatchling.build"

    def test_wheel_packages(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert "haybale_test_project" in data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]

    def test_library_version_is_release(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert data["project"]["version"] == "0.0.1"


class TestLibraryInit:
    """Verify the generated library __init__.py registers all component types."""

    def test_imports_all_registries(self, scaffold_project):
        init_content = (
            scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project" / "__init__.py"
        ).read_text()
        assert "from haywire.core.node.registry import NodeRegistry" in init_content
        assert "from haywire.core.types.registry import TypeRegistry" in init_content
        assert "from haywire.core.adapter.registry import AdapterRegistry" in init_content
        assert "from haywire.ui.widget.registry import WidgetRegistry" in init_content
        assert "from haywire.ui.skin.registry import SkinRegistry" in init_content

    def test_registers_all_folders(self, scaffold_project):
        init_content = (
            scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project" / "__init__.py"
        ).read_text()
        for folder in ["nodes", "types", "adapters", "widgets", "skins"]:
            assert f"base_path / '{folder}'" in init_content

    def test_library_decorator(self, scaffold_project):
        init_content = (
            scaffold_project / "barn" / "haybale-test-project" / "haybale_test_project" / "__init__.py"
        ).read_text()
        assert "@library(" in init_content
        assert "id='test-project'" in init_content
        assert "file_watcher=True" in init_content


class TestProjectMarketplace:
    """The project's <project>/.haywire/marketplace.toml contains [[heaps]] only."""

    def test_project_marketplace_exists(self, scaffold_project):
        assert (scaffold_project / ".haywire" / "marketplace.toml").is_file()

    def test_project_marketplace_has_one_local(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        heaps = data.get("heaps", [])
        assert len(heaps) == 1
        assert heaps[0]["name"] == "haybale-test-project"

    def test_project_marketplace_local_path_is_absolute(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        path = data["heaps"][0]["path"]
        assert Path(path).is_absolute()
        assert Path(path) == scaffold_project / "barn" / "haybale-test-project"

    def test_project_marketplace_has_no_caches(self, scaffold_project):
        """No [[caches]] section — refresh (Plan E) populates that."""
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        assert data.get("caches", []) == []


class TestDevMode:
    """`haywire init --dev` adds editable source paths to the generated pyprojects."""

    def test_project_has_sources(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        sources = data["tool"]["uv"]["sources"]
        assert "haywire-studio" in sources
        assert "haywire-core" in sources
        assert "haybale-core" in sources
        assert "haybale-studio" in sources

    def test_sources_are_editable(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        for pkg in ["haywire-studio", "haywire-core"]:
            assert data["tool"]["uv"]["sources"][pkg]["editable"] is True

    def test_source_paths_exist(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        for pkg in ["haywire-studio", "haywire-core"]:
            assert Path(data["tool"]["uv"]["sources"][pkg]["path"]).is_dir()

    def test_library_has_framework_source(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / "barn" / "haybale-test-project-dev" / "pyproject.toml").read_text()
        )
        sources = data["tool"]["uv"]["sources"]
        assert "haywire-core" in sources
        assert sources["haywire-core"]["editable"] is True

    def test_dev_project_marketplace_includes_dev_repo_libs(self, scaffold_project_dev):
        """In --dev mode the project marketplace holds the scaffolded library AND
        every dev-repo barn library, scoped to this project (not user-global)."""
        data = toml.loads((scaffold_project_dev / ".haywire" / "marketplace.toml").read_text())
        names = {entry["name"] for entry in data.get("heaps", [])}
        # The scaffolded project library:
        assert "haybale-test-project-dev" in names
        # A representative sample of dev-repo libraries:
        for dev_lib in ["haybale-core", "haybale-studio", "haybale-haystack"]:
            assert dev_lib in names, f"missing dev-repo library: {dev_lib}"
        assert data.get("caches", []) == []


class TestNameSanitization:
    """Verify project names are correctly sanitized for Python modules."""

    def test_hyphens_become_underscores(self, tmp_path, monkeypatch, fake_home):
        monkeypatch.chdir(tmp_path)
        from haywire_studio.init import init_project

        init_project("my-cool-project", auto_sync=False)
        assert (
            tmp_path / "my-cool-project" / "barn" / "haybale-my-cool-project" / "haybale_my_cool_project"
        ).is_dir()

    def test_existing_dir_exits(self, tmp_path, monkeypatch, fake_home):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "existing").mkdir()
        from haywire_studio.init import init_project

        with pytest.raises(SystemExit):
            init_project("existing", auto_sync=False)


class TestUserGlobalStaysEmpty:
    """`haywire init` only creates ~/.haywire/marketplace.toml as an empty file.

    The user-global marketplace is reserved for user opt-in subscriptions
    ([[markets]], [[stalls]]). Heaps — the project's own library and any
    --dev sibling libraries — live in the project marketplace instead.
    """

    def test_user_global_marketplace_file_exists(self, scaffold_project_with_fake_home, fake_home):
        # ensure_global_config still creates the directory + an empty file.
        assert (fake_home / ".haywire" / "marketplace.toml").is_file()

    def test_user_global_has_no_heaps_for_project(self, scaffold_project_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        assert data.get("heaps", []) == []

    def test_user_global_has_no_caches_for_project(self, scaffold_project_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        assert data.get("caches", []) == []


class TestSameNameAcrossProjectsAllowed:
    """Two unrelated projects may share the same library name now that
    [[heaps]] are project-scoped — no cross-project G5 refusal at init time.
    """

    def test_second_init_with_same_name_succeeds(self, tmp_path, monkeypatch, fake_home):
        from haywire_studio.init import init_project

        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.chdir(a)
        init_project("test-project", auto_sync=False)

        b = tmp_path / "b"
        b.mkdir()
        monkeypatch.chdir(b)
        init_project("test-project", auto_sync=False)

        # Both project directories exist with their own marketplaces.
        for parent in (a, b):
            project_mp = parent / "test-project" / ".haywire" / "marketplace.toml"
            assert project_mp.is_file()
            data = toml.loads(project_mp.read_text())
            names = [entry["name"] for entry in data.get("heaps", [])]
            assert names == ["haybale-test-project"]


class TestDevModeProjectRegistration:
    """`haywire init --dev` registers dev-repo libraries in the *project* marketplace."""

    @pytest.fixture
    def scaffold_dev_with_fake_home(self, tmp_path, monkeypatch, fake_home):
        monkeypatch.chdir(tmp_path)
        from haywire_studio.init import _get_dev_repo_root, init_project

        init_project("test-dev-project", auto_sync=False, dev_repo=_get_dev_repo_root())
        return tmp_path / "test-dev-project"

    def test_project_marketplace_has_all_dev_repo_libraries(self, scaffold_dev_with_fake_home):
        data = toml.loads((scaffold_dev_with_fake_home / ".haywire" / "marketplace.toml").read_text())
        names = {entry["name"] for entry in data.get("heaps", [])}

        # The scaffolded project library:
        assert "haybale-test-dev-project" in names

        # The dev-repo libraries:
        for dev_lib in [
            "haybale-core",
            "haybale-studio",
            "haybale-graph-editor",
            "haybale-haystack",
            "haybale-example",
            "haybale-testing",
            "haybale-visiongraph",
            "haybale-TEST_A",
        ]:
            assert dev_lib in names, f"missing dev-repo library: {dev_lib}"

    def test_dev_locals_paths_point_at_dev_repo(self, scaffold_dev_with_fake_home):
        from haywire_studio.init import _get_dev_repo_root

        data = toml.loads((scaffold_dev_with_fake_home / ".haywire" / "marketplace.toml").read_text())
        dev_root = _get_dev_repo_root()

        for entry in data["heaps"]:
            if entry["name"] == "haybale-test-dev-project":
                continue  # The project's own library lives in the project, not the dev repo
            path = entry["path"]
            assert path.startswith(dev_root), f"{entry['name']}: {path} not under {dev_root}"
            assert Path(path).is_dir(), f"{entry['name']}: {path} does not exist"

    def test_dev_mode_does_not_write_heaps_to_user_global(self, scaffold_dev_with_fake_home, fake_home):
        """--dev keeps the user-global marketplace's [[heaps]] empty."""
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        assert data.get("heaps", []) == []

    def test_regular_init_does_not_register_dev_repo_libraries(self, scaffold_project_with_fake_home):
        """Without --dev, only the project's own library appears in the project marketplace."""
        data = toml.loads((scaffold_project_with_fake_home / ".haywire" / "marketplace.toml").read_text())
        names = [entry["name"] for entry in data.get("heaps", [])]
        assert names == ["haybale-test-project"]
