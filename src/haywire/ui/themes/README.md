# Haywire Theme System - User Guide

## Table of Contents

- [Haywire Theme System - User Guide](#haywire-theme-system---user-guide)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Quick Start](#quick-start)
    - [Using Theme Colors in Your Code](#using-theme-colors-in-your-code)
    - [Switching Themes](#switching-themes)
  - [Using ThemePalette in Code](#using-themepalette-in-code)
    - [Basic Usage](#basic-usage)
    - [Priority Logic](#priority-logic)
    - [Real-World Example](#real-world-example)
  - [Understanding Key Structure](#understanding-key-structure)
    - [How It Works](#how-it-works)
    - [The Dot is Just a Convention](#the-dot-is-just-a-convention)
    - [Complete Flow Example](#complete-flow-example)
    - [Why This Design?](#why-this-design)
    - [Custom Sections](#custom-sections)
  - [Available Theme Keys](#available-theme-keys)
    - [UI Keys](#ui-keys)
    - [Data Type Keys](#data-type-keys)
    - [Flow Type Keys](#flow-type-keys)
  - [Adding More Keys](#adding-more-keys)
    - [In Code (Add to ThemeKey Enum)](#in-code-add-to-themekey-enum)
    - [Using Custom Keys Without Enum](#using-custom-keys-without-enum)
  - [Theme Metadata Settings](#theme-metadata-settings)
    - [Priority Field](#priority-field)
  - [Theme Inheritance](#theme-inheritance)
    - [In Python Themes](#in-python-themes)
    - [In TOML Themes](#in-toml-themes)
    - [Inheritance Rules](#inheritance-rules)
  - [Creating Your Own TOML Theme](#creating-your-own-toml-theme)
    - [Step 1: Create Theme File](#step-1-create-theme-file)
    - [Step 2: Use Your Theme](#step-2-use-your-theme)
    - [Step 3: Hot Reload During Development](#step-3-hot-reload-during-development)
  - [Creating Python Themes](#creating-python-themes)
  - [TOML Theme Structure Reference](#toml-theme-structure-reference)
    - [Complete Example](#complete-example)
    - [Color Format Rules](#color-format-rules)
    - [Section Naming](#section-naming)
  - [Theme Management](#theme-management)
    - [Switching Themes](#switching-themes-1)
    - [Reloading Themes](#reloading-themes)
  - [Observer Pattern for Theme Changes](#observer-pattern-for-theme-changes)
    - [Best Practice for UI Updates](#best-practice-for-ui-updates)
  - [Extending the Palette](#extending-the-palette)
    - [Step 1: Add Enum Value](#step-1-add-enum-value)
    - [Step 2: Add Default Values to Built-in Themes](#step-2-add-default-values-to-built-in-themes)
    - [Step 3: Use Your New Color](#step-3-use-your-new-color)
    - [Adding New Data Type Colors](#adding-new-data-type-colors)
    - [Adding New Flow Type Colors](#adding-new-flow-type-colors)
  - [Best Practices](#best-practices)
  - [Troubleshooting](#troubleshooting)
    - [Theme not found](#theme-not-found)
    - [Colors not applying](#colors-not-applying)
    - [Values not updating](#values-not-updating)
    - [TOML Syntax Error](#toml-syntax-error)
    - [Missing Color in Theme](#missing-color-in-theme)
  - [File Structure](#file-structure)
  - [API Reference Summary](#api-reference-summary)
    - [ThemePalette Methods](#themepalette-methods)
    - [Example Usage](#example-usage)

---

## Overview

The Haywire Theme System provides a simple, flexible way to customize colors and visual elements that are defined with strings in your application. It supports both built-in Python themes and user-defined TOML themes with inheritance and priority-based preference handling.

**Key Features:**
- Unified `get()` method for retrieving theme values
- Smart priority logic for preference handling
- Theme inheritance to avoid duplication
- Hot-reload support for development
- Observer pattern for UI updates
- IDE autocomplete support with enums
- Both Python and TOML theme formats

---

## Quick Start

### Using Theme Colors in Your Code

```python
from haywire.ui.themes import ThemePalette, ThemeKey
from haywire.core.data.enums import FlowType

# Simple get with ThemeKey enum
color = ThemePalette.get(ThemeKey.UI_PRIMARY)

# With user preference override
color = ThemePalette.get(ThemeKey.UI_PRIMARY, preference="#ff0000")

# With fallback value
color = ThemePalette.get(ThemeKey.UI_PRIMARY, fallback="#0000ff")

# Using string keys directly (ThemeKey is optional)
color = ThemePalette.get('ui.primary')
color = ThemePalette.get('data.float', preference='#50b0ff')
color = ThemePalette.get('flow.control', fallback='#0000ff')
```

### Switching Themes

```python
# List available themes
themes = ThemePalette.list_themes()  # ['default', 'dark', 'my_theme', ...]

# Switch theme
ThemePalette.set_theme('dark')

# Get current theme info
theme_name = ThemePalette.get_theme_name()
```

---

## Using ThemePalette in Code

The `ThemePalette` class provides a unified `get()` method for retrieving any theme value.

### Basic Usage

```python
from haywire.ui.themes import ThemePalette, ThemeKey

# Get theme value (returns theme's value or empty string if not found)
color = ThemePalette.get(ThemeKey.UI_PRIMARY)

# With a preference (user-specified value that overrides theme by default)
color = ThemePalette.get(ThemeKey.UI_PRIMARY, preference="#ff0000")

# With fallback (used if theme doesn't have the key)
color = ThemePalette.get(ThemeKey.UI_PRIMARY, fallback="#0000ff")

# Using string keys directly (ThemeKey is optional for convenience)
color = ThemePalette.get('ui.primary')
color = ThemePalette.get('data.float', preference='#50b0ff')
color = ThemePalette.get('flow.control', fallback='#0000ff')
```

### Priority Logic

The `get()` method uses smart priority logic:

**When preference is None:**
- Returns the theme value if found
- Otherwise returns fallback (or empty string if no fallback)

**When preference is provided:**
- **Default behavior (Priority='Preference')**: Returns the preference, ignoring the theme
- **Theme priority (Priority='Theme')**: Returns theme value if set, otherwise returns preference

This allows users to:
- Override theme colors with their own preferences by default
- Create "strict" themes that enforce their values even when preferences are provided

### Real-World Example

```python
from haywire.ui.themes import ThemePalette, ThemeKey
from haywire.core.data.enums import FlowType

# In a node renderer
def render_control_pin(self, pin):
    # Get control flow color, use pin.color as preference
    ctrl_color = ThemePalette.get(
        ThemeKey.FLOW_CONTROL,
        preference=pin.color,
        fallback='#0000ff'
    )
    
    ui.icon('join_left', color=ctrl_color)

# In a data port renderer
def render_data_port(self, port):
    # Build key from data type
    data_type_key = f'data.{port.data_type}'
    
    port_color = ThemePalette.get(
        data_type_key,
        preference=port.color,
        fallback=ThemePalette.get(ThemeKey.UI_PORT_DEFAULT)
    )
    
    ui.element('div').style(f'background-color: {port_color}')
```

---

## Understanding Key Structure

The theme system uses a simple **string concatenation** approach to convert TOML sections into theme keys.

### How It Works

When you define a theme in TOML:

```toml
[data]
float = "#50b0ff"
int = "#f7b0ff"

[ui]
primary = "#2196f3"
```

The system processes it by:

1. **Taking the section name** (e.g., `data`, `ui`)
2. **Taking each key** in that section (e.g., `float`, `primary`)
3. **Concatenating with a dot**: `"data" + "." + "float"` → `"data.float"`
4. **Storing in a flat dictionary**: `_values['data.float'] = "#50b0ff"`

### The Dot is Just a Convention

The dot (`.`) has **no special meaning** to the theme system:

- `'data.float'` is simply a string (like `'data_float'` or `'data-float'` would be)
- There is no hierarchy or nested structure
- All lookups are plain string matching (case-insensitive)
- The dot is a **naming convention** to organize keys into categories

### Complete Flow Example

```toml
# In your TOML file
[data]
float = "#00bcd4"
int = "#9b59b6"

[my_plugin]
special_color = "#ff0000"
```

**Becomes in memory:**
```python
_values = {
    'data.float': '#00bcd4',
    'data.int': '#9b59b6',
    'my_plugin.special_color': '#ff0000'
}
```

**Access in code:**
```python
# These all work the same way - just string matching
color1 = ThemePalette.get('data.float')           # '#00bcd4'
color2 = ThemePalette.get('data.int')             # '#9b59b6'
color3 = ThemePalette.get('my_plugin.special_color')  # '#ff0000'

# You can also build keys dynamically
data_type = 'float'
color = ThemePalette.get(f'data.{data_type}')  # Creates 'data.float'
```

### Why This Design?

1. **Simple TOML organization**: Sections (`[data]`, `[ui]`) group related values visually
2. **Flat storage**: No complex nested dictionaries to manage
3. **Flexible naming**: Use any section name for custom categories
4. **Easy lookups**: Just string matching, no hierarchy traversal

### Custom Sections

You can create any section name you want - the system treats them all the same:

```toml
[my_game]
player_color = "#00ff00"
enemy_color = "#ff0000"

[experimental]
feature_x = "#123456"
```

Then access with:
```python
player = ThemePalette.get('my_game.player_color')
feature = ThemePalette.get('experimental.feature_x')
```

The section name just becomes part of the string key.

---

## Available Theme Keys

Theme keys are organized by category for clarity. You can use either the `ThemeKey` enum constants or string keys directly.

### UI Keys

- `ThemeKey.UI_PRIMARY` → 'ui.primary'
- `ThemeKey.UI_SECONDARY` → 'ui.secondary'
- `ThemeKey.UI_ACCENT` → 'ui.accent'
- `ThemeKey.UI_ERROR` → 'ui.error'
- `ThemeKey.UI_WARNING` → 'ui.warning'
- `ThemeKey.UI_SUCCESS` → 'ui.success'
- `ThemeKey.UI_INFO` → 'ui.info'
- `ThemeKey.UI_NODE_BACKGROUND` → 'ui.node_background'
- `ThemeKey.UI_NODE_BORDER` → 'ui.node_border'
- `ThemeKey.UI_NODE_SELECTED_BORDER` → 'ui.node_selected_border'
- `ThemeKey.UI_PORT_BORDER` → 'ui.port_border'
- `ThemeKey.UI_PORT_DEFAULT` → 'ui.port_default'
- `ThemeKey.UI_CANVAS_BACKGROUND` → 'ui.canvas_background'
- `ThemeKey.UI_CANVAS_GRID_LINE` → 'ui.canvas_grid_line'
- `ThemeKey.UI_CANVAS_GRID_DOT` → 'ui.canvas_grid_dot'
- `ThemeKey.UI_SELECTION_BOX` → 'ui.selection_box'
- `ThemeKey.UI_SELECTION_BOX_BORDER` → 'ui.selection_box_border'
- `ThemeKey.UI_TEXT_PRIMARY` → 'ui.text_primary'
- `ThemeKey.UI_TEXT_SECONDARY` → 'ui.text_secondary'
- `ThemeKey.UI_TEXT_DISABLED` → 'ui.text_disabled'
- `ThemeKey.UI_TEXT_HINT` → 'ui.text_hint'

### Data Type Keys

- `ThemeKey.DATA_FLOAT` → 'data.float'
- `ThemeKey.DATA_INT` → 'data.int'
- `ThemeKey.DATA_STR` → 'data.str'
- `ThemeKey.DATA_BOOL` → 'data.bool'
- `ThemeKey.DATA_LIST` → 'data.list'
- `ThemeKey.DATA_DICT` → 'data.dict'
- `ThemeKey.DATA_BYTES` → 'data.bytes'
- `ThemeKey.DATA_ANY` → 'data.any'

### Flow Type Keys

- `ThemeKey.FLOW_CONTROL` → 'flow.control'
- `ThemeKey.FLOW_CALLBACK` → 'flow.callback'
- `ThemeKey.FLOW_DATA` → 'flow.data'

---

## Adding More Keys

### In Code (Add to ThemeKey Enum)

Edit `src/haywire/ui/themes/keys.py`:

```python
class ThemeKey(str, Enum):
    # ... existing keys ...
    
    # Add your custom keys
    UI_MY_CUSTOM_COLOR = 'ui.my_custom_color'
    DATA_MY_TYPE = 'data.my_type'
    MY_CATEGORY_THING = 'my_category.thing'
```

Then update built-in themes in `src/haywire/ui/themes/builtin.py`:

```python
class DefaultTheme(PythonTheme):
    VALUES = {
        # ... existing values ...
        ThemeKey.UI_MY_CUSTOM_COLOR: "#abc123",
        ThemeKey.DATA_MY_TYPE: "#def456",
    }
```

### Using Custom Keys Without Enum

You don't need to add keys to `ThemeKey` - any string works:

```python
# Use custom key directly
custom_color = ThemePalette.get('my_plugin.special_color', fallback='#ff0000')

# In your TOML theme
[my_plugin]
special_color = "#00ff00"
```

This is useful for plugins or extensions that want their own theme values.

---

## Theme Metadata Settings

Theme metadata controls theme behavior and information:

```python
from haywire.ui.themes.base import ThemeMetadata

metadata = ThemeMetadata(
    name="My Theme",              # Display name
    author="Your Name",           # Optional: theme author
    description="Description",    # Optional: what this theme is for
    version="1.0.0",             # Optional: version string
    extends="default",            # Optional: parent theme to inherit from
    priority="Preference"         # 'Preference' (default) or 'Theme'
)
```

### Priority Field

The `priority` field controls how theme values interact with preferences:

**`priority="Preference"` (default):**
- User preferences always win
- Theme values are only used when no preference is provided
- Good for themes that suggest colors but allow customization

**`priority="Theme":`**
- Theme values take priority
- Preferences are only used when theme doesn't define a value
- Good for strict design systems or branded themes

Example:

```python
# Theme with Priority='Preference'
color = ThemePalette.get('ui.primary', preference='#ff0000')
# Returns: '#ff0000' (preference wins)

# Theme with Priority='Theme' (and theme defines 'ui.primary')
color = ThemePalette.get('ui.primary', preference='#ff0000')
# Returns: theme's value (theme wins)

# Theme with Priority='Theme' (but theme doesn't define 'ui.special')
color = ThemePalette.get('ui.special', preference='#ff0000')
# Returns: '#ff0000' (preference used as fallback)
```

---

## Theme Inheritance

Themes can inherit from other themes using the `extends` field to avoid duplication.

### In Python Themes

```python
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.keys import ThemeKey

class MyBaseTheme(PythonTheme):
    metadata = ThemeMetadata(
        name="My Base",
        priority="Preference"
    )
    
    VALUES = {
        ThemeKey.UI_PRIMARY: "#2196f3",
        ThemeKey.UI_SECONDARY: "#757575",
        ThemeKey.UI_ACCENT: "#ff4081",
        # ... many more values ...
    }

class MyDarkTheme(PythonTheme):
    metadata = ThemeMetadata(
        name="My Dark",
        extends="my_base",  # Inherit from base
        priority="Preference"
    )
    
    # Only override what changes
    VALUES = {
        ThemeKey.UI_PRIMARY: "#42a5f5",  # Lighter blue for dark theme
        ThemeKey.UI_TEXT_PRIMARY: "#ffffff",  # White text
        # Everything else inherited from MyBaseTheme
    }
```

You can also use Python class inheritance:

```python
class MyDarkTheme(DefaultTheme):
    """Extends DefaultTheme, only overriding specific colors."""
    
    metadata = ThemeMetadata(
        name="My Dark Theme",
        author="Your Name",
        description="Dark variant"
    )
    
    # Only override what you want to change
    VALUES = {
        **DefaultTheme.VALUES,  # Inherit all parent colors
        # Override specific colors
        ThemeKey.UI_PRIMARY: "#42a5f5",
        ThemeKey.UI_NODE_BACKGROUND: "rgba(20, 20, 20, 0.95)",
    }
```

### In TOML Themes

TOML themes automatically support inheritance:

```toml
[metadata]
name = "Ocean Dark"
extends = "default"  # Inherit from default theme

# Only define what you want to change
[ui]
primary = "#0288d1"
node_background = "rgba(30, 30, 30, 0.9)"

[data]
float = "#00bcd4"
```

### Inheritance Rules

1. Child theme values override parent theme values
2. Priority is per-theme: each theme in the chain has its own priority
3. Lookup order: child theme → parent theme → grandparent theme → ...
4. First matching value wins

Example inheritance chain:
```
ocean.toml → extends → DefaultTheme → falls back to hardcoded defaults

When you request a color:
ThemePalette.get('ui.primary')
# 1. Check ocean.toml's [ui] section
# 2. If not found, check DefaultTheme.VALUES
# 3. If not found, use fallback or empty string
```

---

## Creating Your Own TOML Theme

### Step 1: Create Theme File

Create a file in `~/.haywire/themes/my_theme.toml`:

```toml
[metadata]
name = "My Amazing Theme"
author = "Your Name"
description = "A theme optimized for my workflow"
version = "1.0.0"
extends = "default"              # Optional: inherit from another theme
priority = "Preference"           # Optional: 'Preference' or 'Theme'

# UI Section - using dot notation for keys
[ui]
primary = "#3498db"
secondary = "#2c3e50"
accent = "#e74c3c"
node_background = "rgba(255, 255, 255, 0.95)"
canvas_background = "#1a1a1a"

# Data Types Section
[data]
float = "#3498db"
int = "#9b59b6"
str = "#2ecc71"
bool = "#e67e22"
list = "#e74c3c"

# Flow Types Section
[flow]
control = "#3498db"
callback = "#e74c3c"
data = "#2ecc71"

# Custom Section (for your own use)
[my_plugin]
highlight_color = "#f39c12"
border_color = "#34495e"
```

### Step 2: Use Your Theme

```python
from haywire.ui.themes import ThemePalette

# List available themes (yours should appear)
themes = ThemePalette.list_themes()
print(themes)  # ['default', 'dark', 'my_theme', ...]

# Switch to your theme
ThemePalette.set_theme('my_theme')

# Use theme values
primary = ThemePalette.get('ui.primary')
custom = ThemePalette.get('my_plugin.highlight_color')
```

### Step 3: Hot Reload During Development

```python
# After editing the TOML file, reload it
ThemePalette.reload_current_theme()

# Or register an observer to update UI automatically
def on_theme_change(theme_name, theme):
    print(f"Theme changed to: {theme_name}")
    # Trigger UI refresh...

ThemePalette.register_observer(on_theme_change)
```

---

## Creating Python Themes

For built-in themes, create a new Python theme in `src/haywire/ui/themes/builtin.py`:

```python
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.keys import ThemeKey
from haywire.core.data.enums import DataType, FlowType

class MyCustomTheme(PythonTheme):
    """My custom theme description."""
    
    metadata = ThemeMetadata(
        name="My Custom Theme",
        author="Your Name",
        description="A beautiful custom color scheme"
    )
    
    VALUES = {
        # Data type colors
        ThemeKey.DATA_FLOAT: "#00bcd4",
        ThemeKey.DATA_INT: "#03a9f4",
        ThemeKey.DATA_STR: "#4dd0e1",
        ThemeKey.DATA_BOOL: "#26c6da",
        ThemeKey.DATA_LIST: "#00acc1",
        ThemeKey.DATA_DICT: "#0097a7",
        ThemeKey.DATA_BYTES: "#006064",
        ThemeKey.DATA_ANY: "#b0bec5",
        
        # Flow type colors
        ThemeKey.FLOW_CONTROL: "#f44336",
        ThemeKey.FLOW_CALLBACK: "#ff5722",
        ThemeKey.FLOW_DATA: "#4caf50",
        
        # UI colors - semantic
        ThemeKey.UI_PRIMARY: "#0288d1",
        ThemeKey.UI_SECONDARY: "#0097a7",
        ThemeKey.UI_ACCENT: "#00acc1",
        
        # UI colors - status
        ThemeKey.UI_ERROR: "#f44336",
        ThemeKey.UI_WARNING: "#ff9800",
        ThemeKey.UI_SUCCESS: "#4caf50",
        ThemeKey.UI_INFO: "#2196f3",
        
        # UI colors - node/port
        ThemeKey.UI_NODE_BACKGROUND: "rgba(30, 30, 30, 0.9)",
        ThemeKey.UI_NODE_BORDER: "#424242",
        ThemeKey.UI_NODE_SELECTED_BORDER: "#0288d1",
        ThemeKey.UI_PORT_BORDER: "#616161",
        ThemeKey.UI_PORT_DEFAULT: "#9e9e9e",
        
        # UI colors - canvas
        ThemeKey.UI_CANVAS_BACKGROUND: "#1a1a1a",
        ThemeKey.UI_CANVAS_GRID_LINE: "#2d2d2d",
        ThemeKey.UI_CANVAS_GRID_DOT: "#404040",
        ThemeKey.UI_SELECTION_BOX: "rgba(2, 136, 209, 0.3)",
        ThemeKey.UI_SELECTION_BOX_BORDER: "#0288d1",
        
        # UI colors - text
        ThemeKey.UI_TEXT_PRIMARY: "#ffffff",
        ThemeKey.UI_TEXT_SECONDARY: "#b0b0b0",
        ThemeKey.UI_TEXT_DISABLED: "#616161",
        ThemeKey.UI_TEXT_HINT: "#757575",
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

---

## TOML Theme Structure Reference

### Complete Example

```toml
# ============= Metadata (Required) =============
[metadata]
name = "Theme Name"              # Required: display name
author = "Author Name"           # Optional
description = "Description"      # Optional
version = "1.0.0"               # Optional
extends = "parent_theme"         # Optional: inherit from another theme
priority = "Preference"          # Optional: 'Preference' or 'Theme'

# ============= UI Colors =============
[ui]
# Semantic colors
primary = "#2196f3"
secondary = "#757575"
accent = "#ff4081"

# Status colors
error = "#f44336"
warning = "#ff9800"
success = "#4caf50"
info = "#2196f3"

# Node/Port
node_background = "rgba(255, 255, 255, 0.3)"
node_border = "#ffffff"
node_selected_border = "#2196f3"
port_border = "#ffffff"
port_default = "#757575"

# Canvas
canvas_background = "#1e1e1e"
canvas_grid_line = "#2d2d2d"
canvas_grid_dot = "#404040"
selection_box = "rgba(33, 150, 243, 0.3)"
selection_box_border = "#2196f3"

# Text
text_primary = "#212121"
text_secondary = "#757575"
text_disabled = "#bdbdbd"
text_hint = "#9e9e9e"

# ============= Data Types =============
[data]
float = "#50b0ff"
int = "#f7b0ff"
str = "#4caf50"
bool = "#ff9800"
list = "#9c27b0"
dict = "#795548"
bytes = "#9e9e9e"
any = "#bababa"

# ============= Flow Types =============
[flow]
control = "#0000ff"
callback = "#ff0000"
data = "#00ff00"

# ============= Custom Sections =============
# Add your own sections for plugins/extensions
[my_section]
my_value = "#123456"
```

### Color Format Rules

Valid color formats:
- Hex: `#RRGGBB` (e.g., `"#3498db"`)
- Short hex: `#RGB` (e.g., `"#38d"`)
- RGBA: `rgba(R, G, B, A)` (e.g., `"rgba(52, 152, 219, 0.5)"`)
- Transparent: `"transparent"`

### Section Naming

- Section names become prefixes: `[ui]` + `primary` → `'ui.primary'`
- Use any section name for custom categories
- Keys are case-insensitive (normalized to lowercase)

---

## Theme Management

### Switching Themes

```python
# Set active theme
ThemePalette.set_theme('dark')

# Get current theme name
current = ThemePalette.get_theme_name()

# List all available themes
themes = ThemePalette.list_themes()
```

### Reloading Themes

```python
# Reload current theme from disk (useful during development)
ThemePalette.reload_current_theme()
```

---

## Observer Pattern for Theme Changes

Register callbacks to be notified when themes change:

```python
def on_theme_changed(theme_name: str, theme):
    """Called when theme changes."""
    print(f"Theme changed to: {theme_name}")
    # Re-fetch colors and update UI
    bg = ThemePalette.get(ThemeKey.UI_CANVAS_BACKGROUND)
    # ... update UI elements ...

# Register observer
ThemePalette.register_observer(on_theme_changed)

# Unregister when done
ThemePalette.unregister_observer(on_theme_changed)
```

### Best Practice for UI Updates

```python
def _on_theme_changed(self, theme_name: str, theme):
    """Update UI when theme changes."""
    # Use deferred update to avoid UI deletion during callbacks
    ui.timer(0.1, self._update_ui_colors, once=True)

ThemePalette.register_observer(self._on_theme_changed)
```

---

## Extending the Palette

To add new color values to the theme system:

### Step 1: Add Enum Value

Add your new color key to the `ThemeKey` enum in `src/haywire/ui/themes/keys.py`:

```python
class ThemeKey(str, Enum):
    """Theme color keys with IDE autocomplete support."""
    
    # ... existing colors ...
    
    # Your new color
    MY_NEW_COLOR = 'my_new_color'
```

### Step 2: Add Default Values to Built-in Themes

Update `DefaultTheme` in `src/haywire/ui/themes/builtin.py`:

```python
class DefaultTheme(PythonTheme):
    VALUES = {
        # ... existing colors ...
        
        # Your new color with default value
        ThemeKey.MY_NEW_COLOR: "#ff00ff",
    }
```

### Step 3: Use Your New Color

Now you can use it in your code with full autocomplete:

```python
from haywire.ui.themes import ThemePalette, ThemeKey

my_color = ThemePalette.get(ThemeKey.MY_NEW_COLOR)
```

### Adding New Data Type Colors

If you add a new `DataType` enum value in `core/data/enums.py`:

```python
class DataType(Enum):
    # ... existing types ...
    TENSOR = 'tensor'  # New type
```

Then add its default color to themes:

```python
class DefaultTheme(PythonTheme):
    VALUES = {
        # ... existing types ...
        ThemeKey.DATA_TENSOR: "#9c27b0",  # Add to ThemeKey first
    }
```

### Adding New Flow Type Colors

If you add a new flow type, update themes similarly:

```python
VALUES = {
    # ... existing types ...
    ThemeKey.FLOW_NEW_TYPE: "#00ff00",
}
```

---

## Best Practices

1. **Use ThemeKey enum for built-in keys**: Provides autocomplete and type safety
   ```python
   # ✅ Good - Type-safe with autocomplete
   color = ThemePalette.get(ThemeKey.UI_PRIMARY)
   
   # ❌ Avoid - No autocomplete, typo-prone
   color = ThemePalette.get('primery')  # Typo!
   ```

2. **Use string keys for custom values**: Flexible for plugins/extensions
   ```python
   # ✅ Good for custom/plugin keys
   color = ThemePalette.get('my_plugin.special_color', fallback='#ff0000')
   ```

3. **Always provide fallbacks**: Ensures your code works even if theme is incomplete
   ```python
   # ✅ Good - Provides sensible fallback
   color = ThemePalette.get(
       ThemeKey.UI_NODE_BACKGROUND, 
       fallback='rgba(255, 255, 255, 0.3)'
   )
   ```

4. **Use inheritance**: Create minimal theme overrides instead of duplicating everything
   ```python
   # ✅ Good - Only override what changes
   class MyTheme(DefaultTheme):
       VALUES = {
           **DefaultTheme.VALUES,
           ThemeKey.UI_PRIMARY: "#custom",
       }
   
   # ❌ Avoid - Duplicating everything
   class MyTheme(PythonTheme):
       VALUES = {
           # ... copying all 20+ colors ...
       }
   ```

5. **Set priority appropriately**: Use 'Preference' for flexible themes, 'Theme' for strict designs
   ```toml
   [metadata]
   priority = "Preference"  # Allows user customization
   ```

6. **Organize custom keys**: Use section prefixes to avoid conflicts
   ```python
   # ✅ Good - Clear namespace
   color = ThemePalette.get('my_plugin.color')
   
   # ❌ Avoid - Could conflict with built-in keys
   color = ThemePalette.get('color')
   ```

7. **Register observers for dynamic UI updates**: Keep UI in sync with theme changes
   ```python
   ThemePalette.register_observer(self._on_theme_changed)
   ```

---

## Troubleshooting

### Theme not found

```python
# Check if theme exists
themes = ThemePalette.list_themes()
print(themes)

# Returns False if theme doesn't exist
success = ThemePalette.set_theme('nonexistent')
```

**Solutions:**
- Check file is in `~/.haywire/themes/` (for TOML themes)
- Check filename matches theme name (without `.toml`)
- For Python themes, ensure it's registered in `BUILTIN_THEMES`

### Colors not applying

**Check theme priority:**
```python
# If priority='Theme', theme value wins
color = ThemePalette.get('ui.primary', preference='#ff0000')
# Returns theme's primary color, not #ff0000

# If priority='Preference' (default), preference wins
color = ThemePalette.get('ui.primary', preference='#ff0000')
# Returns #ff0000
```

**Verify key spelling:**
```python
# Keys are case-insensitive but must match
ThemePalette.get('UI.PRIMARY')  # Works
ThemePalette.get('ui.primary')  # Works
ThemePalette.get('ui.priamry')  # Doesn't work - typo
```

**Check color format:**
Valid formats: `#RGB`, `#RRGGBB`, `rgba(R, G, B, A)`, `transparent`

### Values not updating

```python
# After editing TOML file, reload it
ThemePalette.reload_current_theme()

# Ensure observers are registered
def on_change(theme_name, theme):
    # Update UI here
    pass

ThemePalette.register_observer(on_change)
```

### TOML Syntax Error

```python
# Will raise ThemeValidationError with details
ThemePalette.set_theme('broken_theme')
```

Validate your TOML file syntax at: https://www.toml-lint.com/

### Missing Color in Theme

If a color is missing, the system falls back gracefully:

```toml
# mytheme.toml - only defines primary
[ui]
primary = "#00ff00"
```

```python
# Request missing secondary
color = ThemePalette.get('ui.secondary', fallback='#757575')
# Returns: '#757575' (fallback value)

# With inheritance
color = ThemePalette.get('ui.secondary')
# Checks mytheme → parent theme → returns parent's value
```

---

## File Structure

```
src/haywire/ui/themes/
├── README.md              # This file
├── __init__.py           # Public API exports
├── base.py               # BaseTheme, PythonTheme, TOMLTheme
├── builtin.py            # Built-in theme definitions
├── keys.py               # ThemeKey enum
├── loader.py             # TOML theme loader and validator
├── palette.py            # ThemePalette manager (main API)
├── utils.py              # Color utilities (validation, conversion)
└── data/                 # TOML theme files
    ├── default.toml
    ├── dark.toml
    └── ocean.toml

~/.haywire/themes/        # User TOML themes
    ├── my_theme.toml
    └── custom.toml
```

---

## API Reference Summary

### ThemePalette Methods

```python
# Get theme values
ThemePalette.get(key, preference=None, fallback='') -> str

# Theme management
ThemePalette.set_theme(theme_name: str) -> bool
ThemePalette.get_theme_name() -> str
ThemePalette.list_themes() -> List[str]
ThemePalette.reload_current_theme() -> bool

# Observers
ThemePalette.register_observer(callback) -> None
ThemePalette.unregister_observer(callback) -> None
```

### Example Usage

```python
from haywire.ui.themes import ThemePalette, ThemeKey

# Get a color
color = ThemePalette.get(ThemeKey.UI_PRIMARY, fallback='#2196f3')

# Switch themes
ThemePalette.set_theme('dark')

# Watch for changes
def on_change(name, theme):
    print(f"Now using: {name}")
    
ThemePalette.register_observer(on_change)
```