# Haybale Core Library

This is a core library providing essential types, nodes, widgets, and renderers for the haywire node system.

## Features

- **Types**: Core data types with serialization support
- **Nodes**: Nodes for data processing and display
- **Widgets**: UI widgets for node configuration
- **Renderers**: Node rendering customization
- **Adapters**: Integration with external systems

## Installation

### Development (Editable Install)

For development with hot-reload support:

```bash
cd libraries/haybale-core
uv pip install -e .
```

### Production

```bash
uv pip install haybale-core
```

## Usage

Once installed, the library is automatically discovered by Haywire through entry points.

The library provides:
- Display nodes for visualization
- Dynamic nodes for runtime node creation
- Core data types
- Core UI widgets and renderers

## Structure

```
📁 haybale-core/                    # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haybale-core"          # pip install haybale-core
│   
│   [project.entry-points."haywire.libraries"]
│   core = "haybale_core:Library"      # ID matches module
│
└── 📁 haybale_core/                        # import haybale_core
    ├── __init__.py
    │   @library(
    │       id='CORE',              # Matches entry point
    │       label='Core Library',
    │   )
    │   class Library(BaseLibrary): ...
    ├── nodes/               # Core nodes
    ├── types/               # Core data types (if any)
    ├── widgets/             # Core UI widgets
    ├── renderers/           # Core node renderers
    └── adapters/            # Core system adapters
```

## Dependencies

- None
