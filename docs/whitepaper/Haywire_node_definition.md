## Complete Node Definition Template

```python
# ============================================================================
# Enhanced Metaclass with Library/Package Support
# ============================================================================

import inspect
import sys

class NodeMetadataMeta(type):  # Assuming HaywireMeta inherits from type
    def __new__(cls, name, bases, attrs):
        # Automatically identify metadata attributes
        metadata_attrs = []
        for attr_name, attr_value in attrs.items():
            if attr_name.startswith('node_') and not callable(attr_value):
                metadata_attrs.append(attr_name)

        attrs['_node_metadata_attrs'] = metadata_attrs

        # Get the module where this class is being defined
        frame = inspect.currentframe()
        try:
            # Go up the call stack to find the module that's defining this class
            caller_frame = frame.f_back
            while caller_frame:
                if caller_frame.f_code.co_name == '<module>':
                    module_globals = caller_frame.f_globals
                    break
                caller_frame = caller_frame.f_back
            else:
                module_globals = {}
        finally:
            del frame

        # Auto-assign file-level HAYWIRE constants to node attributes if not explicitly set
        # Generic approach: HAYWIRE_* constants map to node_* attributes (case conversion)
        for const_name, const_value in module_globals.items():
            if const_name.startswith('HAYWIRE_'):
                # Convert HAYWIRE_LIBRARY_NAME -> node_library_name
                node_attr = 'node_' + const_name[8:].lower()  # Remove 'HAYWIRE_' and lowercase

                # Only assign if not explicitly set in the class
                if node_attr not in attrs:
                    attrs[node_attr] = const_value
                    metadata_attrs.append(node_attr)

        # Update metadata_attrs list
        attrs['_node_metadata_attrs'] = list(set(metadata_attrs))

        # Skip validation for abstract base classes
        # Check if this is an abstract class or the base HaywireNode class
        is_abstract = (
            name == 'HaywireNode' or  # Skip the base class itself
            attrs.get('__abstractmethods__') or  # Has abstract methods
            any(hasattr(base, '__abstractmethods__') and base.__abstractmethods__ for base in bases)  # Inherits abstract methods
        )

        if not is_abstract:
            # Validate that required node attributes are set
            required_attrs = [
                'node_name',
                'node_display_name',
                'node_package',
                'node_library_name',
                'node_library_url',
                'node_search_tags',
                'node_menu',
                'node_version'
            ]

            missing_attrs = []
            for required_attr in required_attrs:
                if required_attr not in attrs:
                    missing_attrs.append(required_attr)

            if missing_attrs:
                # Create helpful error message
                missing_haywire = []
                for attr in missing_attrs:
                    haywire_equivalent = 'HAYWIRE_' + attr[5:].upper()  # node_library_name -> HAYWIRE_LIBRARY_NAME
                    missing_haywire.append(haywire_equivalent)

                raise NodeValidationError(
                    f"Node class '{name}' is missing required attributes: {missing_attrs}\n"
                    f"Either set them explicitly in the class or define these HAYWIRE constants: {missing_haywire}"
                )

        return super().__new__(cls, name, bases, attrs)

# ============================================================================
# Node Classes
# ============================================================================

@abstractmethod
class HaywireNode(object, metaclass=NodeMetadataMeta):
    def __init__(self, node_id, graph):
        self.graph = graph
        self.node_id = node_id

        # Copy class metadata to instance attributes for serialization
        for attr_name in self._node_metadata_attrs:
            if hasattr(self.__class__, attr_name):
                setattr(self, attr_name, getattr(self.__class__, attr_name))

        # Runtime attributes
        self.help_md = None
        self.help_url = 'https://haywire.io/docs/node-help'
        self.is_control_node = False
        self.is_data_node = True
        self.is_loopback_node = False
        self.can_be_muted = True
        self.is_muted = False
        self.mute_connection = ['control_in_ID', 'control_out_ID']
        self.ui_default_color = '#FFFFFF'
        self.ui_custom_color = '#000000'
        self.ui_posX = 0
        self.ui_posY = 0
        self.ui_width = 100
        self.ui_height = 100
        self.ui_width_min = -1
        self.ui_height_min = -1
        self.ui_is_collapsable = True
        self.ui_is_collapsed = False
        self.ui_is_condensable = True
        self.ui_is_condensed = False
        self.ui_is_pinned = False
        self.ui_icon = None
        self.ui_component = None
        self.allows_variables = False

    def get_metadata_dict(self):
        """Get current instance metadata for serialization"""
        return {attr: getattr(self, attr) for attr in self._node_metadata_attrs
                if hasattr(self, attr)}

    def get_class_metadata_dict(self):
        """Get current class metadata for comparison"""
        return {attr: getattr(self.__class__, attr) for attr in self._node_metadata_attrs
                if hasattr(self.__class__, attr)}

    Configs = {}
    Properties = {}
    Inlets = {}
    Outlets = {}

# ============================================================================
# Example Custom Node Classes
# ============================================================================

# these settings set the defaults to configure the nodes defined in this file

HAYWIRE_LIBRARY_NAME = "MathLibrary"
HAYWIRE_LIBRARY_URL = "https://github.com/mathteam/mathlibrary"
HAYWIRE_PACKAGE = "com.math.basic"
HAYWIRE_VERSION = "1.0.0"
HAYWIRE_SEARCH_TAGS = ['math', 'basic']
HAYWIRE_MENU = "math/basic"

class BaseNode(HaywireNode):
    # all node_* attributes can be also set by HAYWIRE_* constants.
    # when set explicitly inside the class definition, they will override the defaults.
    node_display_name = 'Node Name'
    node_description = 'Node Description'
    node_name = 'Node_NAME'
    node_package = 'org.github.maybites.haywire.nodes'
    node_library_name = 'MathLibrary'
    node_library_url = 'https://haywire.io/docs/node-help'
    node_search_tags = ['add', 'sub', 'math', 'vector']
    node_menu = 'misc/custom'
    node_version = '0.0.0'
    node_author = 'Customer'
    node_author_url = 'https://customer.org'
    node_help_md = None
    node_help_url = 'https://haywire.io/docs/node-help'

    def __init__(self, *args, **kwargs):
        super(BaseNode, self).__init__(*args, **kwargs)

    @classmethod
    def Configs(cls):
        # some code
        setConfig('configs_id':
            {
                name: 'Configs Name',
                description: 'Configs Description',
                callback: self.graph,
                is_locked: False,
                is_visible: True,
                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value,
                    is_dirty: False
                }
            }
        )

    # defining Properties
    @classmethod
    def Properties(cls):
        # some code
        setProperty('property_id':
            {
                name: 'Property Name',
                description: 'Property Description',
                is_visible: True,
                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value,
                    is_dirty: False
                }
            }
        )


    # defining Data inlets
    @classmethod
    def Inlets(cls):
        # some code
        setInlet('ctrl_in_ID' :
            {
                coupling:{
                    flow: CTRL,
                    type: MANY,
                    mode: OPTIONAL,
                },
                name: 'Control Name',
                description: 'Control Description',
                is_connected: False
            }
        )
        setInlet('data_in_ID':
            {
                coupling:{
                    flow: DATA,
                    type: ONE,
                    mode: REQUIRED,
                },
                name: 'Data Name',
                description: 'Data Description',
                is_connected: False
                is_visible: True,
                is_lazy: True,
                has_default: 'property_id'
                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value,
                    is_dirty: False
                }
            }
        )
        setInlet('data_in_many_ID':
            {
                coupling:{
                    flow: DATA,
                    type: MANY,
                    mode: OPTIONAL,
                },
                name: 'Data Collect',
                description: 'Data Description',
                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value, # Is of type dict{'outlet.pin.id_1': value, 'outlet.pin.id_2': value}
                    is_dirty: False
                }
            }
        )

    # defining Data outlets
    @classmethod
    def Outlets(cls):
        setOutlet('ctrl_out_ID':
            {
                coupling:{
                    flow: CTRL,
                    type: ONE,
                },
                name: 'Control Name',
                description: 'Control Description',
                is_connected: False
                is_visible: True,
            }
        )
        setOutlet('data_out_ID':
            {
                coupling:{
                    flow: DATA,
                    type: MANY,
                },
                name: 'Data Name',
                description: 'Data Description',
                is_connected: False
                is_visible: True,
                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value,
                    is_dirty: False
                }
            },
        )

    # defining worker function
    def worker(self, context: dict):
        # Implement your worker logic here
        # ...

        return []
            global_data: global_data,
            local_data: local_data,
            node_id: node_id,
            node_pin_id: node_pin_id
        }

    def ON_CHANGED_CONFIG(cls):
        # Implement logic to handle configs changes
        return

    @classmethod
    def ON_VALIDATION_LAZY(cls):
        # checks if there is a condition that allows lazy evaluation. If this is the case, it sets the LAZY_MASK
        return

    @classmethod
    def ON_CHANGED_ASYNC(cls):
        # Method to check if a reference to the outside of the system (like a file) has changed.
        # sets the respective reference to dirty
        return

    @classmethod
    def ON_VALIDATION_INPUT(cls):
        # Validate the properties. Not clear anymore why this might be necessary. ComfyUI has this implemented..
        # Return False if validation fails. This would exit the execution of the flow.
        return True
```


---

## Addendum:

### Making sure an inlet with many couplings can store the data for each connection only once:

You can use the function name (or function object) as the key, which naturally ensures only one value per function since dictionary keys are unique.

```python
# storage
inlet.data.values = {}

def store_value(func, value):
    """Helper function to store values by function reference"""
    inlet.data.values[func] = value

---

def set_outlet_pin():
    node_id.store_value(outlet_pin, "Processing completed")
    ...

```
