# haywire node API design

For transparency reasons, I let claude 4 opus to design the haywire node API. 

I provided it the following files:

* Haywire_node_design.md
* Haywire_node_definition.md
* Haywire_datatypes.md

---
I asked:

I have the following problem:

consider this sketch for the haywire node definition. The class BaseNode(HaywireNode): shows a potential example for a custom class that defines a node in the haywire system. It consists of configs (data that is manipulated through an UI to config the nodes behaviour and appearance), properties (data that is used to evaluate/execute the nodes core function - also called worker), inlets (data that can come from other nodes upstream) and outlets (data that influences nodes further downstream)

the inlets can have properties associated to them to set their default values if no connection is attached to this inlet. if there is a connection, it ignores the default value and the property should not show anymore in the UI representation of the node inside the graph editor. there are inlets that have no properties associated, for example control inlets, but there might also be data inlets that expect complex data that cannot easily displayed within a UI.  ( here are the examples of ComfyUI  https://docs.comfy.org/custom-nodes/backend/datatypes and
LangFlow https://docs.langflow.org/data-types), something that also should be possible with haywire.

it also should support these core data types: The Data-types include int, float, str, bool, bytes, object
The Data-category include scalar, list, tuple, set, dict

the more complex data types will be wrapped within a dict.

all those config, properties, inlets and outlets are planned to be represented as dicts- maybe even as one gigantic dict that contains all those definitions.  this would certainly make the serialization easy.

each definition of a config, property, inlet and outlet has also a sub dict like

                data: {
                    type: Datatype,
                    class: 'Custom',
                    category: SCALAR,
                    value: value,
                    is_dirty: False
                }

the idea here is, that if a property is associated with an inlet, the data- field of an inlet is referencing the data-filed of the property if there is no connection - if there is a connection, the inlet has its own data-field. so when the worker-function access the input information it automatically gets the correct data.

if there is a connection, the upstream node will update the data-field of the inlet dict and set the flag to dirty. something that should also happen when there is no connection and the data is set through a property UI element by the user.

and, we also have the binding of the data to a UI. Haywire_datatypes.py shows a selection of UI elements that would be nice if there was a way to make them available. The trick here is, that the BaseNode(HaywireNode) should be UI agnostic, so the data that configures the UI experience of the configs and properties has to structure in such a way, that it is not evident what kind of UI is used. A strict model - view separation is required here.

also to consider: find a performative way to bind the UI and the nodes data structure. 

My idea here was to introduce a UI wrapper class that hides the HaywireNode from the UI and provides helper functions and other elements that make the UI bindings with niceGUI easy to establish.

Haywire_diagram.md provides you with the complete design of the haywire node system.

For now, I want you to focus on the data structure of the node, so it can be easily configured by the user, has the flexibility described to create this links, and can easily be binded to a UI.

in your previous reply you showed a way to solve some problems with listeners and callbacks, maybe there lies the solution for most of it. Also consider performance: when the node tree is evaluated, is dict based structure the best way to go? if it makes it most elegant way from an architectural point of view, with only little performance penalty compare to a more preformative but obstruse solution, than I would suggest focusing on this appraoch.

do you have any more questions?

---

Looking at your requirements, I have a few clarifying questions before proposing a solution:

1. **Property-Inlet Relationship**: When you say "if a property is associated with an inlet, the data-field of an inlet is referencing the data-field of the property" - do you want this to be:
   - A shared reference (changes to property immediately affect inlet)?
   - A copy-on-write mechanism?
   - Or should the inlet's data field literally point to the property's data field until a connection is made?

2. **Performance Critical Path**: During node evaluation/execution, what operations are most frequent?
   - Reading inlet values?
   - Writing outlet values?
   - Checking dirty flags?
   - Accessing config/property values?

3. **UI Binding Granularity**: For the UI binding, do you need:
   - Individual field-level change notifications (e.g., just the value changed)?
   - Or entire data dict change notifications?
   - Should the UI be notified of dirty flag changes?

4. **Data Type Validation**: Should the data structure enforce type validation when values are set, or is this handled elsewhere?

5. **Connection Lifecycle**: When a connection is made to an inlet that has an associated property:
   - Should the property's UI widget be hidden but the property data remain?
   - Should the property be completely disconnected from the inlet?
   - What happens when the connection is removed - does it revert to the property?

6. **Complex Data Types**: For complex data types wrapped in dicts, do you need:
   - Deep change detection (changes within the wrapped dict)?
   - Or is shallow detection sufficient (only when the entire dict is replaced)?

These clarifications will help me design a data structure that balances elegance, performance, and the flexibility you need for your dual-flow architecture.

---

Answer:

1. whatever makes the most elegant sense. both a copy-on-change mechanism as soon as a property is changed or inlet's data field literally point to the property's data field until a connection is made is ok. I would prefer a solution that requires as little boilerplate code to manage this. so this points to the copy-on-change mechanism, this way the inlets data field is actually available for writing from an upstream node without the need for more code.
2. Reading and writing inlet values and dirty flags. Accessing config/property values is less an issue.
3. just the value changed.
4. Data Type Validation happens on the UI level. there is a mechanism in the node system (ON_VALIDATION_INPUT) to do an additional validation before the execution of the worker-function, but this doesn't affect the current question.
5. just property's UI widget hidden (maybe with an addition flag: is_visible: True/False is to be used to show/hide the property inside the node-UI card and should be able to be set by the user, so maybe is_disabled ? or something that conveys the functionality)
6. shallow detection sufficient

---

Based on your clarifications, here's a solution that emphasizes elegance and minimal boilerplate while maintaining good performance:Now let me create a companion file showing how this integrates with NiceGUI:## Key Design Decisions:

### 1. **Elegant Data Structure**
- `DataField` class handles value storage with automatic change notification
- `ConfigurableElement` base class provides common functionality
- Clean separation between data model and UI concerns

### 2. **Minimal Boilerplate for Property-Inlet Binding**
- Automatic linking via `has_default` parameter
- Inlet's `data` property intelligently returns property data when not connected
- Copy-on-write happens naturally when inlet gets its own data

### 3. **Performance Optimizations**
- `_inlet_data_cache` for fast value access during execution
- Direct dictionary lookups for critical path operations
- Lazy cache rebuilding only when structure changes

### 4. **UI-Agnostic Design**
- `UIBinding` wrapper provides clean interface for any UI framework
- Metadata stored in `kwargs` allows UI hints without coupling
- Observer pattern for reactive updates

### 5. **Change Tracking**
- Built-in `is_dirty` flag on `DataField` for efficient processing
- Automatic dirty marking when values change
- `mark_inlets_clean()` for batch cleanup after processing

### 6. **Connection Management**
- `is_enabled` flag on properties automatically managed when inlet is connected
- Weak references prevent circular dependencies
- Support for both single and many coupling types

## Key Benefits:

1. **Clean Worker Function API**:
```python
def worker(self, context):
    # Simple, direct access
    value = self.data.get_inlet_value('value_in')
    result = process(value)
    self.data.set_outlet_value('result_out', result)
    self.data.mark_inlets_clean()
```

2. **Automatic Property-Inlet Sync**:
- No manual copying needed
- Property UI automatically disabled when connected
- Seamless fallback to property value

3. **Type-Safe UI Generation**:
- UI elements chosen based on data type and hints
- Consistent binding pattern across all UI types
- Easy to extend with new UI elements

4. **Performance Considerations**:
- Dict-based structure is fine for node configuration (not hot path)
- Cached inlet access for execution performance
- Minimal overhead for value propagation

5. **Serialization Ready**:
- Clean `to_dict()` methods throughout
- Preserves all metadata and UI hints
- Easy to reconstruct from JSON

## Extension Points:

1. **Complex Data Types**:
```python
# Wrapped in dict as you specified
complex_data = DataField(
    DataType.OBJECT, 
    DataContainerType.DICT,
    value={'type': 'mesh', 'vertices': [...], 'faces': [...]}
)
```

2. **Custom UI Hints**:
```python
# Add any UI-specific metadata
Property('color', 'Color', 
    data=DataField(DataType.STR, DataContainerType.SINGLE, '#FF0000'),
    ui_hint='color_picker',
    show_alpha=True  # Custom metadata
)
```

3. **Validation Hooks**:
```python
# Can add validation at UI binding level
def validate_before_set(value):
    if self.ON_VALIDATION_INPUT:
        return self.ON_VALIDATION_INPUT(value)
    return True
```

This design provides the elegance and minimal boilerplate you requested while maintaining good performance for the critical execution path. The dict-based structure makes serialization trivial while the caching strategy ensures fast access during node execution.

---

one issue:

inside the class Inlet you define 

*# For many coupling type* 
if coupling_type == 'many': 
   self.connections = {} *# {connection_id: DataField}*

this indicated a misunderstanding of the coupling_type = Many for Inlets.

The inlets doesn't keep track of the connections it has, at least not directly.

if it is set to have many connections, this means that the data-value  container has to hold the value from each connection. so the data would be in form of a list.

here is an example code that illustrates one possible way to deal with it:

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

Can you make me a suggestion on how to implement this into the current design before you actually update the artifacts?

---

You're absolutely right - I misunderstood the coupling_type='many' for inlets. Let me think through how to integrate this into the current design.

For an inlet with `coupling_type='many'`, the data should indeed be a collection of values from multiple upstream connections. Here are a few design options:

## Option 1: Extend DataField for Multi-Value Support

```python
class DataField:
    def __init__(self, type: DataType, category: DataCategory, value: Any = None, 
                 is_multi: bool = False):
        self.type = type
        self.category = category
        self.is_multi = is_multi
        
        if is_multi:
            self.value = {}  # {source_id: value}
            self._aggregated_value = None  # Cached list/dict of values
        else:
            self.value = value
            
    def set_value(self, value: Any, source_id: str = None):
        """Set value with optional source tracking for multi-value fields"""
        if self.is_multi:
            if source_id is None:
                raise ValueError("source_id required for multi-value DataField")
            if self.value.get(source_id) != value:
                self.value[source_id] = value
                self._aggregated_value = None  # Invalidate cache
                self.is_dirty = True
                self._notify_observers()
        else:
            # Original single-value behavior
            if self.value != value:
                self.value = value
                self.is_dirty = True
                self._notify_observers()
    
    def get_value(self):
        """Get value - returns dict for multi-value, single value otherwise"""
        if self.is_multi:
            if self._aggregated_value is None:
                # Return as dict with source IDs as keys
                self._aggregated_value = dict(self.value)
            return self._aggregated_value
        return self.value
    
    def get_values_list(self):
        """Get values as list (for multi-value fields)"""
        if self.is_multi:
            return list(self.value.values())
        return [self.value]
```

## Option 2: Separate MultiDataField Class

```python
class MultiDataField(DataField):
    """Special DataField for many-coupling inlets"""
    def __init__(self, type: DataType, category: DataContainerType):
        super().__init__(type, category)
        self.value = {}  # {source_id: value}
        
    def set_value_from_source(self, source_id: str, value: Any):
        """Set value from a specific source"""
        if self.value.get(source_id) != value:
            self.value[source_id] = value
            self.is_dirty = True
            self._notify_observers()
    
    def remove_source(self, source_id: str):
        """Remove a source (when disconnected)"""
        if source_id in self.value:
            del self.value[source_id]
            self.is_dirty = True
            self._notify_observers()
    
    def get_value(self):
        """Returns dict of {source_id: value}"""
        return dict(self.value)
    
    def get_values_list(self):
        """Returns list of values"""
        return list(self.value.values())
```

## Option 3: Keep DataField Simple, Handle Multi-Value in Inlet

```python
class Inlet(ConfigurableElement):
    def __init__(self, element_id: str, name: str, flow_type: FlowType,
                 coupling_type: str = 'one', mode: str = 'optional', **kwargs):
        super().__init__(element_id, name, **kwargs)
        self.flow_type = flow_type
        self.coupling_type = coupling_type
        self.mode = mode
        self.is_connected = False
        self.is_lazy = kwargs.get('is_lazy', False)
        self.has_default = kwargs.get('has_default', None)
        self._property_ref: Optional[weakref.ref] = None
        
        if coupling_type == 'many':
            # Store individual DataFields per source
            self._source_data: Dict[str, DataField] = {}
            self._aggregated_data: Optional[DataField] = None
        else:
            self._own_data: Optional[DataField] = None
    
    def set_value_from_source(self, source_id: str, value: Any):
        """Set value from a specific source (for many coupling)"""
        if self.coupling_type == 'many':
            if source_id not in self._source_data:
                # Create new DataField for this source
                self._source_data[source_id] = DataField(
                    self.data.type, 
                    self.data.category
                )
            self._source_data[source_id].set_value(value)
            self._update_aggregated_data()
    
    def _update_aggregated_data(self):
        """Update the aggregated data field"""
        if not self._aggregated_data:
            self._aggregated_data = DataField(
                self.data.type,
                DataContainerType.DICT  # Always return as dict
            )
        
        # Aggregate all source values
        aggregated = {
            source_id: data.get_value() 
            for source_id, data in self._source_data.items()
        }
        self._aggregated_data.set_value(aggregated)
    
    @property
    def data(self) -> Optional[DataField]:
        """Get appropriate data based on coupling type"""
        if self.coupling_type == 'many':
            return self._aggregated_data or DataField(
                self.data.type, 
                DataContainerType.DICT, 
                {}
            )
        # Original logic for single coupling
        if self.is_connected or not self._property_ref:
            return self._own_data
        prop = self._property_ref()
        return prop.data if prop else self._own_data
```

## My Recommendation: Option 1 (Extended DataField)

I think Option 1 is the cleanest because:

1. It keeps the multi-value logic encapsulated in DataField
2. It maintains backward compatibility 
3. It's flexible - the source_id could be a pipe reference, node ID, or any identifier
4. The worker function can choose to get values as dict (with source info) or list

This would integrate well with your pipe system:

```python
# In Pipe class
def propagate(self, value):
    """Propagate value through pipe"""
    if self.inlet.coupling_type == 'many':
        # Use pipe ID or source node ID as identifier
        self.inlet.data.set_value(value, source_id=self.source_id)
    else:
        self.inlet.data.set_value(value)
```

Would you like me to proceed with Option 1, or would you prefer a different approach?

---

ok, implement option 1

---

Perfect! I've implemented Option 1 with the following key changes:

## Key Implementation Details:

### 1. **Extended DataField**
- Added `is_multi` flag to support multi-value storage
- Multi-value DataFields store values as `{source_id: value}`
- `set_value()` now requires `source_id` parameter for multi-value fields
- Added utility methods: `get_values_list()`, `remove_source()`, `clear_sources()`, `get_source_ids()`

### 2. **Updated Inlet Class**
- Removed the incorrect `connections` dict
- Automatically sets `is_multi=True` on DataField when `coupling_type='many'`
- Added convenience methods for multi-value operations
- Properly initializes data structure for many-coupling inlets

### 3. **Enhanced NodeData**
- Added `get_inlet_values_list()` for easy list access to multi-value inlets
- `get_inlet_value()` returns dict for multi-value inlets (preserving source info)
- Automatic initialization of multi-value DataFields

### 4. **Example Pipe Implementation**
Shows how pipes would interact with the system:
```python
# For single coupling
pipe.propagate(value)  # Direct set

# For many coupling  
pipe.propagate(value)  # Sets with pipe_id as source
```

### 5. **Worker Function Usage**
Clean API for accessing multi-value inlets:
```python
# Get as dict with source IDs
multi_dict = self.data.get_inlet_value('data_in_many')
# {'pipe_1': 10.5, 'pipe_2': 20.3, 'pipe_3': 15.7}

# Get as list of values only
multi_list = self.data.get_inlet_values_list('data_in_many')  
# [10.5, 20.3, 15.7]
```

This design maintains backward compatibility while elegantly handling the many-coupling case. The source_id can be any identifier (pipe ID, node ID, etc.) that makes sense for your system.

---

is there a reason why not to extend like this?:

class ExampleNode(NodeData):

---

You're absolutely right! The benefits of inheriting from `NodeData` are significant:

## Benefits of Direct Inheritance:

1. **Cleaner Code**:
   ```python
   # Before (composition)
   self.data.get_inlet_value('value_in')
   self.data.configs['precision'].data.get_value()
   
   # After (inheritance)
   self.get_inlet_value('value_in')
   self.configs['precision'].data.get_value()
   ```

2. **More Pythonic**: Inheritance is the natural Python way when you want an object to BE something rather than HAVE something.

3. **Better for Your Metaclass Design**: Your `NodeMetadataMeta` can work seamlessly with a node that IS a `NodeData`:
   ```python
   class HaywireNode(NodeData, metaclass=NodeMetadataMeta):
       # Combines metadata handling with data structure
   ```

4. **Simplified UI Binding**: The renderer can work directly with the node object without an intermediate `.data` accessor.

5. **Natural Extension Point**: Custom nodes can override `NodeData` methods if needed:
   ```python
   class SpecialNode(HaywireNode):
       def get_inlet_value(self, inlet_id: str):
           # Custom preprocessing
           value = super().get_inlet_value(inlet_id)
           return self.preprocess(value)
   ```

6. **Memory Efficiency**: One less object per node instance.

7. **Better Type Hints**: IDEs and type checkers understand the relationship better.

The updated example shows how `MathProcessorNode` inherits from `HaywireNode` (which inherits from `NodeData`), combining:
- All the node metadata from your specification
- The elegant data structure we designed
- Direct access to all methods without the `.data` intermediary

This is definitely the cleaner approach for your system!

---

