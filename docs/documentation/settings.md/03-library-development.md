# Library Development Guide

This guide covers how to define `LibrarySettings` for your haybale library and how nodes can reference them via `shadow()`.

---

## Creating a `LibrarySettings` Class

Decorate a `LibrarySettings` subclass with `@library_settings`. This sets `_namespace` and `_field_key` on every descriptor immediately.

```python
# my_lib/settings.py
from haywire.core.settings import LibrarySettings, setting, Color
from haywire.core.settings.decorators import library_settings


@library_settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    api_url:          str   = setting('https://api.example.com', label='API URL', category='connection')
    api_timeout:      int   = setting(30, min=5, max=300,        label='Timeout (s)', category='connection')
    cache_enabled:    bool  = setting(True,                      label='Enable Cache', category='performance')
    parallel_requests: int  = setting(4, min=1, max=20,          label='Parallel Requests', category='performance')
    accent_color:     Color = setting('#3498db',                  label='Accent Color', category='appearance')
```

Full keys are derived immediately: `my_lib.api_url`, `my_lib.api_timeout`, etc.

---

## Registering with the Global System

The registry picks up classes with `_auto_register = True` (set by `@library_settings`) during library initialization. Alternatively, register explicitly:

```python
# my_lib/__init__.py
from haywire.core.node import BaseLibrary, library

@library(label='My Library', registry_id='my_lib')
class MyLibrary(BaseLibrary):

    def register_components(self, registries):
        from haywire.core.settings import GlobalSettingsRegistry
        from .settings import MyLibSettings

        settings_registry: GlobalSettingsRegistry = registries.get(GlobalSettingsRegistry)
        if settings_registry:
            settings_registry.register_schema(MyLibSettings)

        # ... register nodes, etc.
```

---

## Referencing Library Settings from Nodes

Once `MyLibSettings._field_key` is set (by the time node classes are defined), use `shadow()` and `watch()`:

```python
# my_lib/nodes/fetch_node.py
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch
from ..settings import MyLibSettings


@node(label='API Fetch')
class ApiFetchNode(BaseNode):

    class node(NodeSettings):
        # Shadow: user can override per-node; shows reset button in panel
        api_url:    str  = shadow(MyLibSettings.api_url)
        api_timeout: int = shadow(MyLibSettings.api_timeout)

        # Watch: read-only; invisible in panel; cache invalidated on global change
        cache_enabled: bool = watch(MyLibSettings.cache_enabled)

        # Local node-only setting
        endpoint: str = setting('', label='Endpoint')

    def worker(self, context, payload: dict):
        url = f"{self.settings.api_url}/{self.settings.endpoint}"
        # self.settings.api_timeout — uses local override or global default
        # self.settings.cache_enabled — read-only global cache
        ...
```

**Important:** Node classes using `shadow(MyLibSettings.field)` must be defined *after* `MyLibSettings` is decorated. The `@library_settings` decorator sets `_field_key` at class evaluation time.

---

## TOML Configuration

Users configure library settings in `~/.haywire/settings.toml` (global tier, hand-edited) or
`<workspace>/.haywire/settings.toml` (workspace tier, written by the UI):

```toml
[my_lib]
api_url     = "https://custom-api.example.com"
api_timeout = 60
cache_enabled = true

[my_lib]
# Force on all nodes — cannot be per-node overridden
api_url = { override = true, value = "https://corporate-api.internal" }
```

The workspace tier is layered on top of the global tier. `save_to_toml()` always writes to the
workspace tier — the global tier is never overwritten by the application.

---

## Accessing Library Settings from Non-Node Code

```python
from haywire.core.di.config import get_settings_registry

def make_request(endpoint: str) -> dict:
    registry = get_settings_registry()
    base_url, _ = registry.resolve('my_lib.api_url')
    timeout, _  = registry.resolve('my_lib.api_timeout')
    ...
```

---

## Complete Example

```python
# haybale_image/settings.py
from haywire.core.settings import LibrarySettings, setting, Color
from haywire.core.settings.decorators import library_settings


@library_settings(namespace='image_lib', label='Image Processing')
class ImageLibSettings(LibrarySettings):

    # Quality
    jpeg_quality:     int   = setting(85, min=1, max=100,  label='JPEG Quality',     category='quality', order=10)
    png_compression:  int   = setting(6,  min=0, max=9,    label='PNG Compression',  category='quality', order=20)
    preserve_metadata: bool = setting(True,                label='Preserve Metadata', category='quality', order=30)

    # Processing
    color_space:      str   = setting('sRGB', choices=['sRGB', 'Adobe RGB', 'Linear'],
                                      label='Color Space', category='processing', order=10)
    gpu_acceleration: bool  = setting(True,                label='GPU Acceleration', category='processing', order=20)

    # Resize
    resize_algorithm: str   = setting('lanczos', choices=['nearest', 'bilinear', 'bicubic', 'lanczos'],
                                      label='Resize Algorithm', category='resize', order=10)
```

```python
# haybale_image/nodes/resize_node.py
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow
from ..settings import ImageLibSettings


@node(label='Resize Image')
class ResizeNode(BaseNode):

    class node(NodeSettings):
        algorithm:   str = shadow(ImageLibSettings.resize_algorithm)
        width:       int = setting(512, min=1, max=8192, label='Width')
        height:      int = setting(512, min=1, max=8192, label='Height')

    def worker(self, context, image):
        alg = self.settings.algorithm   # per-node override or global default
        w   = self.settings.width
        h   = self.settings.height
        ...
```

---

## Next Steps

- **[UI Integration Guide](04-ui-integration.md)** — Building settings panels
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
