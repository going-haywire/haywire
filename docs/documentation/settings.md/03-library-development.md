# Library Development Guide

This guide covers how to define `LibrarySettings` for your haybale library and how nodes can reference them via `shadow()` and `watch()`.

---

## Creating a `LibrarySettings` Class

Decorate a `LibrarySettings` subclass with `@settings`. This sets `class_identity` (required by `BaseRegistry` for hot-reload discovery), `class_library`, `_namespace`, and `_field_key` on every descriptor.

```python
# my_lib/settings.py
from haywire.core.settings import LibrarySettings, field, shadow, watch, Color
from haywire.core.settings.decorator import settings


@settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    api_url = field[str]('https://api.example.com', label='API URL',          category='connection')
    api_timeout = field[int](30, min=5, max=300,        label='Timeout (s)',       category='connection')
    cache_enabled = field[bool](True,                      label='Enable Cache',      category='performance')
    parallel_requests = field[int](4, min=1, max=20,          label='Parallel Requests', category='performance')
    accent_color = field[Color]('#3498db',                  label='Accent Color',      category='appearance')
```

Full keys are derived immediately: `my_lib.api_url`, `my_lib.api_timeout`, etc.

`@settings` is required for any class registered via the `BaseRegistry` hot-reload machinery — without it `class_identity` is absent and the registry's `_class_filter` will not pick up the class.

---

## Registration

`LibrarySettings` classes are registered via the `BaseRegistry` hot-reload machinery when the library module is loaded. No explicit registration call is needed in typical usage.

For explicit registration (e.g. in a `register_components()` override):

```python
# my_lib/__init__.py
from haywire.core.node import BaseLibrary, library

@library(label='My Library')
class MyLibrary(BaseLibrary):

    def register_components(self, registries):
        from haywire.core.settings import SettingsRegistry
        from .settings import MyLibSettings

        settings_registry: SettingsRegistry = registries.get(SettingsRegistry)
        if settings_registry:
            settings_registry.register_schema(MyLibSettings)

        # ... register nodes, etc.
```

---

## Referencing Library Settings from Nodes

Once `MyLibSettings._field_key` is set (at class definition time via `namespace=`), use `shadow()` (writable mirror) or `watch()` (read-only mirror):

```python
# my_lib/nodes/fetch_node.py
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, field, shadow, watch
from ..settings import MyLibSettings


@node(label='API Fetch')
class ApiFetchNode(BaseNode):

    class api(NodeSettings):
        # shadow(): writable mirror — user can override per-node; shows reset button in panel
        api_url = shadow(MyLibSettings.api_url)
        api_timeout = shadow(MyLibSettings.api_timeout)

        # watch(): read-only mirror — invisible in panel; cache invalidated on global change
        cache_enabled = watch(MyLibSettings.cache_enabled)

        # Local node-only setting
        endpoint = field[str]('', label='Endpoint')

    def worker(self, context, payload: dict):
        url = f"{self.api.api_url}/{self.api.endpoint}"
        # self.api.api_timeout — uses local override or global default
        # self.api.cache_enabled — read-only global cache
        ...
```

**Important:** Node classes using `shadow(MyLibSettings.field)` or `watch(MyLibSettings.field)` must be defined *after* `MyLibSettings` is defined. The `namespace=` kwarg sets `_field_key` at class evaluation time.

---

## Reactive Access from Non-Node Code

Any class that wants live reactive access to library settings instantiates the class directly. After the library is loaded and `cls._registry` is set, the instance is fully wired with no explicit injection:

```python
from my_lib.settings import MyLibSettings

class MyRenderer:
    def __init__(self):
        self.settings = MyLibSettings()   # auto-wired after registry init
        self.settings.subscribe(self._on_change)

    def render(self):
        url = self.settings.api_url       # resolves through registry

    def _on_change(self, name, value, old):
        if name == 'api_url':
            self._reconnect()
```

For one-off reads without reactivity, use the registry directly:

```python
from haywire.core.di.config import get_settings_registry

def make_request(endpoint: str) -> dict:
    registry = get_settings_registry()
    base_url, _ = registry.resolve('my_lib.api_url')
    timeout, _  = registry.resolve('my_lib.api_timeout')
    ...
```

---

## TOML Configuration

Users configure library settings in `~/.haywire/settings.toml` (global tier, hand-edited) or
`<workspace>/.haywire/settings.toml` (workspace tier, written by the UI):

```toml
[my_lib]
api_url     = "https://custom-api.example.com"
api_timeout = 60
cache_enabled = true

# Force on all nodes — cannot be per-node overridden
api_url = { override = true, value = "https://corporate-api.internal" }
```

The workspace tier is layered on top of the global tier. `save_to_toml()` always writes to the workspace tier — the global tier is never overwritten by the application.

---

## Complete Example

```python
# haybale_image/settings.py
from haywire.core.settings import LibrarySettings, field, shadow, watch, Color
from haywire.core.settings.decorator import settings


@settings(namespace='image_lib', label='Image Processing')
class ImageLibSettings(LibrarySettings):

    # Quality
    jpeg_quality = field[int](85, min=1, max=100, label='JPEG Quality',    category='quality', order=10)
    png_compression = field[int](6,  min=0, max=9,   label='PNG Compression', category='quality', order=20)
    preserve_metadata = field[bool](True,               label='Preserve Metadata', category='quality', order=30)

    # Processing
    color_space = field[str]('sRGB', choices=['sRGB', 'Adobe RGB', 'Linear'],
                                     label='Color Space', category='processing', order=10)
    gpu_acceleration = field[bool](True, label='GPU Acceleration', category='processing', order=20)

    # Resize
    resize_algorithm = field[str]('lanczos', choices=['nearest', 'bilinear', 'bicubic', 'lanczos'],
                                     label='Resize Algorithm', category='resize', order=10)
```

```python
# haybale_image/nodes/resize_node.py
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, field, shadow, watch
from ..settings import ImageLibSettings


@node(label='Resize Image')
class ResizeNode(BaseNode):

    class resize(NodeSettings):
        algorithm = shadow(ImageLibSettings.resize_algorithm)
        width = field[int](512, min=1, max=8192, label='Width')
        height = field[int](512, min=1, max=8192, label='Height')

    def worker(self, context, image):
        alg = self.resize.algorithm   # per-node override or global default
        w   = self.resize.width
        h   = self.resize.height
        ...
```

---

## Next Steps

- **[UI Integration Guide](04-ui-integration.md)** — Building settings panels
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
