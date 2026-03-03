"""Tests for the `haywire init` project scaffolding command."""

import sys
from pathlib import Path

import pytest
import toml


@pytest.fixture
def scaffold_project(tmp_path, monkeypatch):
    """Scaffold a project in a temp directory and return the project path."""
    monkeypatch.chdir(tmp_path)

    from haywire_app.init import init_project
    init_project('test-project', auto_sync=False)

    return tmp_path / 'test-project'


@pytest.fixture
def scaffold_project_dev(tmp_path, monkeypatch):
    """Scaffold a project with --dev pointing to this repo."""
    monkeypatch.chdir(tmp_path)

    from haywire_app.init import init_project, _get_dev_repo_root
    init_project('test-project-dev', auto_sync=False, dev_repo=_get_dev_repo_root())

    return tmp_path / 'test-project-dev'


class TestProjectStructure:
    """Verify that all expected directories and files are created."""

    def test_project_dir_exists(self, scaffold_project):
        assert scaffold_project.is_dir()

    def test_graphs_dir_exists(self, scaffold_project):
        assert (scaffold_project / 'graphs').is_dir()

    def test_haywire_config_dir_exists(self, scaffold_project):
        assert (scaffold_project / '.haywire').is_dir()

    def test_haywire_config_file_exists(self, scaffold_project):
        assert (scaffold_project / '.haywire' / 'config.toml').is_file()

    def test_project_pyproject_exists(self, scaffold_project):
        assert (scaffold_project / 'pyproject.toml').is_file()

    def test_library_dir_exists(self, scaffold_project):
        assert (scaffold_project / 'barn' /'haybale-test-project').is_dir()

    def test_library_pyproject_exists(self, scaffold_project):
        assert (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').is_file()

    def test_library_init_exists(self, scaffold_project):
        assert (scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project' / '__init__.py').is_file()


class TestComponentFolders:
    """Verify that all 5 component folders are created with __init__.py."""

    @pytest.mark.parametrize('folder', ['nodes', 'types', 'widgets', 'skins', 'adapters'])
    def test_component_folder_exists(self, scaffold_project, folder):
        pkg_dir = scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project'
        assert (pkg_dir / folder).is_dir()

    @pytest.mark.parametrize('folder', ['nodes', 'types', 'widgets', 'skins', 'adapters'])
    def test_component_folder_has_init(self, scaffold_project, folder):
        pkg_dir = scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project'
        assert (pkg_dir / folder / '__init__.py').is_file()


class TestProjectPyproject:
    """Verify the generated project pyproject.toml content."""

    def test_project_name(self, scaffold_project):
        data = toml.loads((scaffold_project / 'pyproject.toml').read_text())
        assert data['project']['name'] == 'test-project'

    def test_python_version(self, scaffold_project):
        data = toml.loads((scaffold_project / 'pyproject.toml').read_text())
        assert data['project']['requires-python'] == '>=3.10'

    def test_dependencies(self, scaffold_project):
        data = toml.loads((scaffold_project / 'pyproject.toml').read_text())
        deps = data['project']['dependencies']
        assert 'haywire-app>=0.1.0' in deps
        assert 'haybale-core>=1.0.0' not in deps

    def test_workspace_members(self, scaffold_project):
        data = toml.loads((scaffold_project / 'pyproject.toml').read_text())
        assert data['tool']['uv']['workspace']['members'] == ['barn/*']

class TestLibraryPyproject:
    """Verify the generated library pyproject.toml content."""

    def test_library_name(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').read_text()
        )
        assert data['project']['name'] == 'haybale-test-project'

    def test_library_dependency(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').read_text()
        )
        assert 'haywire-framework>=0.1.0' in data['project']['dependencies']

    def test_entry_point(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').read_text()
        )
        eps = data['project']['entry-points']['haywire.libraries']
        assert eps['test-project'] == 'haybale_test_project:Library'

    def test_hatchling_backend(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').read_text()
        )
        assert data['build-system']['build-backend'] == 'hatchling.build'

    def test_wheel_packages(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / 'barn' /'haybale-test-project' / 'pyproject.toml').read_text()
        )
        assert 'haybale_test_project' in data['tool']['hatch']['build']['targets']['wheel']['packages']


class TestLibraryInit:
    """Verify the generated library __init__.py registers all component types."""

    def test_imports_all_registries(self, scaffold_project):
        init_content = (
            scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project' / '__init__.py'
        ).read_text()
        assert 'from haywire.core.node.registry import NodeRegistry' in init_content
        assert 'from haywire.core.types.registry import TypeRegistry' in init_content
        assert 'from haywire.core.adapter.registry import AdapterRegistry' in init_content
        assert 'from haywire.ui.widget.registry import WidgetRegistry' in init_content
        assert 'from haywire.ui.skin.registry import SkinRegistry' in init_content

    def test_registers_all_folders(self, scaffold_project):
        init_content = (
            scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project' / '__init__.py'
        ).read_text()
        for folder in ['nodes', 'types', 'adapters', 'widgets', 'skins']:
            assert f"base_path / '{folder}'" in init_content

    def test_library_decorator(self, scaffold_project):
        init_content = (
            scaffold_project / 'barn' /'haybale-test-project' / 'haybale_test_project' / '__init__.py'
        ).read_text()
        assert "@library(" in init_content
        assert "id='test-project'" in init_content
        assert "file_watcher=True" in init_content


class TestDevMode:
    """Verify --dev flag adds editable source paths."""

    def test_project_has_sources(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / 'pyproject.toml').read_text())
        sources = data['tool']['uv']['sources']
        assert 'haywire-app' in sources
        assert 'haywire-framework' in sources
        assert 'haybale-core' not in sources

    def test_sources_are_editable(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / 'pyproject.toml').read_text())
        for pkg in ['haywire-app', 'haywire-framework']:
            assert data['tool']['uv']['sources'][pkg]['editable'] is True

    def test_source_paths_exist(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / 'pyproject.toml').read_text())
        for pkg in ['haywire-app', 'haywire-framework']:
            assert Path(data['tool']['uv']['sources'][pkg]['path']).is_dir()

    def test_library_has_framework_source(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / 'barn' /'haybale-test-project-dev' / 'pyproject.toml').read_text()
        )
        sources = data['tool']['uv']['sources']
        assert 'haywire-framework' in sources
        assert sources['haywire-framework']['editable'] is True

    def test_dev_marketplace_exists(self, scaffold_project_dev):
        assert (scaffold_project_dev / '.haywire' / 'marketplace.toml').is_file()

    def test_dev_marketplace_lists_libraries(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / '.haywire' / 'marketplace.toml').read_text()
        )
        names = [pkg['name'] for pkg in data['packages']]
        assert 'haybale-core' in names
        assert 'haybale-example' in names
        assert 'haybale-testing' in names
        assert 'haybale-visiongraph' in names
        assert 'haybale-TEST_A' in names

    def test_dev_marketplace_has_local_source(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / '.haywire' / 'marketplace.toml').read_text()
        )
        for pkg in data['packages']:
            assert pkg['source'] == 'local'

    def test_dev_marketplace_install_specs_are_paths(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / '.haywire' / 'marketplace.toml').read_text()
        )
        for pkg in data['packages']:
            assert Path(pkg['install_spec']).is_dir(), f"{pkg['name']}: {pkg['install_spec']} not found"

class TestNameSanitization:
    """Verify project names are correctly sanitized for Python modules."""

    def test_hyphens_become_underscores(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from haywire_app.init import init_project
        init_project('my-cool-project', auto_sync=False)
        assert (tmp_path / 'my-cool-project' / 'barn' /'haybale-my-cool-project' / 'haybale_my_cool_project').is_dir()

    def test_existing_dir_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'existing').mkdir()
        from haywire_app.init import init_project
        with pytest.raises(SystemExit):
            init_project('existing', auto_sync=False)
