# Undo/Redo System Architecture for Node Editor Applications

## Executive Summary

This document outlines a robust, scalable architecture for implementing undo/redo functionality in node editor applications with clear view-model separation. The design follows the principle of separating general-purpose undo infrastructure from domain-specific action implementations, ensuring maintainability and extensibility.

## Core Architecture Principles

### 1. Three-Layer Separation of Concerns

**General-Purpose History Management**
- Abstract command/action storage and traversal
- Timeline management and grouping mechanisms
- No knowledge of specific node editor operations

**Domain-Specific Action Implementations** 
- Individual action types that understand their specific operations
- Encapsulate both forward (redo) and reverse (undo) transformations
- Handle serialization/deserialization of state changes

**Policy and Grouping Logic**
- High-level coordination of when actions are grouped
- User interaction patterns that determine logical operation boundaries
- Integration with UI event handling

### 2. View-Model Isolation

The undo system must respect and maintain the separation between your Graph/Node data layer and UIGraph/UINode presentation layer:

**Model Layer Actions**
- Operate directly on Graph and Node objects
- Handle structural changes (add/remove nodes, create/delete edges)
- Manage node property modifications
- Independent of UI state

**View Layer Actions**  
- Handle UI-specific state (selection, viewport, zoom, pan)
- Manage transient visual states (hover, focus, animation states)
- UI layout and positioning information

**Coordinated Actions**
- Operations that affect both model and view simultaneously
- Ensure consistency between data and presentation layers

## Core Components

### 1. History Manager
```
interface IHistoryManager {
    addAction(action: IAction): void
    addFence(): void
    undo(): boolean
    redo(): boolean
    canUndo(): boolean
    canRedo(): boolean
    clear(): void
}
```

**Responsibilities:**
- Maintain chronological action sequence
- Implement fence-based grouping for multi-step operations
- Provide traversal mechanisms for undo/redo
- Handle history limits and cleanup

### 2. Action Interface
```
interface IAction {
    execute(): void
    undo(): void
    merge(other: IAction): IAction | null
    canMerge(other: IAction): boolean
}
```

**Key Design Decisions:**
- Actions are responsible for both forward and reverse operations
- Support for action merging enables intelligent coalescing
- Actions should be immutable after creation


### 3. Action Categories for Node Editors

## Structural Graph Actions

### Node Lifecycle Actions
- `AddNodeAction`: Create new nodes in the graph with type and initial properties
- `InsertNodeInEdgeAction`: Place new node in existing connection and shift all nodes on its right further right
- `RemoveNodeAction`: Delete nodes and handle dependent edges with cleanup options
- `DuplicateNodeAction`: Clone existing node with optional position offset
- `ReplaceNodeAction`: Substitute one node type for another while preserving connections
- `ConvertNodeTypeAction`: Change node type while attempting to preserve compatible properties

### Edge/Connection Actions
- `AddEdgeAction`: Create connections between specific node ports
- `RemoveEdgeAction`: Delete specific connections
- `ReconnectEdgeAction`: Change edge source or target (drag endpoint)
- `RerouteEdgeAction`: Modify edge path/routing through waypoints
- `SplitEdgeAction`: Insert node in middle of existing connection

### Node Positioning Actions
- `MoveNodeAction`: Change individual node positions
- `MoveNodesAction`: Batch move multiple nodes maintaining relative positions
- `SnapNodeAction`: Snap node to grid/guides/other nodes
- `DistributeNodesAction`: Space nodes evenly along axis
- `AlignNodesAction`: Align nodes to common edge/center

### Hierarchical Structure Actions
- `GroupNodesAction`: Create visual/logical grouping without changing graph structure
- `UngroupNodesAction`: Dissolve node groupings

## Node Property Actions

### Basic Property Modifications
- `ChangeNodeNameAction`: Modify display label
- `ToggleNodeEnabledAction`: Enable/disable node processing

### Parameter and Configuration Actions
- `ChangeNodeParameterAction`: Modify single parameter value
- `BatchParameterChangeAction`: Modify multiple parameters simultaneously
- `ResetNodeParametersAction`: Restore defaults for all/selected parameters
- `LoadNodePresetAction`: Apply saved parameter configuration
- `SaveNodePresetAction`: Store current configuration as preset
- `CopyNodePropertiesAction`: Transfer properties between nodes
- `PasteNodePropertiesAction`: Transfer properties between nodes

