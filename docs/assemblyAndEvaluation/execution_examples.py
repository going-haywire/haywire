"""
Haywire Assembly and Execution System - Complete Example

This file demonstrates the complete assembly and execution pipeline.
"""

from haywire.core.graph.base import BaseGraph
from haywire.core.execution import Interpreter
from haywire.core.execution.event_source import SystemEventType
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node


# ==============================================================================
# EXAMPLE 1: Simple Flow with Event Node
# ==============================================================================

@node(
    registry_id='print_message',
    label='Print Message',
    menu='examples/simple'
)
class PrintMessageNode(BaseNode):
    """Simple control node that prints a message"""
    
    def initialize(self):
        from haybale_core.types.specs import EXEC, STRING
        
        # Control flow
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        
        # Data input
        self.add(STRING.as_inlet('message', default='Hello, World!'))
    
    def worker(self, context):
        message = self.value('message')
        print(f"[PrintMessage] {message}")
        return {'next_outlet': 'done'}


def example_simple_flow():
    """
    Example of a simple flow: BeginPlay → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='simple_example',
        name='Simple Flow Example'
    )
    
    # Create nodes
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.__registry_key__,
        position=(100, 100)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.__registry_key__,
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
# EXAMPLE 2: Flow with Data Nodes
# ==============================================================================

@node(
    registry_id='add_numbers',
    label='Add Numbers',
    menu='examples/math'
)
class AddNumbersNode(BaseNode):
    """Data node that adds two numbers"""
    
    def initialize(self):
        from haybale_core.types.specs import FLOAT
        
        self.add(FLOAT.as_inlet('a', default=5.0))
        self.add(FLOAT.as_inlet('b', default=3.0))
        self.add(FLOAT.as_outlet('result'))
    
    def worker(self, context):
        a = self.value('a')
        b = self.value('b')
        result = a + b
        self.out('result', result)


@node(
    registry_id='print_number',
    label='Print Number',
    menu='examples/simple'
)
class PrintNumberNode(BaseNode):
    """Control node that prints a number"""
    
    def initialize(self):
        from haybale_core.types.specs import EXEC, FLOAT
        
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        self.add(FLOAT.as_inlet('value', default=0.0))
    
    def worker(self, context):
        value = self.value('value')
        print(f"[PrintNumber] Value: {value}")
        return {'next_outlet': 'done'}


def example_data_flow():
    """
    Example with data flow: BeginPlay → PrintNumber
                            AddNumbers → PrintNumber.value
    """
    from haywire.core.nodes.events.begin_play import BeginPlayNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='data_flow_example',
        name='Data Flow Example'
    )
    
    # Create nodes
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.__registry_key__,
        position=(100, 100)
    )
    
    add_numbers = graph.create_node_wrapper(
        AddNumbersNode.__registry_key__,
        position=(100, 200)
    )
    
    print_number = graph.create_node_wrapper(
        PrintNumberNode.__registry_key__,
        position=(300, 100)
    )
    
    # Connect control flow: BeginPlay → PrintNumber
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        print_number.node_id, 'exec'
    )
    
    # Connect data flow: AddNumbers.result → PrintNumber.value
    graph.create_edge_wrapper(
        add_numbers.node_id, 'result',
        print_number.node_id, 'value'
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

@node(
    registry_id='emit_callback',
    label='Emit Callback',
    menu='examples/callbacks'
)
class EmitCallbackNode(BaseNode):
    """Control node that emits a callback"""
    
    def initialize(self):
        from haybale_core.types.specs import EXEC, STRING
        
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        self.add(STRING.as_inlet('callback_name', default='my_callback'))
        self.add(STRING.as_inlet('message', default='Hello from callback!'))
    
    def worker(self, context):
        callback_name = self.value('callback_name')
        message = self.value('message')
        
        print(f"[EmitCallback] Emitting '{callback_name}'")
        
        # Emit callback
        context['emit_callback'](callback_name, {'message': message})
        
        return {'next_outlet': 'done'}


def example_callback_flow():
    """
    Example with callbacks:
    Flow 1: BeginPlay → EmitCallback
    Flow 2: CustomCallback → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_core.nodes.custom_callback import CustomCallbackNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='callback_example',
        name='Callback Example'
    )
    
    # Flow 1: Emitter flow
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.__registry_key__,
        position=(100, 100)
    )
    
    emit_callback = graph.create_node_wrapper(
        EmitCallbackNode.__registry_key__,
        position=(300, 100)
    )
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        emit_callback.node_id, 'exec'
    )
    
    # Flow 2: Listener flow
    callback_listener = graph.create_node_wrapper(
        CustomCallbackNode.__registry_key__,
        position=(100, 300)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.__registry_key__,
        position=(300, 300)
    )
    
    graph.create_edge_wrapper(
        callback_listener.node_id, 'triggered',
        print_msg.node_id, 'exec'
    )
    
    # Connect callback payload to message
    graph.create_edge_wrapper(
        callback_listener.node_id, 'payload',
        print_msg.node_id, 'message'
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
    from haywire.core.nodes.events.begin_play import BeginPlayNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='external_event_example',
        name='External Event Example'
    )
    
    # Create key press listener
    # (This would be a KeyPressedNode in real implementation)
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.__registry_key__,
        position=(100, 100)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.__registry_key__,
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
    
    # Run examples
    print("\n\n" + "=" * 70)
    print("EXAMPLE 1: Simple Flow")
    print("=" * 70)
    example_simple_flow()
    
    print("\n\n" + "=" * 70)
    print("EXAMPLE 2: Data Flow")
    print("=" * 70)
    example_data_flow()
    
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
