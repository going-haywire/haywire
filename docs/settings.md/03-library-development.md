# Library Development Guide

This guide covers how library developers can create custom global settings that integrate with Haywire's settings system.

## Overview

As a library developer, you can:

1. Define global settings for your library
2. Register them with the global registry
3. Provide UI metadata for settings panels
4. Let users configure your library via TOML or GUI

---

## Creating a Settings Module

### File Structure

```
my_library/
├── __init__.py
├── nodes/
│   └── ...
└── settings.py          # Settings definitions
```

### Basic Settings Module

```python
# my_library/settings.py
"""
Settings definitions for My Library.

These settings are registered with the global registry and available
to all nodes and code that uses this library.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.settings import GlobalSettingsRegistry


# Use a consistent prefix for your library
NAMESPACE = 'my_library'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """
    Register all settings for this library.
    
    Called during library initialization.
    
    Args:
        registry: The global settings registry
    """
    
    # Feature toggles
    registry.define(
        f'{NAMESPACE}.feature_x_enabled',
        default=True,
        label='Enable Feature X',
        description='Toggle the experimental Feature X',
        category=NAMESPACE,
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.feature_y_enabled',
        default=False,
        label='Enable Feature Y',
        description='Toggle Feature Y (requires Feature X)',
        category=NAMESPACE,
        ui_order=11
    )
    
    # Connection settings
    registry.define(
        f'{NAMESPACE}.api_url',
        default='https://api.example.com',
        label='API URL',
        description='Base URL for the external API',
        category=f'{NAMESPACE}.connection',
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.api_timeout',
        default=30,
        label='API Timeout (s)',
        description='Request timeout in seconds',
        category=f'{NAMESPACE}.connection',
        min_value=5,
        max_value=300,
        ui_order=20
    )
    
    registry.define(
        f'{NAMESPACE}.max_retries',
        default=3,
        label='Max Retries',
        description='Number of retry attempts on failure',
        category=f'{NAMESPACE}.connection',
        min_value=0,
        max_value=10,
        ui_order=30
    )
    
    # Performance settings
    registry.define(
        f'{NAMESPACE}.cache_enabled',
        default=True,
        label='Enable Caching',
        description='Cache API responses',
        category=f'{NAMESPACE}.performance',
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.cache_ttl_seconds',
        default=3600,
        label='Cache TTL (s)',
        description='How long to keep cached responses',
        category=f'{NAMESPACE}.performance',
        min_value=60,
        max_value=86400,
        ui_order=20
    )
    
    registry.define(
        f'{NAMESPACE}.parallel_requests',
        default=4,
        label='Parallel Requests',
        description='Maximum concurrent API requests',
        category=f'{NAMESPACE}.performance',
        min_value=1,
        max_value=20,
        ui_order=30
    )
```

---

## Registering with the Global System

### Option 1: Entry Point (Recommended)

Register via Python package entry points in `pyproject.toml`:

```toml
[project.entry-points."haywire.settings"]
my_library = "my_library.settings:register"
```

Haywire automatically discovers and calls these during startup.

### Option 2: Library Load Hook

Register when your library is loaded:

```python
# my_library/__init__.py
"""My Library for Haywire."""

def on_library_enable():
    """Called when the library is enabled."""
    from haywire.core.di.config import get_settings_registry
    from .settings import register
    
    registry = get_settings_registry()
    register(registry)


def on_library_disable():
    """Called when the library is disabled."""
    # Optionally clean up settings
    pass
```

### Option 3: Manual Registration

For testing or special cases:

```python
from haywire.core.di.config import get_settings_registry
from my_library.settings import register

# Register settings manually
registry = get_settings_registry()
register(registry)
```

---

## Namespacing

### Conventions

Always prefix your settings with your library name:

```python
# Good: clear namespace
'my_library.api_url'
'my_library.connection.timeout'
'my_library.processing.algorithm'

# Bad: generic names that might conflict
'api_url'
'timeout'
'algorithm'
```

### Category Hierarchy

Use dot notation for nested categories:

```python
registry.define('my_lib.feature', ..., category='my_lib')
registry.define('my_lib.api.url', ..., category='my_lib.api')
registry.define('my_lib.api.key', ..., category='my_lib.api')
registry.define('my_lib.cache.size', ..., category='my_lib.cache')
```

This creates a UI hierarchy:

```
my_lib
├── feature
├── api
│   ├── url
│   └── key
└── cache
    └── size
```

---

## Validation & Constraints

### Min/Max Values