### Port and Interface Actions
- `AddNodePortAction`: Create new input/output port on a SubGraph-, Source- and Sink-Node
- `RemoveNodePortAction`: Delete port and handle connections on a SubGraph-, Source- and Sink-Node
- `RenameNodePortAction`: Change port label
- `ReorderNodePortsAction`: Change port arrangement/order

### Metadata and Annotation Actions
- `AddNodeCommentAction`: Attach documentation/notes
- `EditNodeCommentAction`: Modify existing comments
- `AddNodeTagAction`: Apply categorical tags/labels
- `RemoveNodeTagAction`: Remove tags
- `SetNodeMetadataAction`: Store arbitrary key-value data

## Graph-Level Actions

### Import/Export Operations
- `ImportSubgraphAction`: Add multiple nodes/edges as a unit
- `ExportSubgraphAction`: Package selection for external use
- `ReplaceGraphAction`: Completely replace current subgraph

### Template and Pattern Actions
- `ApplyGraphTemplateAction`: Instantiate predefined graph pattern
- `CreateTemplateAction`: Save current selection as reusable template

### Encapsulation Actions
- `EncapsulateNodesAction`: Create subgraph from selected node structures
- `DecapsulateNodesAction`: Flatten subgraph nodes into the parent graph
- `CreateMacroAction`: Convert selection into reusable macro/function
- `InlineMacroAction`: Expand macro back to constituent nodes

## Selection Actions

### Basic Selection Operations
- `SelectSingleNodeAction`: Replace selection with single node
- `SelectSingleEdgeAction`: Replace selection with single edge
- `ClearSelectionAction`: Remove all selections
- `SelectAllAction`: Select entire graph contents
- `InvertSelectionAction`: Select everything not currently selected

### Additive/Subtractive Selection
- `AddToSelectionAction`: Add item to existing selection (Ctrl+click)
- `RemoveFromSelectionAction`: Remove item from selection (Ctrl+click)
- `ToggleSelectionAction`: Toggle item selection state
- `ExtendSelectionAction`: Add range to selection (Shift+click)

### Area-Based Selection
- `BoxSelectAction`: Rectangular selection with various modes (replace/add/subtract)
- `SelectByRegionAction`: Select nodes in the visible graph region

### Query-Based Selection
- `SelectByTypeAction`: Select all nodes/edges of specific type
- `SelectByPropertyAction`: Select based on property values/criteria
- `SelectConnectedAction`: Select all items connected to current selection
- `SelectUpstreamAction`: Select all nodes feeding into selection
- `SelectDownstreamAction`: Select all nodes fed by selection
- `SelectByTagAction`: Select items with specific tags/categories

### Selection Refinement
- `GrowSelectionAction`: Expand selection to neighboring items
- `ShrinkSelectionAction`: Contract selection boundary
- `SelectSimilarAction`: Find items similar to current selection
- `FilterSelectionAction`: Apply criteria filter to current selection

## UI State Actions

### Viewport and Navigation
- `PanViewportAction`: Change view position
- `ZoomViewportAction`: Modify zoom level
- `FitViewToSelectionAction`: Frame selection in viewport
- `FitViewToAllAction`: Show entire graph
- `ZoomToActualSizeAction`: Reset zoom to 100%
- `SaveViewStateAction`: Bookmark current view
- `RestoreViewStateAction`: Return to bookmarked view

## Composite Actions

### Copy/Paste Operations
- `CopySelectionAction`: Store selection to clipboard
- `CutSelectionAction`: Remove and store selection
- `PasteAction`: Create items from clipboard
- `PasteInPlaceAction`: Paste at original positions

### Alignment and Distribution
- `AlignNodesLeftAction`: Align to leftmost selected node
- `AlignNodesRightAction`: Align to rightmost selected node
- `AlignNodesCenterAction`: Align to horizontal center
- `AlignNodesTopAction`: Align to topmost selected node
- `AlignNodesBottomAction`: Align to bottommost selected node
- `DistributeHorizontallyAction`: Space evenly along X axis
- `DistributeVerticallyAction`: Space evenly along Y axis


## Grouping and Fencing Strategy

