# UI Integration Guide

This guide covers how to build settings panels using NiceGUI, including widget selection, categorization, and handling the settings hierarchy.

## Overview

The settings system provides rich metadata for UI rendering:

- **Categories** — Group related settings
- **Widget hints** — Suggest appropriate input controls
- **Ordering** — Control display sequence
- **Validation** — Enforce constraints
- **Override indicators** — Show global vs local state

---

## Global Settings Panel

### Basic Implementation

```python
# ui/settings_panel.py
"""Global settings panel for Haywire."""

from nicegui import ui
from haywire.core.di.config import get_library_system
from haywire.core.settings import SettingMode


def render_global_settings_panel():
    """Render the global settings panel."""
    
    registry = get_library_system().get_settings_registry()
    
    with ui.card().classes('w-full max-w-2xl p-4'):
        ui.label('Global Settings').classes('text-2xl font-bold mb-4')
        
        # Group by category
        categories = registry.definitions_by_category()
        
        for category_name in sorted(categories.keys()):
            definitions = categories[category_name]
            
            # Create expandable section for each category
            with ui.expansion(
                _format_category_name(category_name),
                icon='settings',
                value=True  # Start expanded
            ).classes('w-full mb-2'):
                
                # Sort by ui_order
                sorted_defs = sorted(definitions, key=lambda d: d.ui_order)
                
                for defn in sorted_defs:
                    _render_setting_row(registry, defn)
        
        # Save button
        ui.separator().classes('my-4')
        with ui.row().classes('justify-end'):
            ui.button(
                'Save to File',
                icon='save',
                on_click=lambda: _save_settings(registry)
            ).props('color=primary')


def _format_category_name(category: str) -> str:
    """Format category name for display."""
    # 'ui.node' -> 'UI > Node'
    parts = category.split('.')
    return ' > '.join(part.replace('_', ' ').title() for part in parts)


def _save_settings(registry):
    """Save settings to TOML file."""
    registry.save_to_toml()
    ui.notify('Settings saved', type='positive')
```

### Rendering Individual Settings

```python
def _render_setting_row(registry, defn):
    """Render a single setting row with appropriate widget."""
    
    global_val = registry.get_global(defn.name)
    current_value = (
        global_val.value if global_val.mode != SettingMode.AUTO
        else defn.default
    )
    is_override = global_val.mode == SettingMode.OVERRIDE
    
    with ui.row().classes('w-full items-center gap-2 py-1'):
        # Override indicator
        if is_override:
            ui.icon('lock', color='orange').tooltip('Forced on all nodes')
        else:
            ui.icon('lock_open', color='grey').classes('opacity-50')
        
        # Label with tooltip
        with ui.element('div').classes('w-48'):
            ui.label(defn.label).classes('font-medium')
            if defn.description:
                ui.icon('help_outline', size='xs').classes(
                    'ml-1 opacity-50 cursor-help'
                ).tooltip(defn.description)
        
        # Widget (based on type and hints)
        with ui.element('div').classes('flex-grow'):
            widget = _create_widget(registry, defn, current_value)
        
        # Override toggle button
        override_btn = ui.button(
            icon='push_pin' if is_override else 'push_pin',
            color='orange' if is_override else 'grey'
        ).props('flat dense round').tooltip(
            'Remove override' if is_override else 'Force on all nodes'
        )
        override_btn.on('click', lambda d=defn: _toggle_override(registry, d))


def _toggle_override(registry, defn):
    """Toggle override mode for a setting."""
    sv = registry.get_global(defn.name)
    current_value = sv.value if sv.mode != SettingMode.AUTO else defn.default
    
    if sv.mode == SettingMode.OVERRIDE:
        registry.set_global(defn.name, current_value, SettingMode.SET)
        ui.notify(f'{defn.label}: Override removed')
    else:
        registry.set_global(defn.name, current_value, SettingMode.OVERRIDE)
        ui.notify(f'{defn.label}: Now forced on all nodes')
```

### Widget Factory

