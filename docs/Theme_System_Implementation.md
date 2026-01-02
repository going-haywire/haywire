# Haywire Theme System - User Guide

## Overview

The Haywire Theme System provides a simple, flexible way to customize colors and visual elements in your application. It supports both built-in Python themes and user-defined TOML themes with inheritance and priority-based preference handling.

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

## Understanding Key Structure: TOML Sections → String Keys

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

## Available Theme Keys

Theme keys are organized by category for clarity:

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

## Theme Inheritance

Themes can inherit from other themes using the `extends` field:

### In Python Themes

```python
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.colors import ThemeKey

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

### In TOML Themes

TOML themes automatically support inheritance:

```toml
[metadata]
name = "Ocean Dark"
extends = "default"  # Inherit from default theme

# Only define what you want to change
[ui]
primary = "#0288d1"
background = "rgba(30, 30, 30, 0.9)"

[data]
float = "#00bcd4"
```

### Inheritance Rules

1. Child theme values override parent theme values
2. Priority is per-theme: each theme in the chain has its own priority
3. Lookup order: child theme → parent theme → grandparent theme → ...
4. First matching value wins

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

### Observing Theme Changes

```python
def update_ui_colors(theme_name: str, theme):
    """Called when theme changes."""
    # Re-fetch colors and update UI
    bg = ThemePalette.get(ThemeKey.UI_CANVAS_BACKGROUND)
    # ... update UI elements ...

# Register observer
ThemePalette.register_observer(update_ui_colors)

# Unregister when done
ThemePalette.unregister_observer(update_ui_colors)
```

## Best Practices

1. **Use ThemeKey enum for built-in keys**: Provides autocomplete and type safety
2. **Use string keys for custom values**: Flexible for plugins/extensions
3. **Always provide fallbacks**: Ensures your code works even if theme is incomplete
4. **Use inheritance**: Create minimal theme overrides instead of duplicating everything
5. **Set priority appropriately**: Use 'Preference' for flexible themes, 'Theme' for strict designs
6. **Organize custom keys**: Use section prefixes like `'my_plugin.color'` to avoid conflicts

## Troubleshooting

### Theme not found
- Check file is in `~/.haywire/themes/`
- Check filename matches theme name (without `.toml`)
- Use `ThemePalette.list_themes()` to see available themes

### Colors not applying
- Verify key spelling (case-insensitive)
- Check theme priority setting
- Verify color format is valid
- Check if parent theme (if using `extends`) exists

### Values not updating
- Call `ThemePalette.reload_current_theme()` after editing TOML
- Check observer is registered correctly
- Verify UI refresh is triggered after theme change
