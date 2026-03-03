"""
Haywire Assembly and Execution System - Complete Example

This file demonstrates the complete assembly and execution pipeline,
including both string-based and edge-based callback approaches.

Run this file to see the complete execution flow:
    python execution_examples.py
"""

from pathlib import Path
from haywire.core.graph.base import BaseGraph
from haywire.core.execution import Interpreter
from haywire.core.execution.event_source import SystemEventType

def _create_graph_with_math(graph: BaseGraph) -> BaseGraph:
    """
    Create graph: BeginPlay → PrintMessage with MathOP data flow
    
    Args:
        graph: The graph to populate
        
    Returns:
        The populated graph
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    from haybale_example.nodes.math_op import MathOP

    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    math_op = graph.create_node_wrapper(
        MathOP.class_identity.registry_key,
        position=(200, 100)
    )
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        print_msg.node_id, 'exec'
    )
    graph.create_edge_wrapper(
        begin_play.node_id, 'timestamp',
        math_op.node_id, 'value_a'
    )
    graph.create_edge_wrapper(
        math_op.node_id, 'result',
        print_msg.node_id, 'message'
    )
    
    return graph


# ==============================================================================
# Library System Setup
# ==============================================================================

def setup_library_system():
    """
    Initialize library system with test libraries.
    
    This must be called before creating any graphs or nodes.
    """
    from haywire.core.di.test_config import create_test_library_system
    from haywire.core.di.config import set_library_system, set_global_injector
    
    # Find project root
    current = Path(__file__).parent
    while current != current.parent:
        if (current / 'pyproject.toml').exists():
            project_root = current
            break
        current = current.parent
    else:
        raise RuntimeError("Could not find project root")
    
    # Test libraries path
    test_library_path = project_root / 'tests' / 'libraries'
    
    # Create and initialize library system
    service = create_test_library_system(
        project_root=str(project_root),
        library_paths=[str(test_library_path)],
        load_libraries=True,
        enable_file_watching=False
    )
    
    # Set global library system (required for graph operations)
    set_library_system(service)
    set_global_injector(service.injector)
    
    return service


def cleanup_library_system(service):
    """Clean up library system after examples."""
    from haywire.core.di.config import set_library_system, set_global_injector
    
    # Stop file watchers if any
    lib_registry = service.get_library_registry()
    if hasattr(lib_registry, 'stop_file_watching'):
        lib_registry.stop_file_watching()
    
    # Clear global references
    set_library_system(None)
    set_global_injector(None)


def example_simple_flow():
    """
    Example of a simple flow: BeginPlay → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_test_a.nodes.print_node import PrintMessageNode

    # Create graph
    graph = BaseGraph(
        graph_id='simple_example',
        name='Simple Flow Example'
    )
    
    _create_graph_with_math(graph)

    graph.force_validation()
    
    # Create interpreter
    interpreter = Interpreter()
    
    # Load and assemble graph
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    # Show statistics
    stats = interpreter.get_statistics()
    print(f"\nAssembly Statistics:")
    print(f"  Flows: {stats['assembly']['total_flows']}")
    for flow_info in stats['assembly']['flows']:
        print(f"    - {flow_info['flow_id']}: {flow_info['event_type']}")
    
    # Dispatch BEGIN_PLAY event
    print("\n=== Dispatching BEGIN_PLAY Event ===")
    triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    print(f"Triggered {triggered} flow(s)")
    
    # Wait for completion
    interpreter.wait_all()
    
    # Cleanup
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 2: Multiple Nodes in Sequence
# ==============================================================================