```python
def _create_widget(registry, defn, current_value):
    """Create appropriate widget based on setting definition."""
    
    def on_change(value):
        mode = registry.get_global(defn.name).mode
        if mode == SettingMode.AUTO:
            mode = SettingMode.SET
        registry.set_global(defn.name, value, mode)
    
    # Check ui_widget hint first
    if defn.ui_widget == 'color':
        return _create_color_widget(current_value, on_change)
    
    elif defn.ui_widget == 'slider':
        return _create_slider_widget(defn, current_value, on_change)
    
    elif defn.ui_widget == 'textarea':
        return _create_textarea_widget(current_value, on_change)
    
    elif defn.ui_widget == 'password':
        return _create_password_widget(current_value, on_change)
    
    elif defn.ui_widget == 'path':
        return _create_path_widget(current_value, on_change)
    
    # Fall back to type-based selection
    elif defn.choices:
        return _create_select_widget(defn.choices, current_value, on_change)
    
    elif defn.type_ == bool:
        return _create_switch_widget(current_value, on_change)
    
    elif defn.type_ == int:
        return _create_int_widget(defn, current_value, on_change)
    
    elif defn.type_ == float:
        return _create_float_widget(defn, current_value, on_change)
    
    else:
        return _create_text_widget(current_value, on_change)


# Widget implementations

def _create_color_widget(value, on_change):
    """Color picker widget."""
    color = ui.color_input(value=value).classes('w-32')
    color.on('change', lambda e: on_change(e.value))
    return color


def _create_slider_widget(defn, value, on_change):
    """Slider with min/max and value display."""
    with ui.row().classes('items-center gap-2 w-full'):
        slider = ui.slider(
            min=defn.min_value or 0,
            max=defn.max_value or 100,
            step=0.01 if defn.type_ == float else 1,
            value=value
        ).classes('flex-grow')
        
        label = ui.label(f'{value:.2f}' if defn.type_ == float else str(value))
        label.classes('w-16 text-right')
        
        def update(e):
            on_change(e.value)
            label.text = f'{e.value:.2f}' if defn.type_ == float else str(e.value)
        
        slider.on('change', update)
    return slider


def _create_switch_widget(value, on_change):
    """Boolean switch."""
    switch = ui.switch(value=value)
    switch.on('change', lambda e: on_change(e.value))
    return switch


def _create_select_widget(choices, value, on_change):
    """Dropdown select for choices."""
    select = ui.select(options=choices, value=value).classes('w-48')
    select.on('change', lambda e: on_change(e.value))
    return select


def _create_int_widget(defn, value, on_change):
    """Integer number input."""
    number = ui.number(
        value=value,
        min=defn.min_value,
        max=defn.max_value,
        step=1,
        format='%d'
    ).classes('w-32')
    number.on('change', lambda e: on_change(int(e.value)))
    return number


def _create_float_widget(defn, value, on_change):
    """Float number input."""
    number = ui.number(
        value=value,
        min=defn.min_value,
        max=defn.max_value,
        step=0.01
    ).classes('w-32')
    number.on('change', lambda e: on_change(float(e.value)))
    return number


def _create_text_widget(value, on_change):
    """Text input."""
    text = ui.input(value=str(value)).classes('w-full')
    text.on('change', lambda e: on_change(e.value))
    return text


def _create_textarea_widget(value, on_change):
    """Multi-line text area."""
    textarea = ui.textarea(value=str(value)).classes('w-full')
    textarea.on('change', lambda e: on_change(e.value))
    return textarea


def _create_password_widget(value, on_change):
    """Password input."""
    password = ui.input(
        value=str(value),
        password=True,
        password_toggle_button=True
    ).classes('w-full')
    password.on('change', lambda e: on_change(e.value))
    return password


def _create_path_widget(value, on_change):
    """Path input with browse button."""
    with ui.row().classes('items-center gap-2 w-full'):
        path = ui.input(value=str(value)).classes('flex-grow')
        path.on('change', lambda e: on_change(e.value))
        
        async def browse():
            result = await ui.run_javascript(
                'window.showDirectoryPicker().then(h => h.name)'
            )
            if result:
                path.value = result
                on_change(result)
        
        ui.button(icon='folder_open', on_click=browse).props('flat dense')
    return path
```

---

## Node Settings Panel

The node settings panel shows local settings with inheritance indicators.

### Implementation

