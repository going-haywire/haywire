# Haywire Testing Framework

The Haywire testing framework is built on pytest with full dependency injection (DI) support.

## Test Structure

Tests mirror the source code structure:

```
tests/
├── __init__.py
├── conftest.py                 # Root fixtures (DI, paths, registries)
├── test_smoke.py              # Basic smoke tests
├── libraries/                 # Test libraries for integration tests
├── core/                      # Core module tests
│   ├── conftest.py           # Core-specific fixtures
│   ├── test_node/            # Node system tests
│   ├── test_graph/           # Graph system tests
│   └── test_execution/       # Execution/interpreter tests
└── ui/                        # UI component tests
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run only unit tests (fast, isolated)
uv run pytest -m unit

# Run only integration tests (slower, full system)
uv run pytest -m integration

# Run specific test file
uv run pytest tests/test_smoke.py

# Run with coverage
uv run pytest --cov=src/haywire --cov=libraries

# Run in parallel (if pytest-xdist installed)
uv run pytest -n auto
```

## Test Markers

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Slower tests with full library system
- `@pytest.mark.slow` - Tests that take significant time
- `@pytest.mark.ui` - UI-related tests
- `@pytest.mark.core` - Core functionality tests

## Dependency Injection in Tests

### Unit Test Fixtures

For fast, isolated unit tests that don't need libraries:

```python
@pytest.mark.unit
def test_something(
    test_injector,      # Fresh DI injector per test
    node_registry,      # Empty node registry
    node_factory,       # Node factory (DI-provided)
):
    # Test without loading full library system
    pass
```

### Integration Test Fixtures

For tests requiring the full library system:

```python
@pytest.mark.integration  
def test_with_libraries(
    library_system,              # Session-scoped, loads libraries once
    integration_node_registry,   # Registry with all libraries
    integration_node_factory,    # Factory with all libraries
):
    # Test with real nodes from libraries
    pass
```

### Available Fixtures

#### Path Fixtures
- `project_root` - Project root directory (session-scoped)
- `test_library_path` - Path to test libraries

#### DI Fixtures
- `test_injector` - Fresh injector per test (function-scoped)
- `test_injector_with_undo` - Injector with undo system enabled
- `library_system` - Full library system (session-scoped, expensive)

#### Registry Fixtures
- `node_registry` - Node registry from DI
- `adapter_registry` - Adapter registry from DI
- `type_registry` - Type registry from DI

#### Factory Fixtures
- `node_factory` - Node factory from DI
- `adapter_factory` - Adapter factory from DI

#### Service Fixtures
- `history_manager` - Undo/redo manager

#### Integration Fixtures
- `integration_node_registry` - Registry with libraries loaded
- `integration_node_factory` - Factory with libraries loaded

#### Core-Specific Fixtures
- `empty_graph` - Empty HaywireGraph for testing

## CI/CD Integration

Tests run automatically via GitHub Actions on:
- Push to `main` or `develop` branches
- Pull requests
- Manual workflow dispatch

The CI workflow:
1. Tests on multiple Python versions (3.10, 3.11, 3.12)
2. Tests on multiple OS (Ubuntu, macOS)
3. Runs unit tests with coverage
4. Runs integration tests
5. Uploads coverage to Codecov
6. Runs linting (ruff) and type checking (mypy)

## Configuration

### pytest.ini

Test configuration is in `pytest.ini` at the project root:
- Test discovery patterns
- Coverage settings
- Marker definitions
- Output formatting

### conftest.py

Fixtures and test setup are in `conftest.py` files:
- Root `conftest.py` - Project-wide fixtures
- Module-specific `conftest.py` - Additional module fixtures

## Writing New Tests

### Basic Test

```python
import pytest
from haywire.core.graph.base import BaseGraph

@pytest.mark.unit
@pytest.mark.core  
class TestMyFeature:
    def test_basic_functionality(self):
        # Simple test without fixtures
        assert True
    
    def test_with_graph(self, empty_graph: BaseGraph):
        # Test using empty graph fixture
        assert empty_graph.graph_id == 'test_graph'
```

### Integration Test with Libraries

```python
@pytest.mark.integration
@pytest.mark.slow
def test_with_real_nodes(library_system):
    """Test that requires full library system."""
    node_factory = library_system.get_node_factory()
    
    # Create real nodes from libraries
    # ...
```

## Circular Import Handling

**IMPORTANT**: Due to circular dependencies in the haywire core, imports in `conftest.py` must follow a specific order:

```python
# Import graph module FIRST to resolve circular imports
from haywire.core.graph.editor import Editor  # noqa: F401
from haywire.core.graph.base import BaseGraph  # noqa: F401

# Then import other modules
from haywire.core.node.registry import NodeRegistry
# ...
```

This same pattern should be followed when creating new test files that import multiple haywire modules.

## Adding New Test Modules

1. Create test file: `tests/[module]/test_[feature].py`
2. Add module-specific fixtures in `tests/[module]/conftest.py` if needed
3. Use appropriate markers (`@pytest.mark.unit`, etc.)
4. Follow the import order pattern if importing multiple core modules


## Best Practices

1. **Keep unit tests fast** - Don't load libraries unless needed
2. **Use integration marker** - Mark slow tests appropriately
3. **Test in isolation** - Each test should be independent
4. **Use fixtures** - Leverage DI fixtures for setup
5. **Follow import order** - Respect circular import requirements
6. **Update markers** - Use markers for better test organization
