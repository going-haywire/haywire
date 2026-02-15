"""
ForLoop Node - Usage Examples

Demonstrates various loop patterns using the ForLoop node.
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


# ==============================================================================
# EXAMPLE 1: Basic Forward Loop
# ==============================================================================

def example_basic_loop():
    """
    Basic loop: Count from 0 to 9
    
    Flow:
    BeginPlay → ForLoop(0, 10, 1) → PrintMessage → [loop back]
                     ↓
                 Completed → PrintMessage("Done!")
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_testing.nodes.utils.print_node import PrintMessageNode
    from haybale_core.nodes.for_loop import ForLoopNode
    
    graph = BaseGraph(graph_id='basic_loop', name='Basic Loop Example')
    
    # Create nodes
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    for_loop = graph.create_node_wrapper(
        ForLoopNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Configure loop: 0 to 9
    for_loop.node.ports['start'].set_value(0)
    for_loop.node.ports['end'].set_value(10)
    for_loop.node.ports['step'].set_value(1)
    
    # Print each index
    print_index = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(500, 100)
    )
    
    # Print completion message
    print_done = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(500, 200)
    )

    print_done.node.ports['message'].set_value("Loop started!")
    
    # Connect: BeginPlay → ForLoop
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        for_loop.node_id, 'execute'
    )
    
    # Connect: ForLoop.loop_body → PrintMessage (this loops back!)
    graph.create_edge_wrapper(
        for_loop.node_id, 'loop_body',
        print_index.node_id, 'exec'
    )
    
    # Connect: ForLoop.index → PrintMessage.message
    graph.create_edge_wrapper(
        for_loop.node_id, 'index',
        print_index.node_id, 'message'
    )
    
    # Connect: ForLoop.completed → PrintDone
    graph.create_edge_wrapper(
        for_loop.node_id, 'completed',
        print_done.node_id, 'exec'
    )
    
    # Validate graph
    graph.force_validation()
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    print("\n=== Basic Loop: 0 to 9 ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 2: Backward Loop
# ==============================================================================

def example_backward_loop():
    """
    Backward loop: Count from 10 down to 1
    
    Flow:
    BeginPlay → ForLoop(10, 0, -1) → PrintMessage → [loop back]
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_testing.nodes.utils.print_node import PrintMessageNode
    from haybale_core.nodes.for_loop import ForLoopNode
    
    graph = BaseGraph(graph_id='backward_loop', name='Backward Loop Example')
    
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    for_loop = graph.create_node_wrapper(
        ForLoopNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Configure backward loop: 10 down to 1
    for_loop.node.ports['start'].set_value(10)
    for_loop.node.ports['end'].set_value(0)
    for_loop.node.ports['step'].set_value(-1)
    
    print_index = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(500, 100)
    )
    
    # Connect
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        for_loop.node_id, 'execute'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'loop_body',
        print_index.node_id, 'exec'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'index',
        print_index.node_id, 'message'
    )
    
    # Validate graph
    graph.force_validation()
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    print("\n=== Backward Loop: 10 to 1 ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 3: Loop with Step
# ==============================================================================

def example_loop_with_step():
    """
    Loop with custom step: Count by 2s
    
    Flow:
    BeginPlay → ForLoop(0, 10, 2) → PrintMessage → [loop back]
    
    Outputs: 0, 2, 4, 6, 8
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_testing.nodes.utils.print_node import PrintMessageNode
    from haybale_core.nodes.for_loop import ForLoopNode
    
    graph = BaseGraph(graph_id='step_loop', name='Loop with Step Example')
    
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    for_loop = graph.create_node_wrapper(
        ForLoopNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Configure: count by 2s
    for_loop.node.ports['start'].set_value(0)
    for_loop.node.ports['end'].set_value(10)
    for_loop.node.ports['step'].set_value(2)
    
    print_index = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(500, 100)
    )
    
    # Connect
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        for_loop.node_id, 'execute'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'loop_body',
        print_index.node_id, 'exec'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'index',
        print_index.node_id, 'message'
    )
    
    # Validate graph
    graph.force_validation()
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    print("\n=== Loop with Step: Count by 2s (0, 2, 4, 6, 8) ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# EXAMPLE 4: Loop with Math Operations
# ==============================================================================

def example_loop_with_math():
    """
    Loop with math: Calculate squares
    
    Flow:
    BeginPlay → ForLoop(1, 6) → Multiply(index, index) → PrintMessage → [loop back]
    
    Outputs: 1, 4, 9, 16, 25
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_testing.nodes.utils.print_node import PrintMessageNode
    from haybale_example.nodes.math_op import MathOP
    from haybale_core.nodes.for_loop import ForLoopNode
    
    graph = BaseGraph(graph_id='loop_math', name='Loop with Math Example')
    
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    for_loop = graph.create_node_wrapper(
        ForLoopNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    # Loop 1 to 5
    for_loop.node.ports['start'].set_value(1)
    for_loop.node.ports['end'].set_value(1000)
    for_loop.node.ports['step'].set_value(1)
    
    # Square the index (multiply by itself)
    math_square = graph.create_node_wrapper(
        MathOP.class_identity.registry_key,
        position=(500, 100)
    )
    math_square.node.ports['operator'].set_value('multiply')
    
    print_result = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(700, 100)
    )
    
    # Connect control flow
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        for_loop.node_id, 'execute'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'loop_body',
        print_result.node_id, 'exec'
    )
    
    # Connect data: index → both inputs of multiply
    graph.create_edge_wrapper(
        for_loop.node_id, 'index',
        math_square.node_id, 'value_a'
    )
    
    graph.create_edge_wrapper(
        for_loop.node_id, 'index',
        math_square.node_id, 'value_b'
    )
    
    # Connect result to print
    graph.create_edge_wrapper(
        math_square.node_id, 'result',
        print_result.node_id, 'message'
    )
    
    # Validate graph
    graph.force_validation()
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    print("\n=== Loop with Math: Squares (1, 4, 9, 16, 25) ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    interpreter.wait_all()
    interpreter.shutdown()


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("FOR LOOP NODE EXAMPLES")
    print("=" * 70)
    
    # Setup library system (REQUIRED before creating graphs/nodes)
    print("\nInitializing library system...")
    library_service = setup_library_system()
    print("Library system initialized.\n")
    
    try:
        # Run examples
        print("\n" + "=" * 70)
        print("EXAMPLE 1: Basic Forward Loop (0-9)")
        print("=" * 70)
        example_basic_loop()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 2: Backward Loop (10-1)")
        print("=" * 70)
        example_backward_loop()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 3: Loop with Step (count by 2s)")
        print("=" * 70)
        example_loop_with_step()
        
        print("\n\n" + "=" * 70)
        print("EXAMPLE 4: Loop with Math (calculate squares)")
        print("=" * 70)
        example_loop_with_math()
        
        print("\n\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETE")
        print("=" * 70)
        
        print("\n\nNOTE: For break and nested loop examples, you'll need:")
        print("  - BranchNode (for conditional break)")
        print("  - Comparison nodes (for break condition)")
        print("  These are more complex and require additional node types.")
    
    finally:
        # Cleanup
        print("\nCleaning up library system...")
        cleanup_library_system(library_service)
        print("Done.")