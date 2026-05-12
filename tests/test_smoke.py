"""
Smoke tests to verify basic test infrastructure.

These tests ensure that the testing framework itself is working.
"""

import pytest
from injector import Injector


@pytest.mark.unit
class TestSmoke:
    """Basic smoke tests."""

    def test_di_injector_fixture(self, test_injector: Injector):
        """Test that DI injector fixture works."""
        assert test_injector is not None
        assert isinstance(test_injector, Injector)

    def test_project_root_fixture(self, project_root):
        """Test that project root fixture works."""
        assert project_root is not None
        assert project_root.exists()
        assert (project_root / "pyproject.toml").exists()

    def test_registries_are_available(self, node_registry, adapter_registry, type_registry):
        """Test that registry fixtures work."""
        assert node_registry is not None
        assert adapter_registry is not None
        assert type_registry is not None

    def test_factories_are_available(self, node_factory, adapter_factory):
        """Test that factory fixtures work."""
        assert node_factory is not None
        assert adapter_factory is not None
