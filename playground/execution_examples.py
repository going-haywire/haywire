"""
Haywire Assembly and Execution System - Complete Example

This file demonstrates the complete assembly and execution pipeline.

Run this file to see the complete execution flow:
    python execution_examples.py
"""

from pathlib import Path
from haywire.core.graph.base import BaseGraph
from haywire.core.execution import Interpreter
from haywire.core.execution.event_source import SystemEventType


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
    
    # Create nodes
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Connect: BeginPlay.exec → PrintMessage.exec
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        print_msg.node_id, 'exec'
    )
    
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
# EXAMPLE 3: Callback System
# ==============================================================================

def example_callback_flow():
    """
    Example with callbacks:
    Flow 1: BeginPlay → EmitCallback
    Flow 2: CustomCallback → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_core.nodes.custom_callback import CustomCallbackNode
    from haybale_core.nodes.emit_callback import EmitCallbackNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='callback_example',
        name='Callback Example'
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

    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        emit_callback.node_id, 'execute'
    )
    
    # Flow 2: Listener flow
    callback_listener = graph.create_node_wrapper(
        CustomCallbackNode.class_identity.registry_key,
        position=(100, 300)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 300)
    )
    
    graph.create_edge_wrapper(
        callback_listener.node_id, 'triggered',
        print_msg.node_id, 'exec'
    )
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    # Show callback registrations
    stats = interpreter.get_statistics()
    print(f"\nCallback Statistics:")
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
# EXAMPLE 4: External Events
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
        print("EXAMPLE 1: Simple Flow")
        print("=" * 70)
        example_simple_flow()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 2: Sequence Flow")
        print("=" * 70)
        example_sequence_flow()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 3: Callback System")
        print("=" * 70)
        example_callback_flow()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 4: External Events")
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
