# Haywire Example Library

This is an example library demonstrating the Haywire library system capabilities.

## Features

- **Custom Types**: Example data types with serialization support
- **Custom Nodes**: Nodes for data processing and display
- **Custom Widgets**: UI widgets for node configuration
- **Custom Renderers**: Node rendering customization
- **Adapters**: Integration with external systems

## Installation

### Development (Editable Install)

For development with hot-reload support:

```bash
cd libraries/example
uv pip install -e .
```

### Production

```bash
uv pip install haybale-example
```

## Usage

Once installed, the library is automatically discovered by Haywire through entry points.

The library provides:
- Display nodes for visualization
- Dynamic nodes for runtime node creation
- Example custom data types
- Custom UI widgets and renderers

## Structure

```
📁 haybale-EXAMPLE/                    # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haybale-EXAMPLE"          # pip install haybale-cv-tools
│   
│   [project.entry-points."haywire.libraries"]
│   cv_tools = "cv_tools:Library"      # ID matches module
│
└── 📁 haybale_EXAMPLE/                        # import cv_tools
    ├── __init__.py
    │   @library(
    │       id='EXAMPLE',              # Matches entry point
    │       label='Computer Vision Tools',
    │   )
    │   class Library(BaseLibrary): ...
    ├── nodes/               # Custom nodes
    ├── types/               # Custom data types (if any)
    ├── widgets/             # Custom UI widgets
    ├── renderers/           # Custom node renderers
    └── adapters/            # External system adapters
```

## Development

After making changes to the library code:

1. **With editable install**: Changes are immediately reflected (after hot-reload)
2. **Without editable install**: Reinstall the package

## Entry Point

This library is discoverable via the `haywire.libraries` entry point:

```toml
[project.entry-points."haywire.libraries"]
example = "example:Library"
```

## Dependencies

- haywire-core >= 1.0.0