```python
def render_node_settings_panel(node):
    """Render settings panel for a specific node."""
    
    with ui.card().classes('w-full p-4'):
        # Header
        with ui.row().classes('items-center justify-between mb-4'):
            ui.label(f'Settings: {node.identity.label}').classes('text-xl font-bold')
            
            ui.button(
                'Reset All',
                icon='refresh',
                on_click=lambda: _reset_all_node_settings(node)
            ).props('flat dense').tooltip('Reset all to inherited values')
        
        # Get all settings info grouped by category
        all_info = node.settings.get_all_info()
        categories = _group_by_category(all_info)
        
        for category_name in sorted(categories.keys()):
            settings = categories[category_name]
            
            with ui.expansion(
                _format_category_name(category_name),
                icon='tune',
                value=True
            ).classes('w-full mb-2'):
                
                # Sort by ui_order
                sorted_settings = sorted(
                    settings,
                    key=lambda s: s[1].definition.ui_order
                )
                
                for name, info in sorted_settings:
                    _render_node_setting_row(node, name, info)


def _group_by_category(all_info: dict) -> dict:
    """Group settings by category."""
    categories = {}
    for name, info in all_info.items():
        cat = info.definition.category or 'general'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((name, info))
    return categories


def _render_node_setting_row(node, name: str, info):
    """Render a single node setting row."""
    
    defn = info.definition
    
    with ui.row().classes('w-full items-center gap-2 py-1'):
        # Status indicator
        _render_status_indicator(info)
        
        # Label
        with ui.element('div').classes('w-40'):
            ui.label(defn.label).classes('font-medium')
            if defn.description:
                ui.icon('help_outline', size='xs').classes(
                    'ml-1 opacity-50'
                ).tooltip(defn.description)
        
        # Value widget
        with ui.element('div').classes('flex-grow'):
            if info.is_overridden:
                # Read-only when globally overridden
                ui.label(str(info.value)).classes('text-gray-500 italic')
            else:
                _create_node_widget(node, name, info)
        
        # Reset button (only if locally set)
        if info.local_mode == SettingMode.SET and not info.is_overridden:
            ui.button(
                icon='refresh',
                on_click=lambda n=name: _reset_node_setting(node, n)
            ).props('flat dense round').tooltip('Reset to inherited')
        else:
            # Placeholder for alignment
            ui.element('div').classes('w-10')


def _render_status_indicator(info):
    """Render the inheritance/override status indicator."""
    
    if info.is_overridden:
        ui.icon('lock', color='orange').tooltip(
            'Forced by global settings\n'
            f'Value: {info.global_value}'
        )
    
    elif info.source == 'local':
        ui.icon('edit', color='green').tooltip(
            'Custom value for this node\n'
            f'Global default: {info.global_value or info.definition.default}'
        )
    
    elif info.source == 'global':
        ui.icon('language', color='blue').tooltip(
            'Using global setting\n'
            f'Value: {info.global_value}'
        )
    
    else:  # default
        ui.icon('auto_fix_high', color='grey').tooltip(
            'Using default value\n'
            f'Default: {info.definition.default}'
        )


def _create_node_widget(node, name: str, info):
    """Create widget for node setting."""
    
    defn = info.definition
    
    def on_change(value):
        node.settings.set(name, value)
    
    # Reuse widget factory from global settings
    return _create_widget_for_value(defn, info.value, on_change)


def _reset_node_setting(node, name: str):
    """Reset a single node setting."""
    node.settings.reset(name)
    ui.notify(f'Reset: {name}')


def _reset_all_node_settings(node):
    """Reset all node settings to inherited values."""
    node.settings.reset_all()
    ui.notify('All settings reset to inherited values')
```

---

## Widget Mapping Reference

| `ui_widget` | Widget Type | Use Case |
|-------------|-------------|----------|
| `color` | Color picker | Hex colors like `#ff0000` |
| `slider` | Range slider | Bounded numeric values |
| `textarea` | Multi-line text | Long strings, templates |
| `password` | Password field | Secrets, API keys |
| `path` | Path + browse | File/directory paths |
| `select` | Dropdown | Predefined choices |
| `switch` | Toggle switch | Boolean values |
| `number` | Number input | int/float values |
| `text` | Text input | Short strings (default) |

### Automatic Widget Selection

When `ui_widget` is not specified, the system chooses based on:

1. **Has `choices`?** → Select dropdown
2. **Type is `bool`?** → Switch
3. **Type is `int` with min/max?** → Number input (or slider if range is small)
4. **Type is `float` with min/max?** → Number input
5. **Otherwise** → Text input

---

## Live Updates

### Reacting to Setting Changes

```python
def render_live_settings_panel(node):
    """Settings panel that updates live."""
    
    # Container for dynamic content
    container = ui.element('div')
    
    def refresh():
        container.clear()
        with container:
            _render_settings_content(node)
    
    # Initial render
    refresh()
    
    # Subscribe to changes
    def on_change(name, value, source):
        refresh()
    
    node.settings.on_change(on_change)
    
    # Cleanup on disconnect
    ui.on('disconnect', lambda: node.settings.remove_callback(on_change))
```

### Hot-Reload from TOML

```python
def render_global_settings_with_reload():
    """Global settings panel with hot-reload indicator."""
    
    registry = get_library_system().get_settings_registry()
    
    with ui.card().classes('w-full p-4'):
        with ui.row().classes('items-center justify-between mb-4'):
            ui.label('Global Settings').classes('text-xl font-bold')
            
            # File watching status
            if registry._file_watch_enabled:
                with ui.row().classes('items-center gap-1'):
                    ui.icon('sync', color='green').classes('animate-spin')
                    ui.label('Watching for changes').classes('text-sm text-gray-500')
            
            # Manual reload button
            ui.button(
                'Reload',
                icon='refresh',
                on_click=lambda: _reload_settings(registry)
            ).props('flat')
        
        # ... rest of panel


def _reload_settings(registry):
    """Manually reload settings from file."""
    registry.reload_from_toml()
    ui.notify('Settings reloaded from file', type='positive')
```

---

## Styling Tips

### Consistent Layout

```python
# Use grid for aligned labels and widgets
with ui.grid(columns='auto 1fr auto').classes('gap-2 w-full'):
    for defn in definitions:
        ui.label(defn.label)
        _create_widget(...)
        _create_reset_button(...)
```

### Visual Hierarchy

```python
# Category headers
ui.label(category_name).classes('text-lg font-semibold text-primary mt-4 mb-2')

# Setting rows
with ui.row().classes('pl-4 py-1 hover:bg-gray-50 rounded'):
    ...
```

### Override Styling

```python
# Overridden settings have muted appearance
if info.is_overridden:
    widget.classes('opacity-50 pointer-events-none')
    
# Local overrides have highlight
elif info.source == 'local':
    container.classes('border-l-2 border-green-500 pl-2')
```

---

## Complete Example: Integrated Settings Dialog