### Automatic Grouping Scenarios
- **Drag Operations**: All intermediate move events grouped as single action
- **Multi-Selection Operations**: Batch changes to selected items
- **Import/Paste**: All related creation and setup operations
- **Tool-Based Operations**: Complete tool interaction cycles

### Manual Fencing Triggers
- **User Gesture Completion**: Mouse up, key release, focus change
- **Mode Transitions**: Switching between different editor tools
- **Explicit Checkpoints**: Save operations, major workflow milestones

### Intelligent Merging
- **Incremental Changes**: Property adjustments that can be combined
- **Continuous Operations**: Drag movements that can be coalesced
- **Rapid Repetition**: Quick successive similar operations

## Integration with View-Model Architecture

### Model Action Flow
```
User Interaction → UI Layer → Create Action → Execute on Graph → Update History
```

### View Action Flow  
```
User Interaction → UI Layer → Create UI Action → Execute on UIGraph → Update History
```

### Coordinated Action Flow
```
User Interaction → Create Composite Action → Execute Model + View Changes → Update History
```

## Memory and Performance Considerations

### Action Optimization Strategies
- **State Snapshots vs Deltas**: Use deltas for small changes, snapshots for complex operations
- **Lazy Evaluation**: Defer expensive calculations until undo/redo execution
- **Reference Management**: Careful handling of object references to prevent memory leaks

### History Limits
- **Configurable Depth**: Allow users to set undo history limits
- **Memory-Based Limits**: Cap total memory usage rather than just action count
- **Automatic Cleanup**: Remove old actions beyond practical utility

## Error Handling and Recovery

### Action Validation
- **Pre-execution Checks**: Validate action viability before execution
- **State Consistency**: Ensure graph remains valid after all operations
- **Graceful Degradation**: Handle cases where undo/redo cannot complete

### Recovery Mechanisms
- **Partial Undo**: When complete reversal isn't possible
- **State Reconstruction**: Rebuild consistent state from available information
- **User Notification**: Clear feedback when operations cannot be undone

## Extension Points

### Integration Hooks
- **Pre/Post Action Events**: Allow observers to react to undo operations
- **State Change Notifications**: Keep external systems synchronized
- **Audit Trail**: Optional detailed logging for debugging and analysis

## Implementation Guidelines

### Phase 1: Core Infrastructure
1. Identify the most important actions for a simple implementation
2. Implement basic `HistoryManager` with simple action storage
3. Create fundamental action types for basic node/edge operations
4. Keep in mind the more advanced action types so architecture allows for extention
5. Establish fencing mechanism for operation grouping

### Phase 2: UI Integration
1. Connect history manager to UI interaction patterns
2. Implement view-specific actions for selection and viewport
3. Add automatic grouping for common interaction patterns

### Phase 3: Advanced Features
1. Action merging and optimization
2. Memory management and history limits
3. Serialization and persistence capabilities

### Phase 4: Polish and Extension
1. Error handling and recovery mechanisms
2. Plugin architecture for custom actions
3. Performance optimization and profiling

This architecture provides a solid foundation that scales from simple implementations to sophisticated, feature-rich undo systems while maintaining clean separation of concerns and respecting your existing view-model architecture.

# Addendum:

## Fence

A **fence** in the context of undo systems is a **marker** or **boundary** placed in the history list to group related actions together. When you perform an undo operation, it doesn't just undo a single action—it undoes all actions back to the previous fence, treating them as one logical operation.

## Visual Example

Here's what a history list might look like with fences:

```
History List:
┌─────────────────┐
│ AddNodeAction   │  ← Current position
│ SetPropertyAction│
│ ──── FENCE ──── │  ← Fence separating logical operations
│ MoveNodeAction  │
│ MoveNodeAction  │
│ MoveNodeAction  │
│ ──── FENCE ──── │
│ DeleteEdgeAction│
│ AddEdgeAction   │
│ ──── FENCE ──── │
│ ...             │
└─────────────────┘
```

When the user hits "Undo":
- The system walks backward through the history
- It undoes `AddNodeAction`, then `SetPropertyAction`
- It stops when it hits the fence
- **Result**: Both actions are undone as a single logical operation

## Practical Node Editor Examples

