# haywire/core/settings/node_settings.py
"""
NodeSettings — base class for node-local settings.

Subclass inside a @node class body and declare fields with ``field()``:

    @node(node_type=NodeType.DATA)
    class FilterNode(BaseNode):
        class Settings(NodeSettings):
            strength = field[float](0.5, min=0.0, max=1.0, label='Strength')
            mode     = field[str]('fast', choices=['fast', 'precise'])

NodeSettings are:
- Purely local — values never enter the registry
- Instantiated once per node instance by the @node framework
- Registry-injected at instantiation for mirror/read_only field resolution
- Never auto-registered; field keys are assigned by _wire_settings_schemas()

Nodes access their settings via self.<inner_class_name>:
    self.settings.strength = 0.8
    self.settings.reset('strength')
"""

from .settings import Settings


class NodeSettings(Settings):
    """
    Base class for node-local settings.

    Declare as an inner class on a @node class.  The @node decorator assigns
    ``_field_key`` to each ``field()`` descriptor, and the node instance
    injects the registry at construction for mirror/read_only resolution.

    NodeSettings are never registered with SettingsRegistry.
    """

    pass
