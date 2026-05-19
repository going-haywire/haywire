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
    """The project's <project>/.haywire/marketplace.toml contains [[locals]] only."""

    def test_project_marketplace_exists(self, scaffold_project):
        assert (scaffold_project / ".haywire" / "marketplace.toml").is_file()

    def test_project_marketplace_has_one_local(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        assert len(locals_) == 1
        assert locals_[0]["name"] == "haybale-test-project"

    def test_project_marketplace_local_path_is_absolute(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        path = data["locals"][0]["path"]
        assert Path(path).is_absolute()
        assert Path(path) == scaffold_project / "barn" / "haybale-test-project"

    def test_project_marketplace_has_no_packages(self, scaffold_project):
        """No [[packages]] section — refresh (Plan E) populates that."""
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        assert data.get("packages", []) == []


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

    def test_dev_project_marketplace_still_locals_only(self, scaffold_project_dev):
        """Even in --dev mode, the PROJECT marketplace is just the project's library.
        Dev-repo libraries go to the user-global marketplace (tested in TestUserGlobalRegistration)."""
        data = toml.loads((scaffold_project_dev / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        assert len(locals_) == 1
        assert locals_[0]["name"] == "haybale-test-project-dev"
        assert data.get("packages", []) == []


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


class TestUserGlobalRegistration:
    """`haywire init` writes a [[locals]] entry to ~/.haywire/marketplace.toml."""

    def test_user_global_marketplace_exists_after_init(self, scaffold_project_with_fake_home, fake_home):
        global_mp = fake_home / ".haywire" / "marketplace.toml"
        assert global_mp.is_file()

    def test_user_global_has_local_for_project(self, scaffold_project_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        names = [entry["name"] for entry in locals_]
        assert "haybale-test-project" in names

    def test_user_global_local_path_is_absolute_to_project(self, scaffold_project_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        local = next(e for e in data["locals"] if e["name"] == "haybale-test-project")
        assert Path(local["path"]).is_absolute()
        assert "test-project" in local["path"]
        assert local["path"].endswith("barn/haybale-test-project")


class TestG5NameCollision:
    """`haywire init` refuses if a [[locals]] with the same name already exists."""

    def test_second_init_with_same_name_refused(self, tmp_path, monkeypatch, fake_home):
        from haywire_studio.init import init_project

        # First project at /tmp/a/test-project
        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.chdir(a)
        init_project("test-project", auto_sync=False)

        # Second project trying to claim the same library name at /tmp/b/test-project
        b = tmp_path / "b"
        b.mkdir()
        monkeypatch.chdir(b)
        with pytest.raises(SystemExit) as exc_info:
            init_project("test-project", auto_sync=False)

        assert exc_info.value.code != 0

    def test_collision_does_not_create_second_project_dir(self, tmp_path, monkeypatch, fake_home):
        from haywire_studio.init import init_project

        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.chdir(a)
        init_project("test-project", auto_sync=False)

        b = tmp_path / "b"
        b.mkdir()
        monkeypatch.chdir(b)
        with pytest.raises(SystemExit):
            init_project("test-project", auto_sync=False)

        # Verify the second project's directory was not created (or was rolled back).
        assert not (b / "test-project").exists()


class TestDevModeUserGlobalRegistration:
    """`haywire init --dev` also registers dev-repo libraries in the user-global marketplace."""

    @pytest.fixture
    def scaffold_dev_with_fake_home(self, tmp_path, monkeypatch, fake_home):
        monkeypatch.chdir(tmp_path)
        from haywire_studio.init import _get_dev_repo_root, init_project

        init_project("test-dev-project", auto_sync=False, dev_repo=_get_dev_repo_root())
        return tmp_path / "test-dev-project"

    def test_user_global_has_all_dev_repo_libraries(self, scaffold_dev_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        names = {entry["name"] for entry in data.get("locals", [])}

        # The project's own library:
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

    def test_dev_locals_paths_point_at_dev_repo(self, scaffold_dev_with_fake_home, fake_home):
        from haywire_studio.init import _get_dev_repo_root

        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        dev_root = _get_dev_repo_root()

        for entry in data["locals"]:
            if entry["name"] == "haybale-test-dev-project":
                continue  # The project's own library lives in the project, not the dev repo
            path = entry["path"]
            assert path.startswith(dev_root), f"{entry['name']}: {path} not under {dev_root}"
            assert Path(path).is_dir(), f"{entry['name']}: {path} does not exist"

    def test_regular_init_does_not_register_dev_repo_libraries(
        self, scaffold_project_with_fake_home, fake_home
    ):
        """Without --dev, only the project's own library should appear."""
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        names = [entry["name"] for entry in data.get("locals", [])]
        assert names == ["haybale-test-project"]
