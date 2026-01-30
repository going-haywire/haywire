"""
Integration tests for Interpreter with full library system.

These tests require libraries to be loaded and are slower.
"""

import pytest
from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph
from haywire.core.di.config import LibrarySystemService


@pytest.mark.integration
@pytest.mark.slow
class TestInterpreter:
    """Test Interpreter with real nodes from libraries."""

    def _create_simple_graph(self, graph: BaseGraph) -> BaseGraph:
        """
        Create a simple graph: BeginPlay → PrintMessage
        
        Args:
            graph: The graph to populate
            
        Returns:
            The populated graph
        """
        from haybale_core.nodes.begin_play import BeginPlayNode
        from haybale_testing.nodes.testbed.print_node import PrintMessageNode

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
        
        return graph

    def _create_graph_with_math(self, graph: BaseGraph) -> BaseGraph:
        """
        Create graph: BeginPlay → PrintMessage with MathOP data flow
        
        Args:
            graph: The graph to populate
            
        Returns:
            The populated graph
        """
        from haybale_core.nodes.begin_play import BeginPlayNode
        from haybale_testing.nodes.testbed.print_node import PrintMessageNode
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

    def test_simple_flow_execution(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test simple flow: BeginPlay → PrintMessage"""
        graph = self._create_simple_graph(graph_with_library_system)

        # Test: Verify graph structure
        assert len(graph.node_wrappers) == 2
        assert len(graph.list_edge_wrappers()) == 1

        # Test: Create and load interpreter
        interpreter = Interpreter()
        assert interpreter is not None

        # Test: Load and assemble graph
        interpreter.load_graph(graph)
        assert interpreter.current_graph == graph

        # Test: Verify assembly statistics
        stats = interpreter.get_statistics()
        assert stats['current_graph'] == graph.graph_id
        assert stats['assembly']['total_flows'] == 1
        assert len(stats['assembly']['flows']) == 1

        flow_info = stats['assembly']['flows'][0]
        assert 'begin_play' in flow_info['event_type']
        assert flow_info['node_count'] == 2

        # Test: Dispatch event
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1

        # Test: Wait for completion
        interpreter.wait_all(timeout=5.0)

        # Test: Verify schedulers
        assert len(stats['schedulers']) == 1
        scheduler_info = stats['schedulers'][0]
        assert scheduler_info['subscription'] is not None

        # Cleanup
        interpreter.shutdown()
        assert interpreter.current_graph is None

        # Test: Library system integration
        assert library_system is not None
        node_registry = library_system.get_node_registry()
        assert node_registry is not None

        available_nodes = node_registry.list_names()
        assert isinstance(available_nodes, list)
        assert len(available_nodes) > 0

    def test_callback_flow_execution(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test callback flow: BeginPlay → EmitCallback, CustomCallback → Print"""
        from haybale_core.nodes.begin_play import BeginPlayNode
        from haybale_core.nodes.emit_callback import EmitCallbackNode
        from haybale_core.nodes.custom_callback import CustomCallbackNode
        from haybale_testing.nodes.testbed.print_node import PrintMessageNode

        graph = graph_with_library_system

        # Flow 1: BeginPlay → EmitCallback
        begin_play = graph.create_node_wrapper(
            BeginPlayNode.class_identity.registry_key,
            position=(100, 100)
        )
        
        emit_callback = graph.create_node_wrapper(
            EmitCallbackNode.class_identity.registry_key,
            position=(300, 100)
        )
        
        # Set mode to use custom callback name and set the callback name
        emit_callback.node.ports['mode_switch'].set_value(True)
        emit_callback.node.ports['custom_callback_name'].set_value('test_callback')

        graph.create_edge_wrapper(
            begin_play.node_id, 'exec',
            emit_callback.node_id, 'execute'
        )

        # Flow 2: CustomCallback → PrintMessage
        custom_callback = graph.create_node_wrapper(
            CustomCallbackNode.class_identity.registry_key,
            position=(100, 300)
        )
        
        # Set mode to use custom callback name and set the listener name
        custom_callback.node.ports['mode_switch'].set_value(True)
        custom_callback.node.ports['custom_callback_name'].set_value('test_callback')
        
        print_msg = graph.create_node_wrapper(
            PrintMessageNode.class_identity.registry_key,
            position=(300, 300)
        )
        
        print_msg.node.ports['message'].set_value('Callback received!')

        graph.create_edge_wrapper(
            custom_callback.node_id, 'triggered',
            print_msg.node_id, 'exec'
        )

        # Test: Verify graph structure
        assert len(graph.node_wrappers) == 4
        assert len(graph.edge_wrappers) == 2

        # Test: Load graph
        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Verify assembly
        stats = interpreter.get_statistics()
        assert stats['assembly']['total_flows'] == 2
        
        # Test: Verify callback registration
        callback_stats = stats['callbacks']
        assert callback_stats['total_callbacks'] >= 1

        # Test: Dispatch BEGIN_PLAY
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1

        # Wait for execution (including callback trigger)
        interpreter.wait_all(timeout=5.0)

        # Cleanup
        interpreter.shutdown()

    def test_multiple_event_dispatches(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test multiple event dispatches to the same flow"""
        graph = self._create_simple_graph(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Dispatch event multiple times
        triggered1 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered1 == 1
        
        triggered2 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered2 == 1
        
        triggered3 = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered3 == 1

        # Test: Wait for all executions
        interpreter.wait_all(timeout=5.0)

        # Test: Verify scheduler state
        stats = interpreter.get_statistics()
        assert len(stats['schedulers']) == 1

        interpreter.shutdown()

    def test_interpreter_reload_graph(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test reloading a different graph into the interpreter"""
        from haybale_core.nodes.begin_play import BeginPlayNode
        from haybale_testing.nodes.testbed.print_node import PrintMessageNode

        # Create first graph
        graph1 = self._create_simple_graph(graph_with_library_system)

        # Create second graph
        graph2 = BaseGraph(
            graph_id='test_graph_2',
            name='Test Graph 2'
        )
        graph2 = self._create_simple_graph(graph2)

        # Test: Load first graph
        interpreter = Interpreter()
        interpreter.load_graph(graph1)
        
        stats1 = interpreter.get_statistics()
        assert stats1['current_graph'] == graph1.graph_id
        assert stats1['assembly']['total_flows'] == 1

        # Test: Reload with second graph
        interpreter.load_graph(graph2)
        
        stats2 = interpreter.get_statistics()
        assert stats2['current_graph'] == graph2.graph_id
        assert stats2['assembly']['total_flows'] == 1

        # Test: Execute second graph
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 1
        
        interpreter.wait_all(timeout=5.0)
        interpreter.shutdown()

    def test_empty_graph_handling(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test interpreter with an empty graph"""
        graph = graph_with_library_system

        # Test: Load empty graph
        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Verify no flows assembled
        stats = interpreter.get_statistics()
        assert stats['current_graph'] == graph.graph_id
        assert stats['assembly']['total_flows'] == 0

        # Test: Dispatch event to empty graph
        triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        assert triggered == 0

        interpreter.shutdown()

    def test_interpreter_statistics(
        self,
        graph_with_library_system: BaseGraph,
        library_system: LibrarySystemService
    ):
        """Test interpreter statistics reporting"""

        graph = self._create_graph_with_math(graph_with_library_system)

        interpreter = Interpreter()
        interpreter.load_graph(graph)

        # Test: Statistics structure
        stats = interpreter.get_statistics()
        
        assert 'current_graph' in stats
        assert 'total_subscriptions' in stats
        assert 'assembly' in stats
        assert 'callbacks' in stats
        assert 'schedulers' in stats

        # Test: Assembly stats
        assembly_stats = stats['assembly']
        assert 'total_flows' in assembly_stats
        assert 'flows' in assembly_stats
        assert assembly_stats['total_flows'] > 0

        # Test: Scheduler stats
        assert isinstance(stats['schedulers'], list)
        assert len(stats['schedulers']) > 0
        
        scheduler = stats['schedulers'][0]
        assert 'flow_id' in scheduler
        assert 'subscription' in scheduler
        assert 'executing' in scheduler
        assert 'queued' in scheduler

        interpreter.shutdown()


