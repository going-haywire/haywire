from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType
from haywire.ui.console_bridge import console_print

from ..types.specs import EXEC, FLOAT


@node(
    registry_id='tick',
    label='Tick',
    description='Triggered periodically (every frame/interval)',
    menu='event/runtime',
    search_tags=['frame', 'update', 'loop', 'event'],
    node_type=NodeType.EVENT,
)
class TickNode(BaseNode):
    """
    Triggered periodically (every frame/interval).
    
    Config:
        interval: Target time between ticks (seconds)
    
    Outputs:
        exec: Control flow
        delta_time: Time since last tick
    """
        
    def init(self):
        from haywire.core.data.enums import FlowType
               
        # Control output
        self.add(EXEC.as_outlet('exec', label='Execute'))
        
        # Data output
        self.add(FLOAT.as_outlet('delta_time', label='Delta Time'))
    
    def on_init(self):
        self.event_subscription = SystemEvent(SystemEventType.TICK)

    def worker(self, context: ExecutionContext) -> str | None:   
        delta = context.trigger.payload.get('delta_time', 0.016)
        self.out('delta_time', delta)        
        return 'exec'

    def worker_perftest(self, context: ExecutionContext) -> str | None:
        import time
        
        delta = context.trigger.payload.get('delta_time', 0.016)
        
        # Profile the out() call in detail
        port = self.ports.get('delta_time')
        
        t0 = time.perf_counter_ns()
        # Direct data set - bypass everything
        port._data._value = delta
        t1 = time.perf_counter_ns()
        
        # Now with dirty flag
        port._data._value = delta
        port._data.is_dirty = True
        t2 = time.perf_counter_ns()
        
        # With observer check
        port._data._value = delta
        port._data.is_dirty = True
        has_obs = port._data.on_changed.has_observers()
        t3 = time.perf_counter_ns()
        
        # Full set_value on _data
        port._data.set_value(delta)
        t4 = time.perf_counter_ns()
        
        # Full port.set_value
        port.set_value(delta)
        t5 = time.perf_counter_ns()

        self.out('delta_time', delta)

        t6 = time.perf_counter_ns()
        

        # Accumulate
        if not hasattr(self, '_detail_times'):
            self._detail_times = {
                'raw_assign': [], 
                'with_dirty': [], 
                'with_observer_check': [],
                'data_set_value': [], 
                'port_set_value': [],
                'out_call': []
            }
        
        self._detail_times['raw_assign'].append(t1 - t0)
        self._detail_times['with_dirty'].append(t2 - t1)
        self._detail_times['with_observer_check'].append(t3 - t2)
        self._detail_times['data_set_value'].append(t4 - t3)
        self._detail_times['port_set_value'].append(t5 - t4)
        self._detail_times['out_call'].append(t6 - t5)
        
        return 'exec'

    def on_shutdown_perftest(self, context):
        if hasattr(self, '_detail_times'):
            console_print(f"\nTick out() breakdown over {len(self._detail_times['raw_assign'])} calls:")
            for name, times in self._detail_times.items():
                avg = sum(times) / len(times) if times else 0
                console_print(f"  {name}: {avg:.0f} ns")

            