# Application startup
from haywire.core.di.config import init_library_system

# Initialize (typically in main.py)
init_library_system(config_dir='~/.haywire')

# Now anywhere in your code:
from haywire.core.di.config import get_library_system

registry = get_library_system().get_settings_registry()

# Define custom settings for your plugin/extension
registry.define('my_plugin.feature_x', True, label='Enable Feature X')

# Access values
value = registry.resolve('my_plugin.feature_x')[0]

# In nodes, it's even simpler:
class MyNode(BaseNode):
    def worker(self, context):
        # Direct access to any global setting
        if self.settings.debug.verbose_logging:
            pass
        
        # Local-only settings
        self.settings.define('local_thing', 42, scope=SettingScope.LOCAL_ONLY)
        x = self.settings.local_thing


# examples/my_custom_node.py
"""
Example node showing settings usage.
"""


```python

from haywire.core.node.base import BaseNode
from haywire.core.settings import SettingScope
from haywire.core.execution.execution_context import ExecutionContext

# Assuming you have type definitions like this
# from haywire.core.types import FLOAT, STRING, BOOL


class MyCustomNode(BaseNode):
    """
    Example node demonstrating the settings system.
    """
    
    def initialize(self):
        """Set up ports and settings."""
        
        # Ports (your existing pattern)
        # self.add(FLOAT.as_inlet('value', label='Input Value'))
        # self.add(FLOAT.as_outlet('result', label='Result'))
        
        # Local-only settings (no global equivalent)
        self.settings.define(
            'cache_enabled', 
            default=True,
            scope=SettingScope.LOCAL_ONLY,
            label='Enable Caching',
            description='Cache intermediate results for faster re-execution',
            category='performance'
        )
        self.settings.define(
            'cache_size', 
            default=100,
            scope=SettingScope.LOCAL_ONLY,
            label='Cache Size',
            min_value=10,
            max_value=10000,
            category='performance'
        )
        
        # Optionally set local override for a global setting
        # (Only if you want a different default for this node type)
        # self.settings['ui.node.bg_color'] = '#e8f4e8'  # Greenish tint
    
    def worker(self, context: ExecutionContext, value: float = 0.0) -> str | None:
        """Main execution logic."""
        
        # Access global settings directly (no define needed)
        if self.settings['debug.verbose_logging']:
            context.log(f"Processing value: {value}")
        
        # Or use dot notation
        if self.settings.debug.show_execution_time:
            context.log(f"Execution started")
        
        # Access local-only settings
        if self.settings.cache_enabled:
            cache_size = self.settings.cache_size
            # ... use cache ...
        
        # Check if a setting is overridden globally
        color_info = self.settings.get_info('ui.node.bg_color')
        if color_info.is_overridden:
            context.log("Note: Background color is forced by global settings")
        
        # Do computation
        result = value * 2
        
        self.out('result', result)
        return None  # Data flow node
    
    def get_background_color(self) -> str:
        """
        Used by UI renderer to get the node's background color.
        
        Demonstrates how UI code can access settings.
        """
        return self.settings['ui.node.bg_color']
    
    def get_display_config(self) -> dict:
        """
        Get all UI-related settings for rendering.
        """
        return {
            'bg_color': self.settings['ui.node.bg_color'],
            'border_color': self.settings['ui.node.border_color'],
            'font_size': self.settings['ui.node.font_size'],
            'show_labels': self.settings['ui.node.show_labels'],
            'border_radius': self.settings['ui.node.border_radius'],
        }


class ConditionalNode(BaseNode):
    """
    Control flow node example showing settings usage.
    """
    
    def initialize(self):
        # self.add(BOOL.as_inlet('condition', label='Condition'))
        # self.add(EXEC.as_outlet('true_branch', label='True'))
        # self.add(EXEC.as_outlet('false_branch', label='False'))
        
        # Local setting for this node type
        self.settings.define(
            'invert_condition',
            default=False,
            scope=SettingScope.LOCAL_ONLY,
            label='Invert Condition',
            description='Swap true/false branches'
        )
    
    def worker(self, context: ExecutionContext, condition: bool = False) -> str:
        """Execute based on condition."""
        
        # Apply local setting
        if self.settings.invert_condition:
            condition = not condition
        
        if self.settings.debug.verbose_logging:
            context.log(f"Condition: {condition}")
        
        return 'true_branch' if condition else 'false_branch'
```

# examples/settings_from_ui.py
"""
Example showing how to access settings from UI code.
"""