```python
registry.define(
    'my_lib.port',
    default=8080,
    min_value=1,
    max_value=65535,
    label='Port Number'
)

registry.define(
    'my_lib.ratio',
    default=0.5,
    min_value=0.0,
    max_value=1.0,
    label='Blend Ratio'
)
```

### Choices (Enum-like)

```python
registry.define(
    'my_lib.log_level',
    default='INFO',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    label='Log Level'
)

registry.define(
    'my_lib.algorithm',
    default='balanced',
    choices=['fast', 'balanced', 'accurate'],
    label='Algorithm',
    description='Trade-off between speed and accuracy'
)
```

### Custom Validators

```python
def validate_api_key(value: str) -> bool:
    """Validate API key format."""
    if not value:
        return True  # Empty is allowed
    return len(value) == 32 and value.isalnum()

registry.define(
    'my_lib.api_key',
    default='',
    label='API Key',
    description='32-character alphanumeric API key',
    validator=validate_api_key
)
```

```python
def validate_url(value: str) -> bool:
    """Validate URL format."""
    return value.startswith('http://') or value.startswith('https://')

registry.define(
    'my_lib.endpoint',
    default='https://api.example.com',
    label='API Endpoint',
    validator=validate_url
)
```

### Type Coercion

The registry automatically coerces TOML values:

```python
# Explicit type specification
registry.define(
    'my_lib.threshold',
    default=0.5,
    type_=float,  # Ensures TOML integers become floats
    label='Threshold'
)
```

---

## UI Metadata

### Widget Hints

The `ui_widget` parameter suggests which widget to use:

```python
# Color picker
registry.define(
    'my_lib.accent_color',
    default='#3498db',
    ui_widget='color',
    label='Accent Color'
)

# Slider
registry.define(
    'my_lib.volume',
    default=0.75,
    min_value=0.0,
    max_value=1.0,
    ui_widget='slider',
    label='Volume'
)

# Multi-line text
registry.define(
    'my_lib.template',
    default='Hello, {name}!',
    ui_widget='textarea',
    label='Message Template'
)

# Password/secret
registry.define(
    'my_lib.api_secret',
    default='',
    ui_widget='password',
    label='API Secret'
)

# File path
registry.define(
    'my_lib.output_path',
    default='./output',
    ui_widget='path',
    label='Output Directory'
)
```

### Ordering

Control display order within categories:

```python
registry.define('my_lib.first', ..., category='my_lib', ui_order=10)
registry.define('my_lib.second', ..., category='my_lib', ui_order=20)
registry.define('my_lib.third', ..., category='my_lib', ui_order=30)
```

Lower `ui_order` values appear first.

### Labels and Descriptions

```python
registry.define(
    'my_lib.complex_option',
    default=True,
    label='Enable Complex Processing',  # Short, shown as label
    description=(
        'When enabled, uses the advanced processing pipeline '
        'which provides better results but requires more memory. '
        'Recommended for systems with 16GB+ RAM.'
    ),  # Longer, shown as tooltip or help text
    category='my_lib.processing'
)
```

---

## Accessing Settings in Library Code

### In Regular Python Code

```python
# my_library/api.py
from haywire.core.di.config import get_settings_registry

def make_api_request(endpoint: str) -> dict:
    registry = get_settings_registry()
    
    base_url = registry.resolve('my_library.api_url')[0]
    timeout = registry.resolve('my_library.api_timeout')[0]
    
    import requests
    response = requests.get(
        f"{base_url}/{endpoint}",
        timeout=timeout
    )
    return response.json()
```

### In Node Code

```python
# my_library/nodes/api_node.py
from haywire.core.node import BaseNode, node

@node(label="API Fetch")
class ApiFetchNode(BaseNode):
    
    def worker(self, context, endpoint: str):
        # Access library settings directly
        base_url = self.settings['my_library.api_url']
        timeout = self.settings['my_library.api_timeout']
        
        # Or use dot notation
        if self.settings.my_library.cache_enabled:
            # Check cache first
            ...
```

### Helper Module Pattern

Create a helper for convenient access:

```python
# my_library/config.py
"""Configuration access helpers."""

from haywire.core.di.config import get_settings_registry


class Config:
    """Convenient access to my_library settings."""
    
    @staticmethod
    def _get(name: str):
        registry = get_settings_registry()
        return registry.resolve(f'my_library.{name}')[0]
    
    @property
    def api_url(self) -> str:
        return self._get('api_url')
    
    @property
    def api_timeout(self) -> int:
        return self._get('api_timeout')
    
    @property
    def cache_enabled(self) -> bool:
        return self._get('cache_enabled')
    
    @property
    def max_retries(self) -> int:
        return self._get('max_retries')


# Singleton instance
config = Config()


# Usage:
# from my_library.config import config
# url = config.api_url
```