```python
# ui/settings_dialog.py
"""Complete settings dialog with tabs for global and per-node settings."""

from nicegui import ui
from haywire.core.di.config import get_library_system
from haywire.core.settings import SettingMode


class SettingsDialog:
    """Modal dialog for editing settings."""
    
    def __init__(self, node=None):
        """
        Create settings dialog.
        
        Args:
            node: Optional node for node-specific settings tab
        """
        self.node = node
        self.registry = get_library_system().get_settings_registry()
        self.dialog = None
    
    def show(self):
        """Show the settings dialog."""
        with ui.dialog() as self.dialog, ui.card().classes('w-[800px] max-h-[80vh]'):
            # Header
            with ui.row().classes('w-full items-center justify-between p-4 border-b'):
                ui.label('Settings').classes('text-2xl font-bold')
                ui.button(icon='close', on_click=self.dialog.close).props('flat round')
            
            # Tabs
            with ui.tabs().classes('w-full') as tabs:
                global_tab = ui.tab('Global', icon='language')
                if self.node:
                    node_tab = ui.tab('Node', icon='tune')
            
            # Tab panels
            with ui.tab_panels(tabs, value=global_tab).classes('w-full flex-grow overflow-auto'):
                with ui.tab_panel(global_tab):
                    self._render_global_settings()
                
                if self.node:
                    with ui.tab_panel(node_tab):
                        self._render_node_settings()
            
            # Footer
            with ui.row().classes('w-full justify-end p-4 border-t gap-2'):
                ui.button('Cancel', on_click=self.dialog.close).props('flat')
                ui.button('Save', on_click=self._save, color='primary')
        
        self.dialog.open()
    
    def _render_global_settings(self):
        """Render global settings content."""
        categories = self.registry.definitions_by_category()
        
        for cat_name in sorted(categories.keys()):
            with ui.expansion(_format_category(cat_name), value=True).classes('w-full'):
                for defn in sorted(categories[cat_name], key=lambda d: d.ui_order):
                    self._render_global_setting(defn)
    
    def _render_node_settings(self):
        """Render node settings content."""
        if not self.node:
            return
        
        all_info = self.node.settings.get_all_info()
        categories = {}
        
        for name, info in all_info.items():
            cat = info.definition.category or 'general'
            categories.setdefault(cat, []).append((name, info))
        
        for cat_name in sorted(categories.keys()):
            with ui.expansion(_format_category(cat_name), value=True).classes('w-full'):
                for name, info in sorted(categories[cat_name], key=lambda x: x[1].definition.ui_order):
                    self._render_node_setting(name, info)
    
    def _render_global_setting(self, defn):
        """Render a single global setting."""
        sv = self.registry.get_global(defn.name)
        value = sv.value if sv.mode != SettingMode.AUTO else defn.default
        is_override = sv.mode == SettingMode.OVERRIDE
        
        with ui.row().classes('w-full items-center gap-4 py-2'):
            # Override lock
            lock = ui.button(
                icon='lock' if is_override else 'lock_open'
            ).props('flat dense round')
            lock.style(f'color: {"orange" if is_override else "gray"}')
            lock.on('click', lambda d=defn: self._toggle_global_override(d))
            
            # Label
            ui.label(defn.label).classes('w-48 font-medium')
            
            # Widget
            with ui.element('div').classes('flex-grow'):
                self._create_global_widget(defn, value)
    
    def _render_node_setting(self, name: str, info):
        """Render a single node setting."""
        with ui.row().classes('w-full items-center gap-4 py-2'):
            # Status icon
            if info.is_overridden:
                ui.icon('lock', color='orange')
            elif info.source == 'local':
                ui.icon('edit', color='green')
            else:
                ui.icon('link', color='grey')
            
            # Label
            ui.label(info.definition.label).classes('w-48 font-medium')
            
            # Widget or read-only display
            with ui.element('div').classes('flex-grow'):
                if info.is_overridden:
                    ui.label(str(info.value)).classes('text-gray-500')
                else:
                    self._create_node_widget(name, info)
            
            # Reset button
            if info.local_mode == SettingMode.SET:
                ui.button(
                    icon='refresh',
                    on_click=lambda n=name: self.node.settings.reset(n)
                ).props('flat dense round')
    
    def _toggle_global_override(self, defn):
        """Toggle override mode."""
        sv = self.registry.get_global(defn.name)
        value = sv.value if sv.mode != SettingMode.AUTO else defn.default
        
        new_mode = SettingMode.SET if sv.mode == SettingMode.OVERRIDE else SettingMode.OVERRIDE
        self.registry.set_global(defn.name, value, new_mode)
        
        # Refresh UI
        self.dialog.close()
        self.show()
    
    def _create_global_widget(self, defn, value):
        """Create widget for global setting."""
        def on_change(v):
            mode = self.registry.get_global(defn.name).mode
            if mode == SettingMode.AUTO:
                mode = SettingMode.SET
            self.registry.set_global(defn.name, v, mode)
        
        _create_widget(defn, value, on_change)
    
    def _create_node_widget(self, name: str, info):
        """Create widget for node setting."""
        def on_change(v):
            self.node.settings.set(name, v)
        
        _create_widget(info.definition, info.value, on_change)
    
    def _save(self):
        """Save settings and close dialog."""
        self.registry.save_to_toml()
        ui.notify('Settings saved', type='positive')
        self.dialog.close()


def _format_category(cat: str) -> str:
    """Format category name for display."""
    return ' > '.join(p.replace('_', ' ').title() for p in cat.split('.'))


def _create_widget(defn, value, on_change):
    """Create appropriate widget based on definition."""
    # Implementation from earlier in this guide
    ...


# Usage:
# SettingsDialog().show()  # Global only
# SettingsDialog(node=my_node).show()  # With node settings tab
```

---

## Next Steps

- **[API Reference](05-reference.md)** — Complete API documentation
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
