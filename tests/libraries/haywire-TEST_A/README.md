# Haywire TEST_A Library

This is a test library for the Haywire library system.

## Features

- **Custom Types**: Test data types with serialization support
- **Custom Nodes**: Test nodes for data processing
- **Custom Widgets**: Test UI widgets for node configuration
- **Custom Renderers**: Test node rendering customization
- **Adapters**: Test integration with external systems

## Installation

### Development (Editable Install)

For development with hot-reload support:

```bash
cd tests/libraries/haywire-TEST_A
uv pip install -e .
```

### Production

```bash
uv pip install haywire-TEST_A
```

## Usage

Once installed, the library is automatically discovered by Haywire through entry points.

## Structure

```
📁 haywire-TEST_A/                    # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haywire-TEST_A"          # pip install haywire-TEST_A
│   
│   [project.entry-points."haywire.libraries"]
│   test_a = "test_a:Library"        # ID matches module
│
└── 📁 test_a/                       # Python module
    ├── __init__.py                  # Library class with @library decorator
    ├── 📁 adapters/
    ├── 📁 nodes/
    ├── 📁 renderers/
    ├── 📁 types/
    └── 📁 widgets/
```

## Development

This library is used for testing the Haywire library system functionality.
