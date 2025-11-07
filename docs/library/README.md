# Haywire Library System Documentation

## Overview

The Haywire library system enables modular extension of Haywire through pip-installable packages. Libraries can provide custom nodes, widgets, renderers, and data type adapters.

## Documentation

### For Library Developers

**[Library System Developer Guide](Library_System_Developer_Guide.md)**

Complete guide for creating, configuring, and publishing Haywire libraries:
- Quick start tutorial
- Library structure options
- Configuration reference
- Installation methods
- Publishing to PyPI
- Troubleshooting guide
- Best practices

**Start here if you want to:** Create a new library, publish to PyPI, or use existing libraries.

### For System Developers

**[Library System Technical Reference](Library_System_Technical_Reference.md)**

Technical deep-dive into the library system architecture:
- Component architecture
- 4-priority loading system
- Dual-structure support (flat vs package)
- Module resolution algorithm
- Hot-reload implementation
- Entry point discovery
- DI configuration
- Performance considerations

**Start here if you want to:** Understand the internals, extend the system, or debug issues.

## Quick Links

### Creating a Library

See: [Developer Guide - Creating a New Library](Library_System_Developer_Guide.md#creating-a-new-library)

### Installing Libraries

```bash
# Install from PyPI
uv pip install haywire-my-library

# Install for development (hot-reload)
cd my_library
uv pip install -e .
```

### Entry Point Configuration

```toml
# In your library's pyproject.toml
[project.entry-points."haywire.libraries"]
my_library = "my_library:Library"
```

## Examples

- **Example Library**: See `libraries/example/` in the main repo
- **Core Library**: See `src/haywire/libraries/core/` for the flat structure pattern
