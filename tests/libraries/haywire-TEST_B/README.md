# Haywire TEST_B Library

This is a test library B for the Haywire library system.

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
cd tests/libraries/haywire-TEST_B
uv pip install -e .
```

### Production

```bash
uv pip install haywire-TEST_B
```

## Usage

Once installed, the library is automatically discovered by Haywire through entry points.

## Structure

```
📁 haywire-TEST_B/                    # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haywire-TEST_B"          # pip install haywire-TEST_B
│   
│   [project.entry-points."haywire.libraries"]
│   test_b = "test_b:Library"        # ID matches module
│
└── 📁 test_b/                       # Python module
    ├── __init__.py                  # Library class with @library decorator
    ├── 📁 adapters/
    ├── 📁 nodes/
    ├── 📁 renderers/
    ├── 📁 types/
    └── 📁 widgets/
```

## Development

This library is used for testing the Haywire library system functionality.
