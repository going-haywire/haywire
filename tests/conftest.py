"""
Root pytest configuration with DI fixtures.

Provides fixtures for different test scopes and scenarios.
"""

import pytest
from pathlib import Path
from typing import Generator
from injector import Injector

from haywire.core.di.test_config import create_test_injector, create_test_library_system

# IMPORTANT: Import order matters due to circular dependencies
# Import graph module first to resolve circular imports
from haywire.core.graph.editor import Editor  # noqa: F401
from haywire.core.graph.base import BaseGraph  # noqa: F401

# Import types only when needed to avoid circular imports
from haywire.core.node.registry import NodeRegistry
from haywire.core.node.factory import NodeFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.types.registry import TypeRegistry
from haywire.core.undo.interfaces import IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig


# ==============================================================================
# Pytest Configuration
# ==============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower, full system)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "ui: UI-related tests")
    config.addinivalue_line("markers", "core: Core functionality tests")


# ==============================================================================
# Path Fixtures
# ==============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    # Walk up from tests/ to find pyproject.toml
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


@pytest.fixture(scope="session")
def test_library_path(project_root: Path) -> Path:
    """Get path to test libraries."""
    return project_root / "barn"


# ==============================================================================
# DI Injector Fixtures
# ==============================================================================


@pytest.fixture(scope="function")
def test_injector(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide a fresh test injector for each test.

    This is for unit tests that need DI but not full library loading.
    """
    injector = create_test_injector(
        workspace_root=str(project_root), enable_file_watching=False, load_libraries=False
    )

    yield injector

    # Cleanup if needed
    # (registries are fresh per test, so no cleanup required)


@pytest.fixture(scope="function")
def test_injector_with_undo(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide test injector (kept for backwards-compat; undo is now per-graph).
    """
    injector = create_test_injector(
        workspace_root=str(project_root),
        enable_file_watching=False,
        load_libraries=False,
    )

    yield injector


@pytest.fixture(scope="session")
def library_system(project_root: Path, test_library_path: Path):
    """
    Provide fully initialized library system for integration tests.

    This is expensive, so it's session-scoped and shared across tests.
    Mark tests using this with @pytest.mark.integration
    """
    # Import here to avoid circular imports at module level
    from haywire.core.di.config import set_library_system, set_global_injector

    service = create_test_library_system(
        workspace_root=str(project_root),
        library_paths=[str(test_library_path)],
        load_libraries=True,
        enable_file_watching=False,
    )

    # IMPORTANT: Set global library system for graph operations
    set_library_system(service)
    set_global_injector(service.injector)

    yield service

    # Cleanup
    # Stop file watchers if any
    lib_registry = service.get_library_registry()
    if hasattr(lib_registry, "stop_file_watching"):
        lib_registry.stop_file_watching()

    # Clear global references
    set_library_system(None)
    set_global_injector(None)


# ==============================================================================
# Registry Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def node_registry(test_injector: Injector) -> NodeRegistry:
    """Get node registry from DI."""
    return test_injector.get(NodeRegistry)


@pytest.fixture
def adapter_registry(test_injector: Injector) -> AdapterRegistry:
    """Get adapter registry from DI."""
    return test_injector.get(AdapterRegistry)


@pytest.fixture
def type_registry(test_injector: Injector) -> TypeRegistry:
    """Get type registry from DI."""
    return test_injector.get(TypeRegistry)


# ==============================================================================
# Factory Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def node_factory(test_injector: Injector) -> NodeFactory:
    """Get node factory from DI."""
    return test_injector.get(NodeFactory)


@pytest.fixture
def adapter_factory(test_injector: Injector) -> AdapterFactory:
    """Get adapter factory from DI."""
    return test_injector.get(AdapterFactory)


# ==============================================================================
# Service Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def history_manager() -> IHistoryManager:
    """Provide a fresh per-graph HistoryManager (no longer from DI)."""
    return HistoryManager(UndoConfig(max_actions=50))


# ==============================================================================
# Integration Test Fixtures
# ==============================================================================


@pytest.fixture
def integration_node_registry(library_system) -> NodeRegistry:
    """Get node registry with all libraries loaded."""
    return library_system.get_node_registry()


@pytest.fixture
def integration_node_factory(library_system) -> NodeFactory:
    """Get node factory with all libraries loaded."""
    return library_system.get_node_factory()