### Example 1: Node Creation Workflow
```
User Action: "Add a Math Node"
1. AddNodeAction (create the node)
2. SetPropertyAction (set default name)
3. SetPositionAction (place at mouse cursor)
4. SelectNodeAction (select the new node)
── FENCE ── (marks end of "add node" operation)
```

One "Undo" reverses all 4 actions, completely removing the node.

### Example 2: Drag Operation
```
User Action: "Drag node from A to B"
1. MoveNodeAction (intermediate position 1)
2. MoveNodeAction (intermediate position 2)
3. MoveNodeAction (intermediate position 3)
4. MoveNodeAction (final position)
── FENCE ── (marks end of drag)
```

One "Undo" moves the node back to its original position, not through each intermediate step.

### Example 3: Multi-Selection Delete
```
User Action: "Select 3 nodes and delete them"
1. SelectNodeAction (add node A to selection)
2. SelectNodeAction (add node B to selection)
3. SelectNodeAction (add node C to selection)
4. DeleteNodeAction (delete node A)
5. DeleteEdgeAction (delete connected edges)
6. DeleteNodeAction (delete node B)
7. DeleteEdgeAction (delete connected edges)
8. DeleteNodeAction (delete node C)
── FENCE ── (marks end of delete operation)
```

One "Undo" restores all three nodes and their connections.

## When to Add Fences

### Automatic Fence Placement
- **Mouse Up**: End of drag operations
- **Key Release**: End of keyboard-driven operations
- **Tool Changes**: Switching between different editor tools
- **Focus Loss**: When user clicks elsewhere

### Manual Fence Placement
- **Complex Operations**: Before starting multi-step procedures
- **Checkpoints**: At logical breakpoints in workflows
- **Error Recovery Points**: Before potentially risky operations

## Implementation Concept

```typescript
class HistoryManager {
  private actions: (IAction | Fence)[] = [];
  private currentIndex = -1;

  addAction(action: IAction) {
    // Add the action to history
    this.actions.push(action);
    this.currentIndex++;
  }

  addFence() {
    // Add a fence marker
    this.actions.push(new Fence());
  }

  undo() {
    // Walk backwards until we hit a fence
    while (this.currentIndex >= 0) {
      const item = this.actions[this.currentIndex];
      
      if (item instanceof Fence) {
        break; // Stop at fence
      }
      
      item.undo(); // Undo the action
      this.currentIndex--;
    }
  }
}
```

Fences make the undo system match user **mental models** of what constitutes a single "operation" rather than just technical implementation details.

## TimeLine and Grouping

**Timeline management** and **grouping mechanisms** refer to how the undo system organizes, stores, and navigates through the sequence of user actions over time. Let me break this down:

## Timeline Management

Timeline management is about maintaining and navigating the chronological sequence of actions - essentially managing the "history timeline" of what happened when.

### Core Timeline Concepts

**Linear History **
```
Past ←→ Present ←→ Future
[A] → [B] → [C] → [D] → [E] ← Current Position
                    ↑
              Can undo back to here
                           ↑
                    Can redo forward to here
```

### Timeline Operations

**Navigation**
- Moving backward through time (undo)
- Moving forward through time (redo)  
- Jumping to specific points in timeline
- Finding actions by timestamp or criteria

**Maintenance**
- Pruning old history beyond limits
- Compacting related actions
- Managing memory usage over time
- Handling timeline corruption/gaps

## Grouping Mechanisms

Grouping determines how individual actions are clustered into logical units that behave as single operations from the user's perspective.

### Types of Grouping

**1. Temporal Grouping**
Actions that happen within a time window are grouped together:
```
Timeline: [Action] → [Action] → [Action] → [Action]
Time:     0ms       50ms       100ms      2000ms
                    ←─ Group ─→              ← New Group
```

**2. Gesture-Based Grouping**
Actions that belong to a single user gesture:
```
Mouse Down → Mouse Move → Mouse Move → Mouse Move → Mouse Up
[          Single Drag Operation - One Undo Group          ]
```

**3. Semantic Grouping**
Actions that logically belong together regardless of timing:
```
User Action: "Duplicate selected nodes"
- CopySelectionAction
- PasteAction  
- PositionNodesAction
- SelectNewNodesAction
[     All grouped as "Duplicate Operation"     ]
```