```python
from haywire.core.di.config import get_library_system
from haywire.core.settings import SettingMode


def render_settings_panel():
    """Example NiceGUI settings panel."""
    from nicegui import ui
    
    registry = get_library_system().get_settings_registry()
    
    with ui.card().classes('p-4'):
        ui.label('Global Settings').classes('text-xl font-bold mb-4')
        
        # Group by category
        for category, definitions in registry.definitions_by_category().items():
            with ui.expansion(category.replace('.', ' > ').title(), value=True):
                for defn in definitions:
                    global_val = registry.get_global(defn.name)
                    current_value = (
                        global_val.value if global_val.mode != SettingMode.AUTO 
                        else defn.default
                    )
                    
                    with ui.row().classes('items-center gap-2 w-full'):
                        ui.label(defn.label).classes('w-48')
                        
                        # Create appropriate widget based on type
                        if defn.type_ == bool:
                            switch = ui.switch(value=current_value)
                            switch.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, e.value))
                        
                        elif defn.choices:
                            select = ui.select(
                                options=defn.choices,
                                value=current_value
                            )
                            select.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, e.value))
                        
                        elif defn.type_ == int:
                            number = ui.number(
                                value=current_value,
                                min=defn.min_value,
                                max=defn.max_value
                            )
                            number.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, int(e.value)))
                        
                        elif defn.ui_widget == 'color':
                            color = ui.color_input(value=current_value)
                            color.on('change', lambda e, n=defn.name: 
                                     registry.set_global(n, e.value))
                        
                        else:
                            text = ui.input(value=str(current_value))
                            text.on('change', lambda e, n=defn.name: 
                                    registry.set_global(n, e.value))
                        
                        # Override toggle
                        is_override = global_val.mode == SettingMode.OVERRIDE
                        override_btn = ui.button(
                            icon='lock' if is_override else 'lock_open',
                            color='orange' if is_override else 'grey'
                        ).props('flat dense')
                        
                        def toggle_override(name=defn.name):
                            sv = registry.get_global(name)
                            if sv.mode == SettingMode.OVERRIDE:
                                registry.set_global(name, sv.value, SettingMode.SET)
                            else:
                                registry.set_global(name, sv.value, SettingMode.OVERRIDE)
                        
                        override_btn.on('click', toggle_override)
        
        # Save button
        ui.button('Save Settings', on_click=lambda: registry.save_to_toml())


def render_node_settings_panel(node):
    """Render settings panel for a specific node."""
    from nicegui import ui
    
    with ui.card().classes('p-4'):
        ui.label(f'Node Settings: {node.node_id}').classes('text-lg font-bold mb-2')
        
        for name, info in node.settings.get_all_info().items():
            with ui.row().classes('items-center gap-2'):
                # Override indicator
                if info.is_overridden:
                    ui.icon('lock', color='orange').tooltip('Forced by global settings')
                elif info.is_inherited:
                    ui.icon('link', color='grey').tooltip(f'Inherited from {info.source}')
                else:
                    ui.icon('edit', color='green').tooltip('Local override')
                
                ui.label(info.definition.label).classes('w-32')
                
                # Value display/edit
                if info.is_overridden:
                    # Read-only when overridden
                    ui.label(str(info.value)).classes('text-grey')
                else:
                    if info.definition.type_ == bool:
                        switch = ui.switch(value=info.value)
                        switch.on('change', lambda e, n=name: node.settings.set(n, e.value))
                    else:
                        inp = ui.input(value=str(info.value))
                        inp.on('change', lambda e, n=name: node.settings.set(n, e.value))
                
                # Reset button (only if locally overridden)
                if info.local_mode == SettingMode.SET:
                    ui.button(icon='refresh', on_click=lambda n=name: node.settings.reset(n)).props('flat dense')

```

# my_library/settings.py
"""
Custom settings for my library.
"""

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.settings import GlobalSettingsRegistry


CATEGORY = 'my_library'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register my library's settings."""
    
    registry.define(
        'my_library.feature_x_enabled', True,
        label='Enable Feature X',
        description='Toggle the fancy feature X',
        category=CATEGORY,
        ui_order=10
    )
    registry.define(
        'my_library.api_url', 'https://api.example.com',
        label='API URL',
        description='Base URL for external API',
        category=CATEGORY,
        ui_order=20
    )
    registry.define(
        'my_library.max_connections', 5,
        label='Max Connections',
        description='Maximum concurrent API connections',
        category=CATEGORY,
        min_value=1,
        max_value=20,
        ui_order=21
    )


# Register when library is loaded
def on_library_load():
    from haywire.core.di.config import get_settings_registry
    register(get_settings_registry())
```

## Directory Structure
```
haywire/core/settings/
├── __init__.py
├── enums.py
├── value.py
├── definition.py
├── registry.py
├── holder.py
└── builtins/
    ├── __init__.py
    ├── ui_node.py
    ├── ui_edge.py
    ├── ui_canvas.py
    ├── ui_minimap.py
    ├── execution.py
    ├── debug.py
    └── editor.py