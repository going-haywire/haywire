"""
Performance test for TickNode.worker_perftest

Run from project root:
    python -m pytest tests/perf/test_tick_perf.py -v -s
    
Or directly:
    python tests/perf/test_tick_perf.py
"""

from pathlib import Path
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


# Mock ExecutionContext and Trigger for standalone testing
@dataclass
class MockTrigger:
    payload: Dict[str, Any]
    source_key: str = "test"
    timestamp: float = 0.0


@dataclass  
class MockExecutionContext:
    trigger: MockTrigger
    global_ctx: Optional[Dict] = None
    local_ctx: Optional[Dict] = None
    vm: Optional[Any] = None


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
        workspace_root=str(project_root),
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



def run_performance_test():
    """Run performance tests at different iteration counts."""
    
    # Import here to ensure proper module loading
    from haybale_core.nodes.tick import TickNode
    
    print("=" * 60)
    print("TickNode Performance Test")
    print("=" * 60)
    
    iteration_counts = [1, 10, 100, 1000]
    
    for num_iterations in iteration_counts:
        print(f"\n{'─' * 60}")
        print(f"Testing with {num_iterations} iterations")
        print('─' * 60)
        
        # Create fresh node instance for each test
        node = TickNode("tick_test_node", None)
        node.init()
        node.post_init()
        
        # Create mock context with trigger payload
        trigger = MockTrigger(payload={'delta_time': 0.016})
        context = MockExecutionContext(trigger=trigger)
        
        # Warm-up run (JIT, cache warming, etc.)
        for _ in range(min(10, num_iterations)):
            node.worker_perftest(context)
        
        # Clear timing data after warm-up
        if hasattr(node, '_detail_times'):
            del node._detail_times
        
        # Timed test runs
        overall_start = time.perf_counter_ns()
        
        for _ in range(num_iterations):
            node.worker_perftest(context)
        
        overall_end = time.perf_counter_ns()
        overall_time_ns = overall_end - overall_start
        avg_time_ns = overall_time_ns / num_iterations
        
        # Print results
        print(f"\nOverall: {overall_time_ns:,} ns total, {avg_time_ns:,.0f} ns/call")
        
        # Print detailed breakdown
        if hasattr(node, '_detail_times'):
            print(f"\nBreakdown over {len(node._detail_times['raw_assign'])} calls:")
            for name, times in node._detail_times.items():
                if times:
                    avg = sum(times) / len(times)
                    min_t = min(times)
                    max_t = max(times)
                    print(f"  {name:25s}: avg={avg:8.0f} ns, min={min_t:6.0f} ns, max={max_t:8.0f} ns")
    
    print("\n" + "=" * 60)
    print("Performance Test Complete")
    print("=" * 60)


def run_comparison_test():
    """Compare different output strategies."""
    
    from haybale_core.nodes.tick import TickNode
    
    print("\n" + "=" * 60)
    print("Output Strategy Comparison (1000 iterations)")
    print("=" * 60)
    
    node = TickNode("tick_test_node", None)
    node.init()
    node.post_init()
    
    trigger = MockTrigger(payload={'delta_time': 0.016})
    context = MockExecutionContext(trigger=trigger)
    
    port = node.ports.get('delta_time')
    delta = 0.016
    num_iterations = 1000
    
    strategies = {}
    
    # Strategy 1: Direct assignment only
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        port._data._value = delta
    strategies['1. raw_assign'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Strategy 2: Assignment + dirty flag
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        port._data._value = delta
        port._data.is_dirty = True
    strategies['2. assign+dirty'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Strategy 3: _data.set_value()
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        port._data.set_value(delta)
    strategies['3. _data.set_value()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Strategy 4: port.set_value()
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        port.set_value(delta)
    strategies['4. port.set_value()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Strategy 5: self.out()
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        node.out('delta_time', delta)
    strategies['5. self.out()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Print results
    print(f"\nAverage time per call ({num_iterations} iterations):\n")
    baseline = strategies['1. raw_assign']
    for name, avg_ns in strategies.items():
        overhead = avg_ns - baseline
        multiplier = avg_ns / baseline if baseline > 0 else 0
        print(f"  {name:25s}: {avg_ns:8.0f} ns  (+{overhead:6.0f} ns, {multiplier:.1f}x baseline)")


def run_isolated_component_test():
    """Test individual components in isolation."""
    
    print("\n" + "=" * 60)
    print("Isolated Component Test (10000 iterations)")
    print("=" * 60)
    
    num_iterations = 10000
    results = {}
    
    # Test 1: Dictionary .get() with default
    payload = {'delta_time': 0.016}
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = payload.get('delta_time', 0.016)
    results['dict.get()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 2: Dictionary direct access
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = payload['delta_time']
    results['dict[]'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 3: isinstance check
    value = 0.016
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = isinstance(value, float)
    results['isinstance()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 4: __class__ check
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = value.__class__ is float
    results['__class__ is'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 5: float() coercion on float
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = float(value)
    results['float() on float'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 6: Attribute assignment
    class DummyObj:
        __slots__ = ['value']
    obj = DummyObj()
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        obj.value = value
    results['attr assign (slots)'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 7: Bool check on empty list
    empty_list = []
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = bool(empty_list)
    results['bool([])'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 8: Direct truthiness on empty list
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        if empty_list:
            pass
    results['if []:'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 9: Method call overhead
    class DummyClass:
        def method(self):
            return True
    dummy = DummyClass()
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = dummy.method()
    results['method call'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Test 10: time.perf_counter_ns() itself
    start = time.perf_counter_ns()
    for _ in range(num_iterations):
        _ = time.perf_counter_ns()
    results['perf_counter_ns()'] = (time.perf_counter_ns() - start) / num_iterations
    
    # Print results
    print(f"\nAverage time per operation:\n")
    for name, avg_ns in sorted(results.items(), key=lambda x: x[1]):
        print(f"  {name:25s}: {avg_ns:6.0f} ns")


if __name__ == '__main__':

    # Setup library system (REQUIRED before creating graphs/nodes)
    print("\nInitializing library system...")
    library_service = setup_library_system()
    print("Library system initialized.\n")

    try:
        run_performance_test()
        run_comparison_test()
        run_isolated_component_test()

    finally:
        # Cleanup
        print("\nCleaning up library system...")
        cleanup_library_system(library_service)
        print("Done.")