**4. Hierarchical Grouping**
Nested groups for complex operations:
```
Import Graph Operation
├── Create Nodes Group
│   ├── AddNodeAction (Node 1)
│   ├── AddNodeAction (Node 2)
│   └── AddNodeAction (Node 3)
├── Create Edges Group
│   ├── AddEdgeAction (1→2)
│   └── AddEdgeAction (2→3)
└── Layout Group
    ├── PositionNodeAction (Node 1)
    ├── PositionNodeAction (Node 2)
    └── PositionNodeAction (Node 3)
```

## Practical Node Editor Examples

### Example 1: Timeline with Smart Grouping
```
Time: 0:00  User starts dragging node A
      0:01  MoveNodeAction (position 1) ┐
      0:02  MoveNodeAction (position 2) │ Temporal + Gesture
      0:03  MoveNodeAction (position 3) │ Grouping
      0:04  MoveNodeAction (position 4) ┘
      0:05  User releases mouse → End of drag group

      0:10  User clicks node B
      0:11  SelectNodeAction (node B) ← New group (different gesture)

      0:15  User starts typing to rename node B
      0:16  ChangePropertyAction (name: "A") ┐
      0:17  ChangePropertyAction (name: "Ab") │ Text editing
      0:18  ChangePropertyAction (name: "Add") │ group
      0:19  ChangePropertyAction (name: "Add Node") ┘
      0:20  User presses Enter → End of edit group
```

**Timeline Navigation:**
- Undo once: Reverts "Add Node" rename completely
- Undo twice: Reverts selection of node B  
- Undo thrice: Reverts entire drag operation of node A

### Example 2: Complex Operation Grouping
```
User Action: "Connect two nodes with validation"

Automatic Grouping:
┌─ Connection Attempt Group ─────────────────────┐
│ 1. ValidateConnectionAction (check if valid)   │
│ 2. CreateEdgeAction (create the edge)          │  
│ 3. RecalculateLayoutAction (adjust positions)  │
│ 4. SelectEdgeAction (select new edge)          │
└────────────────────────────────────────────────┘

If connection fails at step 1:
┌─ Failed Connection Group  ──┐
│ 1. ValidateConnectionAction │ ← Only this executes
│ 2. ShowErrorAction          │ ← Error handling
└─────────────────────────────┘
```

## Advanced Timeline Management

### Compression and Optimization
```
Before Compression:
[MoveNode: x=10] → [MoveNode: x=11] → [MoveNode: x=12] → ... → [MoveNode: x=50]

After Compression:
[MoveNode: from x=10 to x=50] ← Single action representing the net change
```

### Branching Strategies
```
Linear Strategy (Discard):
[A] → [B] → [C]
      ↓ (undo to B, then do X)
[A] → [B] → [X]  ← C is lost forever

Checkpoint Strategy:
[A] → [B] → [C] → [Checkpoint] → [X]
                  ↑ Can return to this saved state
```

### Smart Grouping Logic
```typescript
class GroupingManager {
  determineGrouping(newAction: IAction, lastAction: IAction): GroupStrategy {
    // Temporal: Same type within time window
    if (newAction.type === lastAction.type && 
        timeSince(lastAction) < GROUPING_WINDOW) {
      return GroupStrategy.MERGE;
    }
    
    // Gesture: Part of ongoing user interaction
    if (this.currentGesture && this.gestureInProgress()) {
      return GroupStrategy.CONTINUE_GROUP;
    }
    
    // Semantic: Logically related operations
    if (this.semanticallyRelated(newAction, lastAction)) {
      return GroupStrategy.CONTINUE_GROUP;
    }
    
    return GroupStrategy.NEW_GROUP;
  }
}
```

## Why This Matters for Node Editors

**User Mental Model Alignment**
- Users think: "I moved that node"
- System tracks: 47 individual position updates
- Timeline management groups these into one logical "move"

**Performance Optimization**
- Compress redundant actions
- Garbage collect old history
- Optimize memory usage for long editing sessions

**Flexible Navigation**
- Jump to specific edit points
- Provide rich undo/redo UI (timeline scrubbing)
- Support "go back to where I was 5 minutes ago"

The key insight is that timeline management bridges the gap between the technical reality (many small actions) and user expectations (logical operations), making the undo system feel natural and intuitive.