---

## TOML Configuration

Users can configure your library via `~/.haywire/settings.toml`:

```toml
[my_library]
feature_x_enabled = true
feature_y_enabled = false

[my_library.connection]
api_url = "https://custom-api.example.com"
api_timeout = 60
max_retries = 5

[my_library.performance]
cache_enabled = true
cache_ttl_seconds = 7200
parallel_requests = 8
```

### Override Mode

Users can force settings globally:

```toml
[my_library.connection]
# Force all nodes to use this URL (cannot be overridden locally)
api_url = { override = true, value = "https://corporate-api.internal" }
```

---

## Complete Library Example

```python
# my_image_library/settings.py
"""
Settings for My Image Processing Library.

Provides image processing nodes with configurable defaults
for quality, performance, and output settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.settings import GlobalSettingsRegistry


NAMESPACE = 'image_lib'


def validate_quality(value: int) -> bool:
    """JPEG quality must be 1-100."""
    return 1 <= value <= 100


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register image library settings."""
    
    # =================================================================
    # Quality Settings
    # =================================================================
    
    registry.define(
        f'{NAMESPACE}.jpeg_quality',
        default=85,
        label='JPEG Quality',
        description='Default JPEG compression quality (1-100)',
        category=f'{NAMESPACE}.quality',
        min_value=1,
        max_value=100,
        ui_widget='slider',
        ui_order=10,
        validator=validate_quality
    )
    
    registry.define(
        f'{NAMESPACE}.png_compression',
        default=6,
        label='PNG Compression',
        description='PNG compression level (0-9, higher = smaller file)',
        category=f'{NAMESPACE}.quality',
        min_value=0,
        max_value=9,
        ui_order=20
    )
    
    registry.define(
        f'{NAMESPACE}.preserve_metadata',
        default=True,
        label='Preserve Metadata',
        description='Keep EXIF and other metadata in processed images',
        category=f'{NAMESPACE}.quality',
        ui_order=30
    )
    
    # =================================================================
    # Processing Settings
    # =================================================================
    
    registry.define(
        f'{NAMESPACE}.color_space',
        default='sRGB',
        label='Color Space',
        description='Default color space for processing',
        category=f'{NAMESPACE}.processing',
        choices=['sRGB', 'Adobe RGB', 'ProPhoto RGB', 'Linear'],
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.bit_depth',
        default=8,
        label='Bit Depth',
        description='Processing bit depth',
        category=f'{NAMESPACE}.processing',
        choices=[8, 16, 32],
        ui_order=20
    )
    
    registry.define(
        f'{NAMESPACE}.gpu_acceleration',
        default=True,
        label='GPU Acceleration',
        description='Use GPU for processing when available',
        category=f'{NAMESPACE}.processing',
        ui_order=30
    )
    
    # =================================================================
    # Resize Settings
    # =================================================================
    
    registry.define(
        f'{NAMESPACE}.resize_algorithm',
        default='lanczos',
        label='Resize Algorithm',
        description='Interpolation algorithm for resizing',
        category=f'{NAMESPACE}.resize',
        choices=['nearest', 'bilinear', 'bicubic', 'lanczos'],
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.max_dimension',
        default=4096,
        label='Max Dimension',
        description='Maximum width/height for output images',
        category=f'{NAMESPACE}.resize',
        min_value=100,
        max_value=16384,
        ui_order=20
    )
    
    # =================================================================
    # Output Settings
    # =================================================================
    
    registry.define(
        f'{NAMESPACE}.output_format',
        default='same',
        label='Default Output Format',
        description='Default format for saved images',
        category=f'{NAMESPACE}.output',
        choices=['same', 'jpeg', 'png', 'webp', 'tiff'],
        ui_order=10
    )
    
    registry.define(
        f'{NAMESPACE}.output_path',
        default='./processed',
        label='Output Directory',
        description='Default directory for saved images',
        category=f'{NAMESPACE}.output',
        ui_widget='path',
        ui_order=20
    )
    
    registry.define(
        f'{NAMESPACE}.filename_template',
        default='{name}_processed.{ext}',
        label='Filename Template',
        description='Template for output filenames. Variables: {name}, {ext}, {date}',
        category=f'{NAMESPACE}.output',
        ui_order=30
    )
```

---

## Next Steps

- **[UI Integration Guide](04-ui-integration.md)** — Building settings panels with NiceGUI
- **[API Reference](05-reference.md)** — Complete API documentation
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