def example_sequence_flow():
    """
    Example with sequence: BeginPlay → PrintMessage → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='sequence_example',
        name='Sequence Flow Example'
    )
    
    # Create nodes
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    print_msg1 = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    print_msg2 = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(500, 100)
    )
    
    # Connect control flow: BeginPlay → PrintMessage1 → PrintMessage2
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        print_msg1.node_id, 'exec'
    )
    
    graph.create_edge_wrapper(
        print_msg1.node_id, 'done',
        print_msg2.node_id, 'exec'
    )
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    print("\n=== Dispatching BEGIN_PLAY Event ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 3: Callback System - String-Based (Dynamic)
# ==============================================================================

def example_callback_string_based():
    """
    Example with string-based callbacks (no visual connection):
    Flow 1: BeginPlay → EmitCallback (emits 'my_callback')
    Flow 2: CustomCallback (listens for 'my_callback') → PrintMessage
    
    Both nodes configured with matching callback name strings.
    No callback edge - connection happens via string matching.
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_core.nodes.custom_callback import CustomCallbackNode
    from haybale_core.nodes.emit_callback import EmitCallbackNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='callback_string_example',
        name='Callback String-Based Example'
    )
    
    # Flow 1: Emitter flow
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    emit_callback = graph.create_node_wrapper(
        EmitCallbackNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Configure emitter to use custom name mode
    emit_callback.node.ports['mode_switch'].set_value(True)  # Enable custom name
    emit_callback.node.ports['custom_callback_name'].set_value('my_callback')
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        emit_callback.node_id, 'execute'
    )
    
    # Flow 2: Listener flow
    callback_listener = graph.create_node_wrapper(
        CustomCallbackNode.class_identity.registry_key,
        position=(100, 300)
    )
    
    # Configure listener to use custom name mode
    callback_listener.node.ports['mode_switch'].set_value(True)  # Enable custom name
    callback_listener.node.ports['custom_callback_name'].set_value('my_callback')
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 300)
    )
    
    graph.create_edge_wrapper(
        callback_listener.node_id, 'triggered',
        print_msg.node_id, 'exec'
    )
    
    graph.force_validation()

    # NO callback edge between flows - connection via string matching
    print("\nString-based mode: No callback edge needed")
    print("Emitter and listener both configured with callback name 'my_callback'")
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph (String-Based Callbacks) ===")
    interpreter.load_graph(graph)
    
    # Show callback registrations
    stats = interpreter.get_statistics()
    print(f"\nCallback Statistics:")
    print(f"  Total callback edges: {stats['assembly']['callback_edges']}")
    for cb_info in stats['callbacks']['callbacks']:
        print(f"  '{cb_info['event_name']}': {cb_info['listener_count']} listeners")
    
    print("\n=== Dispatching BEGIN_PLAY Event ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    # Wait a bit for callback to trigger
    import time
    time.sleep(0.5)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 4: Callback System - Edge-Based (Visual)
# ==============================================================================

def example_callback_edge_based():
    """
    Example with edge-based callbacks (visual connection):
    Flow 1: BeginPlay → EmitCallback
    Flow 2: CustomCallback → PrintMessage
    
    Callback edge connects:
      CustomCallback.listen_callback (outlet) → EmitCallback.edge_callback (inlet)
    
    Event name (CustomCallback's node_id) propagates through the edge automatically
    via the pipe mechanism.
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_core.nodes.custom_callback import CustomCallbackNode
    from haybale_core.nodes.emit_callback import EmitCallbackNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='callback_edge_example',
        name='Callback Edge-Based Example'
    )
    
    # Flow 1: Emitter flow
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    emit_callback = graph.create_node_wrapper(
        EmitCallbackNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Leave mode_switch=False (default) for edge-based mode
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        emit_callback.node_id, 'execute'
    )
    
    # Flow 2: Listener flow
    callback_listener = graph.create_node_wrapper(
        CustomCallbackNode.class_identity.registry_key,
        position=(100, 300)
    )
    
    # Leave mode_switch=False (default) for edge-based mode
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 300)
    )
    
    graph.create_edge_wrapper(
        callback_listener.node_id, 'triggered',
        print_msg.node_id, 'exec'
    )
    
    # KEY: Create callback edge!
    # This connects the flows visually and propagates event name automatically
    print("\nEdge-based mode: Creating callback edge...")
    callback_edge = graph.create_edge_wrapper(
        callback_listener.node_id, 'listen_callback',  # Source: listener's outlet
        emit_callback.node_id, 'edge_callback'  # Target: emitter's inlet
    )
    
    graph.force_validation()
    
    print(f"Created callback edge: {callback_edge.edge_id}")
    print(f"  Event name will propagate: {callback_listener.node_id}")
    print(f"  From: CustomCallback.listen_callback → EmitCallback.edge_callback")
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph (Edge-Based Callbacks) ===")
    interpreter.load_graph(graph)
    
    # Show callback topology
    stats = interpreter.get_statistics()
    print(f"\nCallback Topology:")
    print(f"  Total callback edges: {stats['assembly']['callback_edges']}")
    
    topology = stats.get('callback_topology', {})
    print(f"  Emitters: {topology.get('emitters', 0)}")
    print(f"  Listeners: {topology.get('listeners', 0)}")
    
    if topology.get('connections'):
        print(f"\n  Connections (listener → emitter):")
        for source, targets in topology['connections'].items():
            print(f"    {source} → {targets}")
    
    print(f"\nCallback Manager Statistics:")
    for cb_info in stats['callbacks']['callbacks']:
        print(f"  '{cb_info['event_name']}': {cb_info['listener_count']} listeners")
    
    print("\n=== Dispatching BEGIN_PLAY Event ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    # Wait a bit for callback to trigger
    import time
    time.sleep(0.5)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 5: External Events
# ==============================================================================

def example_external_events():
    """
    Example with external events (e.g., keyboard input)
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='external_event_example',
        name='External Event Example'
    )
    
    # Create key press listener
    # (This would be a KeyPressedNode in real implementation)
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        print_msg.node_id, 'exec'
    )
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    # Simulate external events
    print("\n=== Simulating External Events ===")
    
    # Dispatch keyboard event
    interpreter.dispatch_external_event(
        category='input',
        name='key_pressed',
        payload={'key': 'Space', 'modifiers': []}
    )
    
    # Dispatch network event
    interpreter.dispatch_external_event(
        category='network',
        name='message_received',
        payload={'from': 'server', 'data': 'Hello!'}
    )
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("HAYWIRE ASSEMBLY & EXECUTION EXAMPLES")
    print("=" * 70)
    
    # Setup library system (REQUIRED before creating graphs/nodes)
    print("\nInitializing library system...")
    library_service = setup_library_system()
    print("Library system initialized.\n")
    
    try:
        # Run examples
        print("\n" + "=" * 70)
        print("EXAMPLE 1: Simple Flow with Data Flow")
        print("=" * 70)
        example_simple_flow()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 2: Sequence Flow")
        print("=" * 70)
        example_sequence_flow()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 3: Callback System - String-Based (Dynamic)")
        print("=" * 70)
        example_callback_string_based()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 4: Callback System - Edge-Based (Visual)")
        print("=" * 70)
        example_callback_edge_based()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 5: External Events")
        print("=" * 70)
        example_external_events()
        
        print("\n\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETE")
        print("=" * 70)
    
    finally:
        # Cleanup
        print("\nCleaning up library system...")
        cleanup_library_system(library_service)
        print("Done.")