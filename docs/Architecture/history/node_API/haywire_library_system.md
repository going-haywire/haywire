# haywire library system design

For transparency reasons, I let claude 4 sonnet to design the haywire library system. 

I provided it the following files:

* @node_discovery_system.py
* @haywire-nicegui-example.py

The node system I intend to create needs a way to organize the nodes being used in libraries.

The idea is to create a library structure like this:

libraries / <labraryname> / adapters
libraries / <labraryname> / widgets
libraries / <labraryname> / data
libraries / <labraryname> / nodes

in the future there can be multiple places where libraries are located, they just have to adhere to a specifc structure.

the core nodes (all the loop, while, event, output, for-loops, setter, getter etc.) will be probably placed inside a library of the core:

haywire / libraries / core / ....

in there will also be the widgets, the defined DataStructs, the adapters that can transform from one dataStruct to another (int -> float, string -> int, string -> float) etc. these adapter will be used by the pipes to make these transformations.

the nodes have to be loaded by the node dicovery system, A first sketch can be found here: @node_discovery_system.py .

widgets are custom niceGUI components that can render the datastructs inside the node so the user can manipulate the data. something similar must happen for widgets. though not as sophisticated: the mapping has to be a simple string -> class that can be reolved when the nodes are rendered for the gui.

currently the @haywire-nicegui-example.py has the class NiceGUINodeRenderer, with multiple functions for different widgets. The new system must have these widgets in their separate files (or combined within the same but as individual classes) and through a central registry made availble to the method that help to generate the node GUI.

similar to the adapters, which have to be available in a central place that allows the graph to evaluate if a connection between two pins with different datastructs are allowed because an adapter exists. the idetification happens through the DataField.id.

can you create me a plan on how to approach such a change?

---

Implementation Plan
Phase 1: Core Infrastructure (Foundation)
Create Registry System Base Classes
WidgetRegistry - Maps widget names to NiceGUI component classes
AdapterRegistry - Maps DataField type pairs to conversion functions
LibraryRegistry - Manages library discovery and loading
Design Library Metadata System
Library __init__.py files contain metadata (name, version, dependencies)
Auto-registration hooks for widgets, adapters, and nodes
Dependency resolution between libraries
Implement Library Discovery
Scan multiple library paths (configurable)
Validate library structure
Load libraries in dependency order
Handle missing/broken libraries gracefully
Phase 2: Widget System Refactoring
Extract Widgets from NiceGUINodeRenderer
Create individual widget classes from existing _create_* methods
Base NodeWidget class with standard interface
Widget registration decorators/mechanisms
Create Core Widget Library
Move slider, checkbox, number, etc. to haywire/libraries/core/widgets/
Implement widget discovery and registration
Update NiceGUINodeRenderer to use widget registry
Phase 3: Adapter System
Design Adapter Interface
Base TypeAdapter class with can_convert() and convert() methods
Registration system for source->target type mappings
Integration with pipe connection validation
Create Core Adapters
Basic type conversions (int↔float, str↔numeric, etc.)
Place in haywire/libraries/core/adapters/
Register with central adapter registry
Integrate with Connection System
Update pipe/connection logic to check adapter registry
Auto-suggest/apply conversions when connecting incompatible types
Visual indicators for adapted connections
Phase 4: Node System Integration
Extend Node Discovery System
Update existing 
NodeRegistry
 to work with library structure
Library-aware node resolution
Handle node conflicts between libraries
Create Core Node Library
Move fundamental nodes (loops, events, setters, getters) to haywire/libraries/core/nodes/
Organize by functionality (control, data, math, etc.)
Ensure proper registration and discovery
Phase 5: Testing & Documentation
Create Example Custom Library
Demonstrate full library structure
Custom nodes, widgets, adapters, and data types
Test multi-library scenarios
Integration Testing
Library loading and discovery
Widget rendering with registry
Adapter-based connections
Node creation from multiple libraries
Key Design Decisions
Registry Pattern
Centralized registries for cross-cutting concerns
Lazy loading to avoid circular dependencies
Plugin-style architecture for extensibility
Library Isolation
Each library manages its own components
Clear dependency declaration
Graceful degradation for missing libraries
Backward Compatibility
Existing node discovery system remains functional
Gradual migration path for current nodes
Legacy widget support during transition
Benefits of This Approach
Modularity: Clean separation between nodes, widgets, adapters, and data
Extensibility: Easy to add new libraries without core changes
Maintainability: Organized code structure with clear responsibilities
Reusability: Widgets and adapters can be shared across libraries
Scalability: Multiple library locations support different deployment scenarios
Would you like me to start implementing any specific phase of this plan, or would you prefer to discuss any aspects in more detail first?

---

here some more context: @file:Haywire_design.md 

A couple of corrections:

when connecting incompatible types that don't have an adapter throw an error. There will be two places where a connection is checked: when the user creates a connection via GUI, the userinterface needs a list of all adapters and gives back an error right away and erfuses to keep the connection. if for some reason a invalid connection passes this test, when the assembly process happens and the pipes are generated and there is no adapter for the attempted connection, an error can be thrown. but for the time beeing focus only on the availability if the adapter information in a suitable data format. the GUI and the assembly will be done at a later time.

also, Visual indicators for adapted connections is for a later time when integration of GUI becomes relevant. this will happen with the rendering of the conneciton within the GUI and shall not be part of this task.

Create Core Node Library but implement only two example classes. once the whole system works we will expand. but you can already add all the widgets form point 4.

also move the content of @__init__.py into this core library, thats where it would belong ultimately.

do  create a test library outside the src/haywire (put it reporoot/libraries/test, but implement only one class and only one widget and one adapater and one datastruct. this to see that multi library 

Legacy widget support during transition: what do have in mind here?

any more questions?

---

Clarifications & Corrections Understood:
Adapter Error Handling: Throw errors for incompatible connections without adapters - focus on making adapter information available in suitable data format for now
Visual Indicators: Deferred until GUI integration (not part of this task)
Core Node Library: Implement only 2 example classes initially, but include all widgets from point 4
Data Definitions: Move content from 
src/haywire/core/data/init.py
 into the core library
Test Library: Create minimal test library at repo_root/libraries/test with 1 class, 1 widget, 1 adapter, 1 datastruct
Question about Legacy Widget Support:
Regarding "Legacy widget support during transition" - I was thinking of a fallback mechanism where:

If a widget isn't found in the new registry system, fall back to the old hardcoded methods in 
NiceGUINodeRenderer
/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/playground/node_API/haywire-nicegui-example.py
This would allow gradual migration without breaking existing functionality
Once all widgets are migrated, remove the fallback
Is this what you had in mind, or should we do a clean break without backward compatibility?

Updated Implementation Approach:
Based on your corrections, here's the refined approach:

Phase 1: Core Infrastructure
Create registry base classes (WidgetRegistry, AdapterRegistry, LibraryRegistry)
Implement library discovery mechanism
Move 
src/haywire/core/data/init.py
 content to haywire/libraries/core/data/
Phase 2: Widget System
Extract ALL widgets from 
NiceGUINodeRenderer
 into individual classes
Create core widget library with all current widget types
Implement widget registry and update renderer
Phase 3: Adapter System
Create adapter interface and registry (focus on data availability)
Implement basic type conversion adapters
Make adapter info queryable for connection validation
Phase 4: Node System
Create 2 example core node classes
Update node discovery to work with library structure
Phase 5: Test Library
Create minimal test library outside src/haywire with 1 of each component type

---

and then it goes..