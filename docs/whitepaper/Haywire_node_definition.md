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

        # Extract file-level HAYWIRE declarations and auto-assign to node attributes
        file_declarations = {}

        # Check for HAYWIRE constants in the module globals
        if 'HAYWIRE_LIBRARY_NAME' in module_globals:
            file_declarations['library_name'] = module_globals['HAYWIRE_LIBRARY_NAME']
        if 'HAYWIRE_LIBRARY_URL' in module_globals:
            file_declarations['library_url'] = module_globals['HAYWIRE_LIBRARY_URL']
        if 'HAYWIRE_PACKAGE_NAME' in module_globals:
            file_declarations['package_name'] = module_globals['HAYWIRE_PACKAGE_NAME']

        # Auto-assign file-level declarations to node metadata if not explicitly set
        if 'node_library_name' not in attrs and 'library_name' in file_declarations:
            attrs['node_library_name'] = file_declarations['library_name']
            metadata_attrs.append('node_library_name')

        if 'node_library_url' not in attrs and 'library_url' in file_declarations:
            attrs['node_library_url'] = file_declarations['library_url']
            metadata_attrs.append('node_library_url')

        if 'node_package' not in attrs and 'package_name' in file_declarations:
            attrs['node_package'] = file_declarations['package_name']
            metadata_attrs.append('node_package')

        # Update metadata_attrs list
        attrs['_node_metadata_attrs'] = list(set(metadata_attrs))

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
        self.is_control_node = False # Set_automatically()
        self.is_data_node = True # Set_automatically()
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
HAYWIRE_PACKAGE_NAME = "com.math.basic"

class BaseNode(HaywireNode):
    node_display_name = 'Node Name'
    node_description = 'Node Description'
    node_name = 'Node_NAME'
    node_package = 'org.github.maybites.haywire.nodes'      # override the default package name: HAYWIRE_PACKAGE_NAME
    node_library_name = 'MathLibrary'                       # override the default library name: HAYWIRE_LIBRARY_NAME
    node_library_url = 'https://haywire.io/docs/node-help'  # override the default library url: HAYWIRE_LIBRARY_URL
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
