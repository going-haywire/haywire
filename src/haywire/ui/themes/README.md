# Haywire Theme System

The Haywire theme system provides a flexible, type-safe way to manage colors throughout the application. It supports both built-in Python themes and user-defined TOML themes with inheritance.

## Table of Contents

- [Quick Start](#quick-start)
- [Using Themes](#using-themes)
- [Creating New Themes](#creating-new-themes)
- [Extending the Palette](#extending-the-palette)
- [Theme Inheritance](#theme-inheritance)
- [API Reference](#api-reference)

---

## Quick Start

### Using Theme Colors in Your Code

```python
from haywire.ui.themes import ThemePalette, Theme_UI_Color
from haywire.core.data.enums import FlowType

# UI colors with autocomplete
background = ThemePalette.ui(Theme_UI_Color.NODE_BACKGROUND)
primary = ThemePalette.ui(Theme_UI_Color.PRIMARY)

# Flow type colors
ctrl_color = ThemePalette.flow_type(FlowType.CTRL)
data_color = ThemePalette.flow_type(FlowType.DATA)

# Data type colors
float_color = ThemePalette.data_type('float')
string_color = ThemePalette.data_type('string')

# Canvas colors (also part of Theme_UI_Color)
canvas_bg = ThemePalette.ui(Theme_UI_Color.CANVAS_BACKGROUND)
grid_line = ThemePalette.ui(Theme_UI_Color.CANVAS_GRID_LINE)
```

### Switching Themes

```python
# List available themes
themes = ThemePalette.list_themes()  # ['default', 'dark', 'ocean', ...]

# Switch theme
ThemePalette.set_theme('dark')

# Get current theme info
theme_name = ThemePalette.get_theme_name()
theme_key = ThemePalette.get_theme_key()
```

---

## Using Themes

### Available Theme Categories

The theme system organizes colors into three categories:

1. **UI Colors** (`Theme_UI_Color` enum) - Interface elements and canvas
2. **Flow Type Colors** (`FlowType` enum) - Connection types (control, data, callback)
3. **Data Type Colors** (strings) - Port colors based on data types

### IDE Autocomplete Support

The system uses enums to provide IDE autocomplete:

```python
from haywire.ui.themes.colors import Theme_UI_Color

# When you type Theme_UI_Color. you'll see all available options:
Theme_UI_Color.PRIMARY
Theme_UI_Color.SECONDARY
Theme_UI_Color.NODE_BACKGROUND
Theme_UI_Color.TEXT_PRIMARY
Theme_UI_Color.CANVAS_BACKGROUND
# ... etc
```

### Observer Pattern for Theme Changes

Register callbacks to be notified when themes change:

```python
def on_theme_changed(theme_name: str, theme: BaseTheme):
    print(f"Theme changed to: {theme_name}")
    # Update your UI here

ThemePalette.register_observer(on_theme_changed)
```

---

## Creating New Themes

### Option 1: Python Theme (Built-in)

Create a new Python theme in `src/haywire/ui/themes/builtin.py`:

```python
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.core.data.enums import DataType, FlowType

class MyCustomTheme(PythonTheme):
    """My custom theme description."""
    
    metadata = ThemeMetadata(
        name="My Custom Theme",
        author="Your Name",
        description="A beautiful custom color scheme"
    )
    
    # Data type colors - using DataType enum keys
    DATA_TYPES = {
        DataType.FLOAT.value: "#00bcd4",
        DataType.INT.value: "#03a9f4",
        DataType.STRING.value: "#4dd0e1",
        DataType.BOOL.value: "#26c6da",
        DataType.LIST.value: "#00acc1",
        DataType.DICT.value: "#0097a7",
        DataType.OBJECT.value: "#006064",
        'any': "#b0bec5",
    }
    
    # Flow type colors - using FlowType enum keys
    FLOW_TYPES = {
        FlowType.CTRL.value: "#f44336",
        FlowType.CALLBACK.value: "#ff5722",
        FlowType.DATA.value: "#4caf50",
    }
    
    # UI colors - using Theme_UI_Color enum keys
    UI_COLORS = {
        # Semantic colors
        Theme_UI_Color.PRIMARY.value: "#0288d1",
        Theme_UI_Color.SECONDARY.value: "#0097a7",
        Theme_UI_Color.ACCENT.value: "#00acc1",
        
        # Status colors
        Theme_UI_Color.ERROR.value: "#f44336",
        Theme_UI_Color.WARNING.value: "#ff9800",
        Theme_UI_Color.SUCCESS.value: "#4caf50",
        Theme_UI_Color.INFO.value: "#2196f3",
        
        # Node/port specific
        Theme_UI_Color.NODE_BACKGROUND.value: "rgba(30, 30, 30, 0.9)",
        Theme_UI_Color.NODE_BORDER.value: "#424242",
        Theme_UI_Color.NODE_SELECTED_BORDER.value: "#0288d1",
        Theme_UI_Color.PORT_BORDER.value: "#616161",
        Theme_UI_Color.PORT_DEFAULT.value: "#9e9e9e",
        
        # Canvas colors
        Theme_UI_Color.CANVAS_BACKGROUND.value: "#1a1a1a",
        Theme_UI_Color.CANVAS_GRID_LINE.value: "#2d2d2d",
        Theme_UI_Color.CANVAS_GRID_DOT.value: "#404040",
        Theme_UI_Color.SELECTION_BOX.value: "rgba(2, 136, 209, 0.3)",
        Theme_UI_Color.SELECTION_BOX_BORDER.value: "#0288d1",
        
        # Text colors
        Theme_UI_Color.TEXT_PRIMARY.value: "#ffffff",
        Theme_UI_Color.TEXT_SECONDARY.value: "#b0b0b0",
        Theme_UI_Color.TEXT_DISABLED.value: "#616161",
        Theme_UI_Color.TEXT_HINT.value: "#757575",
    }
```

Then register it in the `BUILTIN_THEMES` dictionary:

```python
BUILTIN_THEMES: Dict[str, type[PythonTheme]] = {
    'default': DefaultTheme,
    'dark': DarkTheme,
    'mycustom': MyCustomTheme,  # Add your theme here
}
```

### Option 2: TOML Theme (User-defined)

Create a TOML file in `src/haywire/ui/themes/data/mytheme.toml`:

```toml
[metadata]
name = "My Theme"
author = "Your Name"
description = "A custom theme"
version = "1.0.0"
extends = "default"  # Optional: inherit from another theme

[data_types]
float = "#00bcd4"
int = "#03a9f4"
str = "#4dd0e1"
bool = "#26c6da"
list = "#00acc1"
dict = "#0097a7"
object = "#006064"
any = "#b0bec5"

[flow_types]
control = "#f44336"
callback = "#ff5722"
data = "#4caf50"

[ui]
# Semantic colors
primary = "#0288d1"
secondary = "#0097a7"
accent = "#00acc1"

# Status colors
error = "#f44336"
warning = "#ff9800"
success = "#4caf50"
info = "#2196f3"

# Node/port specific
node_background = "rgba(30, 30, 30, 0.9)"
node_border = "#424242"
node_selected_border = "#0288d1"
port_border = "#616161"
port_default = "#9e9e9e"

# Canvas colors
canvas_background = "#1a1a1a"
canvas_grid_line = "#2d2d2d"
canvas_grid_dot = "#404040"
selection_box = "rgba(2, 136, 209, 0.3)"
selection_box_border = "#0288d1"

# Text colors
text_primary = "#ffffff"
text_secondary = "#b0b0b0"
text_disabled = "#616161"
text_hint = "#757575"
```

---

## Extending the Palette

To add new color values to the theme system, you need to update several files:

### Step 1: Add Enum Value to `colors.py`

Add your new color key to the `Theme_UI_Color` enum:

```python
# src/haywire/ui/themes/colors.py

class Theme_UI_Color(str, Enum):
    """UI theme color keys with IDE autocomplete support."""
    
    # ... existing colors ...
    
    # Your new color
    MY_NEW_COLOR = 'my_new_color'
```

### Step 2: Add Default Values to Built-in Themes

Update `DefaultTheme` in `builtin.py`:

```python
# src/haywire/ui/themes/builtin.py

class DefaultTheme(PythonTheme):
    # ...
    
    UI_COLORS = {
        # ... existing colors ...
        
        # Your new color with default value
        Theme_UI_Color.MY_NEW_COLOR.value: "#ff00ff",
    }
```

### Step 3: Use Your New Color

Now you can use it in your code with full autocomplete:

```python
from haywire.ui.themes import ThemePalette, Theme_UI_Color

my_color = ThemePalette.ui(Theme_UI_Color.MY_NEW_COLOR)
```

### Adding New Data Type Colors

If you add a new `DataType` enum value in `core/data/enums.py`:

```python
# src/haywire/core/data/enums.py

class DataType(Enum):
    # ... existing types ...
    TENSOR = 'tensor'  # New type
```

Then add its default color to themes:

```python
# src/haywire/ui/themes/builtin.py

class DefaultTheme(PythonTheme):
    DATA_TYPES = {
        # ... existing types ...
        DataType.TENSOR.value: "#9c27b0",  # New color
    }
```

### Adding New Flow Type Colors

Flow types are defined in `core/data/enums.py`. If you add a new one, update themes:

```python
# In builtin.py
FLOW_TYPES = {
    # ... existing types ...
    FlowType.NEW_TYPE.value: "#00ff00",
}
```

---

## Theme Inheritance

Themes can inherit from other themes to avoid duplication.

### Python Theme Inheritance

```python
class MyDarkTheme(DefaultTheme):
    """Extends DefaultTheme, only overriding specific colors."""
    
    metadata = ThemeMetadata(
        name="My Dark Theme",
        author="Your Name",
        description="Dark variant"
    )
    
    # Only override what you want to change
    UI_COLORS = {
        **DefaultTheme.UI_COLORS,  # Inherit all parent colors
        # Override specific colors
        Theme_UI_Color.PRIMARY.value: "#42a5f5",
        Theme_UI_Color.NODE_BACKGROUND.value: "rgba(20, 20, 20, 0.95)",
    }
```

### TOML Theme Inheritance

```toml
[metadata]
name = "My Ocean Theme"
extends = "default"  # Inherit from default theme

# Only define what you want to override
[ui]
primary = "#0288d1"
accent = "#00acc1"

# Everything else is inherited from parent theme
```

### Inheritance Resolution

1. Check local theme's color dictionaries
2. If not found, check parent theme
3. If still not found, use default fallback

```python
# Example inheritance chain:
# ocean.toml → extends → DefaultTheme → falls back to hardcoded defaults

# When you request a color:
ThemePalette.ui('primary')
# 1. Check ocean.toml's [ui] section
# 2. If not found, check DefaultTheme.UI_COLORS
# 3. If not found, use default '#757575'
```

---

## API Reference

### ThemePalette Class Methods

#### `set_theme(theme_name: str) -> bool`
Set the active theme by name.

```python
ThemePalette.set_theme('dark')
```

#### `get_theme_name() -> str`
Get the display name of the current theme.

```python
name = ThemePalette.get_theme_name()  # "Dark"
```

#### `get_theme_key() -> str`
Get the key/filename of the current theme.

```python
key = ThemePalette.get_theme_key()  # "dark"
```

#### `list_themes() -> List[str]`
List all available themes (built-in + TOML).

```python
themes = ThemePalette.list_themes()  # ['default', 'dark', 'ocean']
```

#### `ui(element: Theme_UI_Color | str, default: Optional[str] = None) -> str`
Get UI element color from current theme.

```python
color = ThemePalette.ui(Theme_UI_Color.PRIMARY)
color = ThemePalette.ui('primary')  # Also works with strings
```

#### `flow_type(flow_type: FlowType | str, default: Optional[str] = None) -> str`
Get flow type color from current theme.

```python
color = ThemePalette.flow_type(FlowType.CTRL)
color = ThemePalette.flow_type('control')  # Also works with strings
```

#### `data_type(data_type: str, default: Optional[str] = None) -> str`
Get data type color from current theme.

```python
color = ThemePalette.data_type('float')
```

#### `canvas(element: Theme_UI_Color | str, default: Optional[str] = None) -> str`
Get canvas color (delegates to `ui()` since canvas colors are merged).

```python
color = ThemePalette.canvas(Theme_UI_Color.CANVAS_BACKGROUND)
```

#### `register_observer(observer: Callable[[str, BaseTheme], None]) -> None`
Register a callback for theme change notifications.

```python
def on_change(theme_name: str, theme: BaseTheme):
    print(f"Theme changed to {theme_name}")

ThemePalette.register_observer(on_change)
```

#### `reload_current_theme() -> bool`
Reload the current theme from disk (useful for TOML theme development).

```python
ThemePalette.reload_current_theme()
```

---

## File Structure

```
src/haywire/ui/themes/
├── README.md              # This file
├── __init__.py           # Public API exports
├── base.py               # BaseTheme, PythonTheme, TOMLTheme
├── builtin.py            # Built-in theme definitions
├── colors.py             # Theme_UI_Color enum and Colors class
├── loader.py             # TOML theme loader and validator
├── palette.py            # ThemePalette manager (main API)
├── utils.py              # Color utilities (validation, conversion)
└── data/                 # TOML theme files
    ├── default.toml
    ├── dark.toml
    └── ocean.toml
```

---

## Best Practices

### 1. Use Enums for Type Safety

```python
# ✅ Good - Type-safe with autocomplete
color = ThemePalette.ui(Theme_UI_Color.PRIMARY)

# ❌ Avoid - No autocomplete, typo-prone
color = ThemePalette.ui('primery')  # Typo!
```

### 2. Provide Fallback Defaults

```python
# Provide sensible fallback in case color is missing
color = ThemePalette.ui(Theme_UI_Color.NODE_BACKGROUND, 'rgba(255, 255, 255, 0.3)')
```

### 3. Use Inheritance to Reduce Duplication

```python
# ✅ Good - Only override what changes
class MyTheme(DefaultTheme):
    UI_COLORS = {
        **DefaultTheme.UI_COLORS,
        Theme_UI_Color.PRIMARY.value: "#custom",
    }

# ❌ Avoid - Duplicating everything
class MyTheme(PythonTheme):
    UI_COLORS = {
        # ... copying all 20+ colors ...
    }
```

### 4. Use Theme Keys for Enum-based Dictionaries

```python
# ✅ Good - Using enum values as keys
UI_COLORS = {
    Theme_UI_Color.PRIMARY.value: "#2196f3",
    Theme_UI_Color.SECONDARY.value: "#757575",
}

# ❌ Avoid - Plain strings (no refactoring safety)
UI_COLORS = {
    'primary': "#2196f3",
    'secondary': "#757575",
}
```

### 5. Register Observers for Dynamic UI Updates

```python
def _on_theme_changed(self, theme_name: str, theme):
    """Update UI when theme changes."""
    # Use deferred update to avoid UI deletion during callbacks
    ui.timer(0.1, self._update_ui_colors, once=True)

ThemePalette.register_observer(self._on_theme_changed)
```

---

## Troubleshooting

### Theme Not Found

```python
ThemePalette.set_theme('nonexistent')  # Returns False
```

Check available themes:
```python
print(ThemePalette.list_themes())
```

### Missing Color in Theme

If a color is missing, the system falls back to parent theme or default:

```toml
# mytheme.toml - only defines primary
[ui]
primary = "#00ff00"

# When you request secondary:
ThemePalette.ui('secondary')
# → Checks mytheme.toml [ui] → Not found
# → Checks parent theme (if extends is set) → Found
# → Returns parent's secondary color
```

### TOML Syntax Error

```python
ThemePalette.set_theme('broken_theme')
# Raises: ThemeValidationError with details
```

Validate your TOML file syntax at: https://www.toml-lint.com/
