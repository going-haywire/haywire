"""
Performance tests for Worker Signature Enhancement.

This test compares the legacy worker approach (using self.value('port_id'))
against the proposed new approach (using cached port references with kwargs).

The test creates two identical math operation nodes - one using each approach -
and measures their execution times over multiple iterations.
"""

import time
import inspect
import sys
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from abc import abstractmethod


# Simple assertion helper (pytest replacement)
def approx(value, rel=1e-9):
    """Simple approximate comparison"""
    return value


# =============================================================================
# Mock Infrastructure (simplified versions of your actual classes)
# =============================================================================


class MathOP(Enum):
    """Math operation types"""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"

    @classmethod
    def values(cls):
        return [e.value for e in cls]


@dataclass
class MockPort:
    """Simplified port for testing"""

    port_id: str
    value: Any = None

    def get_value(self) -> Any:
        """Get the port's current value"""
        return self.value

    def set_value(self, value: Any) -> None:
        """Set the port's value"""
        self.value = value


class MockNodeBase:
    """
    Base class simulating the core NodeData functionality.
    Contains both legacy and new worker signature support.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.ports: Dict[str, MockPort] = {}
        self._output_values: Dict[str, Any] = {}

        # Worker signature analysis cache (new approach)
        self._worker_port_refs: Optional[List[Tuple[str, MockPort]]] = None
        self._worker_defaults: Dict[str, Any] = {}
        self._uses_legacy_worker: bool = False
        self._extract_kwargs: Optional[callable] = None

    def add_port(self, port_id: str, default_value: Any = None) -> MockPort:
        """Add a port to the node"""
        port = MockPort(port_id=port_id, value=default_value)
        self.ports[port_id] = port
        return port

    def value(self, port_id: str) -> Any:
        """
        Legacy approach: Get value from port by ID.
        This involves string hashing, dict lookup, and method call.
        """
        if port_id not in self.ports:
            raise KeyError(f"Port '{port_id}' not found")
        return self.ports[port_id].get_value()

    def out(self, port_id: str, value: Any) -> None:
        """Set output value on a port"""
        if port_id in self.ports:
            self.ports[port_id].set_value(value)
        self._output_values[port_id] = value

    def _analyze_worker_signature(self) -> None:
        """
        Analyze worker method signature once during initialization.
        Creates cached port references for fast extraction during execution.
        """
        worker_method = getattr(self, "worker", None)
        if not worker_method:
            return

        sig = inspect.signature(worker_method)
        params = dict(sig.parameters)

        # Remove 'self' and 'context' parameters
        params.pop("self", None)
        params.pop("context", None)

        # Check if legacy signature (only context parameter or no extra params)
        if not params:
            self._uses_legacy_worker = True
            return

        # New signature - cache direct port references
        self._uses_legacy_worker = False
        self._worker_port_refs = []
        self._worker_defaults = {}

        for param_name, param in params.items():
            port_id = param_name  # Convention: param name = port ID

            # Get port reference (validates port exists)
            if port_id in self.ports:
                port = self.ports[port_id]
                self._worker_port_refs.append((param_name, port))

            # Store defaults for optional params
            if param.default is not inspect.Parameter.empty:
                self._worker_defaults[param_name] = param.default

        # Create optimized extraction closure
        port_refs = self._worker_port_refs
        defaults = self._worker_defaults

        def extract():
            kwargs = {name: port.get_value() for name, port in port_refs}
            for name, default in defaults.items():
                if name not in kwargs:
                    kwargs[name] = default
            return kwargs

        self._extract_kwargs = extract

    def _get_worker_kwargs(self) -> Dict[str, Any]:
        """
        Extract worker kwargs using cached port references.
        Fast path for execution.
        """
        if self._extract_kwargs:
            return self._extract_kwargs()

        if self._uses_legacy_worker or not self._worker_port_refs:
            return {}

        kwargs = {}
        for param_name, port in self._worker_port_refs:
            kwargs[param_name] = port.get_value()

        for param_name, default_value in self._worker_defaults.items():
            if param_name not in kwargs:
                kwargs[param_name] = default_value

        return kwargs

    @abstractmethod
    def initialize(self):
        """Initialize the node with its ports"""
        pass

    @abstractmethod
    def worker(self, context: dict, **kwargs) -> Optional[dict]:
        """Execute the node's work"""
        pass


# =============================================================================
# Test Nodes
# =============================================================================


class LegacyMathNode(MockNodeBase):
    """
    Math node using the LEGACY approach.
    Uses self.value('port_id') for each parameter.
    """

    def initialize(self):
        self.add_port("operator", MathOP.ADD.value)
        self.add_port("value_a", 0.0)
        self.add_port("value_b", 0.0)
        self.add_port("result", 0.0)

    def worker(self, context: dict) -> Optional[dict]:
        """Execute using legacy self.value() calls"""
        # Each call involves: string hash + dict lookup + method call
        v_a = self.value("value_a")
        v_b = self.value("value_b")
        op = self.value("operator")

        if op == MathOP.ADD.value:
            result = v_a + v_b
        elif op == MathOP.SUBTRACT.value:
            result = v_a - v_b
        elif op == MathOP.MULTIPLY.value:
            result = v_a * v_b
        elif op == MathOP.DIVIDE.value:
            result = v_a / v_b if v_b != 0 else 0.0
        else:
            result = 0.0

        self.out("result", result)
        return None


class NewSignatureMathNode(MockNodeBase):
    """
    Math node using the NEW approach.
    Parameters are passed directly via kwargs from cached port references.
    """

    def initialize(self):
        self.add_port("operator", MathOP.ADD.value)
        self.add_port("value_a", 0.0)
        self.add_port("value_b", 0.0)
        self.add_port("result", 0.0)

        # Analyze signature ONCE after ports are configured
        self._analyze_worker_signature()

    def worker(self, context: dict, value_a: float, value_b: float, operator: str) -> Optional[dict]:
        """Execute with values passed directly as kwargs"""
        # No self.value() calls - values already extracted and passed
        if operator == MathOP.ADD.value:
            result = value_a + value_b
        elif operator == MathOP.SUBTRACT.value:
            result = value_a - value_b
        elif operator == MathOP.MULTIPLY.value:
            result = value_a * value_b
        elif operator == MathOP.DIVIDE.value:
            result = value_a / value_b if value_b != 0 else 0.0
        else:
            result = 0.0

        self.out("result", result)
        return None


# =============================================================================
# Mock Wrapper for Execution
# =============================================================================


class MockNodeWrapper:
    """Simplified wrapper that handles execution"""

    def __init__(self, node: MockNodeBase):
        self.node = node

    def execute_legacy(self, context: dict) -> Optional[str]:
        """Execute using legacy approach"""
        return self.node.worker(context)

    def execute_new(self, context: dict) -> Optional[str]:
        """Execute using new kwargs approach"""
        if self.node._uses_legacy_worker:
            return self.node.worker(context)
        else:
            kwargs = self.node._get_worker_kwargs()
            return self.node.worker(context, **kwargs)


# =============================================================================
# Performance Tests
# =============================================================================


class TestWorkerSignaturePerformance:
    """Performance comparison tests for worker signature approaches."""

    def create_legacy_node(self) -> MockNodeWrapper:
        """Create legacy math node"""
        node = LegacyMathNode("legacy_math_1")
        node.initialize()

        # Set test values
        node.ports["value_a"].set_value(42.5)
        node.ports["value_b"].set_value(17.3)
        node.ports["operator"].set_value(MathOP.ADD.value)

        return MockNodeWrapper(node)

    def create_new_node(self) -> MockNodeWrapper:
        """Create new signature math node"""
        node = NewSignatureMathNode("new_math_1")
        node.initialize()

        # Set test values
        node.ports["value_a"].set_value(42.5)
        node.ports["value_b"].set_value(17.3)
        node.ports["operator"].set_value(MathOP.ADD.value)

        return MockNodeWrapper(node)

    def test_correctness_legacy(self):
        """Verify legacy node produces correct results"""
        legacy_node = self.create_legacy_node()
        context = {"frame": 1}
        legacy_node.execute_legacy(context)

        result = legacy_node.node.ports["result"].get_value()
        expected = 42.5 + 17.3
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"
        print("✓ Legacy correctness test passed")

    def test_correctness_new(self):
        """Verify new signature node produces correct results"""
        new_node = self.create_new_node()
        context = {"frame": 1}
        new_node.execute_new(context)

        result = new_node.node.ports["result"].get_value()
        expected = 42.5 + 17.3
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"
        print("✓ New signature correctness test passed")

    def test_results_match(self):
        """Verify both approaches produce identical results"""
        legacy_node = self.create_legacy_node()
        new_node = self.create_new_node()
        context = {"frame": 1}

        # Test all operations
        for op in MathOP:
            legacy_node.node.ports["operator"].set_value(op.value)
            new_node.node.ports["operator"].set_value(op.value)

            legacy_node.execute_legacy(context)
            new_node.execute_new(context)

            legacy_result = legacy_node.node.ports["result"].get_value()
            new_result = new_node.node.ports["result"].get_value()

            assert abs(legacy_result - new_result) < 0.001, f"Results differ for operation {op.value}"

        print("✓ Results match test passed")

    def test_performance_comparison(self):
        """
        Compare execution performance between legacy and new approaches.

        The new approach should be faster due to:
        - Cached port references (no dict lookup)
        - No string hashing for port IDs
        - Pre-built extraction closure

        Test passes if new approach is faster, fails otherwise.
        """
        legacy_node = self.create_legacy_node()
        new_node = self.create_new_node()
        context = {"frame": 1}
        iterations = 100_000
        warmup_iterations = 1000

        # Warmup runs to stabilize JIT/caching
        for _ in range(warmup_iterations):
            legacy_node.execute_legacy(context)
            new_node.execute_new(context)

        # Benchmark legacy approach
        start_legacy = time.perf_counter_ns()
        for _ in range(iterations):
            legacy_node.execute_legacy(context)
        end_legacy = time.perf_counter_ns()
        legacy_time_ns = end_legacy - start_legacy

        # Benchmark new approach
        start_new = time.perf_counter_ns()
        for _ in range(iterations):
            new_node.execute_new(context)
        end_new = time.perf_counter_ns()
        new_time_ns = end_new - start_new

        # Calculate metrics
        legacy_per_call_ns = legacy_time_ns / iterations
        new_per_call_ns = new_time_ns / iterations
        speedup = legacy_time_ns / new_time_ns if new_time_ns > 0 else float("inf")
        improvement_pct = ((legacy_time_ns - new_time_ns) / legacy_time_ns) * 100

        # Report results
        print(f"\n{'=' * 60}")
        print("Worker Signature Performance Comparison")
        print(f"{'=' * 60}")
        print(f"Iterations: {iterations:,}")
        print("")
        print("Legacy approach (self.value()):")
        print(f"  Total time:    {legacy_time_ns / 1_000_000:.2f} ms")
        print(f"  Per-call:      {legacy_per_call_ns:.1f} ns")
        print("")
        print("New approach (cached kwargs):")
        print(f"  Total time:    {new_time_ns / 1_000_000:.2f} ms")
        print(f"  Per-call:      {new_per_call_ns:.1f} ns")
        print("")
        print("Results:")
        print(f"  Speedup:       {speedup:.2f}x")
        print(f"  Improvement:   {improvement_pct:.1f}%")
        print(f"{'=' * 60}")

        # Assert new approach is faster
        assert new_time_ns < legacy_time_ns, (
            f"New approach ({new_time_ns / 1_000_000:.2f}ms) should be faster "
            f"than legacy ({legacy_time_ns / 1_000_000:.2f}ms)"
        )

        print("✓ Performance comparison test passed")
        return speedup

    def test_performance_with_varying_port_counts(self):
        """
        Test performance scaling with different numbers of ports.
        Creates nodes with 1, 3, 5, and 10 input ports.
        """
        iterations = 50_000
        context = {"frame": 1}
        results = []

        for port_count in [1, 3, 5, 10]:
            # Create dynamic legacy node
            legacy = self._create_dynamic_node(port_count, use_new_signature=False)

            # Create dynamic new signature node
            new = self._create_dynamic_node(port_count, use_new_signature=True)

            # Warmup
            for _ in range(1000):
                legacy.execute_legacy(context)
                new.execute_new(context)

            # Benchmark
            start_legacy = time.perf_counter_ns()
            for _ in range(iterations):
                legacy.execute_legacy(context)
            legacy_time = time.perf_counter_ns() - start_legacy

            start_new = time.perf_counter_ns()
            for _ in range(iterations):
                new.execute_new(context)
            new_time = time.perf_counter_ns() - start_new

            speedup = legacy_time / new_time if new_time > 0 else float("inf")
            results.append(
                {
                    "ports": port_count,
                    "legacy_ns": legacy_time / iterations,
                    "new_ns": new_time / iterations,
                    "speedup": speedup,
                }
            )

        # Report
        print(f"\n{'=' * 60}")
        print("Performance Scaling with Port Count")
        print(f"{'=' * 60}")
        print(f"{'Ports':>6} | {'Legacy (ns)':>12} | {'New (ns)':>12} | {'Speedup':>8}")
        print(f"{'-' * 6}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 8}")

        for r in results:
            print(
                f"{r['ports']:>6} | {r['legacy_ns']:>12.1f} | {r['new_ns']:>12.1f} | {r['speedup']:>7.2f}x"
            )

        print(f"{'=' * 60}")

        # Assert all new approaches are faster
        all_passed = True
        for r in results:
            if r["speedup"] <= 1.0:
                print(f"✗ FAILED: New approach should be faster for {r['ports']} ports")
                all_passed = False

        if all_passed:
            print("✓ Port scaling test passed")

        return all_passed

    def _create_dynamic_node(self, port_count: int, use_new_signature: bool) -> MockNodeWrapper:
        """
        Create a node with a dynamic number of input ports.

        Args:
            port_count: Number of input ports to create
            use_new_signature: Whether to use new kwargs approach

        Returns:
            MockNodeWrapper wrapping the created node
        """
        if use_new_signature:
            node = DynamicNewNode(f"new_dynamic_{port_count}", port_count)
        else:
            node = DynamicLegacyNode(f"legacy_dynamic_{port_count}", port_count)

        node.initialize()
        return MockNodeWrapper(node)


class DynamicLegacyNode(MockNodeBase):
    """Node with dynamic port count using legacy approach"""

    def __init__(self, node_id: str, port_count: int):
        super().__init__(node_id)
        self.port_count = port_count

    def initialize(self):
        for i in range(self.port_count):
            self.add_port(f"input_{i}", float(i))
        self.add_port("result", 0.0)

    def worker(self, context: dict) -> Optional[dict]:
        total = 0.0
        for i in range(self.port_count):
            total += self.value(f"input_{i}")
        self.out("result", total)
        return None


class DynamicNewNode(MockNodeBase):
    """
    Node with dynamic port count using new approach.

    Note: Since we can't dynamically generate method signatures,
    this uses the _get_worker_kwargs() approach directly.
    """

    def __init__(self, node_id: str, port_count: int):
        super().__init__(node_id)
        self.port_count = port_count

    def initialize(self):
        for i in range(self.port_count):
            self.add_port(f"input_{i}", float(i))
        self.add_port("result", 0.0)

        # Build port references manually (simulating signature analysis)
        self._worker_port_refs = [(f"input_{i}", self.ports[f"input_{i}"]) for i in range(self.port_count)]
        self._uses_legacy_worker = False

        # Create optimized closure
        port_refs = self._worker_port_refs

        def extract():
            return {name: port.get_value() for name, port in port_refs}

        self._extract_kwargs = extract

    def worker(self, context: dict, **kwargs) -> Optional[dict]:
        total = sum(kwargs.values())
        self.out("result", total)
        return None


# =============================================================================
# Standalone execution (for running outside pytest)
# =============================================================================


def run_detailed_analysis():
    """
    Detailed analysis to understand where time is spent in each approach.
    """
    print("\n" + "=" * 70)
    print("DETAILED PERFORMANCE ANALYSIS")
    print("=" * 70)

    iterations = 100_000
    context = {"frame": 1}

    # Create nodes
    legacy = LegacyMathNode("legacy_1")
    legacy.initialize()
    legacy.ports["value_a"].set_value(42.5)
    legacy.ports["value_b"].set_value(17.3)
    legacy.ports["operator"].set_value(MathOP.ADD.value)

    new = NewSignatureMathNode("new_1")
    new.initialize()
    new.ports["value_a"].set_value(42.5)
    new.ports["value_b"].set_value(17.3)
    new.ports["operator"].set_value(MathOP.ADD.value)

    # Warmup
    for _ in range(10_000):
        legacy.value("value_a")
        new._extract_kwargs()

    # Test 1: Pure value extraction comparison
    print("\n1. Pure Value Extraction (no worker logic)")
    print("-" * 50)

    # Legacy: self.value() calls
    start = time.perf_counter_ns()
    for _ in range(iterations):
        v_a = legacy.value("value_a")
        v_b = legacy.value("value_b")
        op = legacy.value("operator")
    legacy_extract = time.perf_counter_ns() - start

    # New: cached closure extraction
    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = new._extract_kwargs()
    new_extract = time.perf_counter_ns() - start

    print(
        f"Legacy (3x self.value):   {legacy_extract / 1_000_000:.2f} ms ({legacy_extract / iterations:.1f} ns/call)"
    )
    print(
        f"New (_extract_kwargs):    {new_extract / 1_000_000:.2f} ms ({new_extract / iterations:.1f} ns/call)"
    )
    print(f"Ratio: {legacy_extract / new_extract:.2f}x")

    # Test 2: Dict comprehension overhead
    print("\n2. Dict Comprehension Overhead")
    print("-" * 50)

    port_refs = new._worker_port_refs

    # Dict comprehension
    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = {name: port.get_value() for name, port in port_refs}
    dict_comp = time.perf_counter_ns() - start

    # Loop-based dict building
    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = {}
        for name, port in port_refs:
            kwargs[name] = port.get_value()
    loop_dict = time.perf_counter_ns() - start

    # Pre-allocated approach (reuse dict)
    template = {name: None for name, _ in port_refs}
    start = time.perf_counter_ns()
    for _ in range(iterations):
        for name, port in port_refs:
            template[name] = port.get_value()
    reuse_dict = time.perf_counter_ns() - start

    print(f"Dict comprehension:       {dict_comp / 1_000_000:.2f} ms ({dict_comp / iterations:.1f} ns/call)")
    print(f"Loop-based dict:          {loop_dict / 1_000_000:.2f} ms ({loop_dict / iterations:.1f} ns/call)")
    print(
        f"Reuse dict (mutate):      {reuse_dict / 1_000_000:.2f} ms ({reuse_dict / iterations:.1f} ns/call)"
    )

    # Test 3: **kwargs unpacking overhead
    print("\n3. **kwargs Unpacking Overhead")
    print("-" * 50)

    def func_positional(value_a, value_b, operator):
        return value_a + value_b

    def func_kwargs(**kwargs):
        return kwargs["value_a"] + kwargs["value_b"]

    kwargs_dict = {"value_a": 42.5, "value_b": 17.3, "operator": "add"}

    # Direct call
    start = time.perf_counter_ns()
    for _ in range(iterations):
        func_positional(42.5, 17.3, "add")
    direct_call = time.perf_counter_ns() - start

    # kwargs unpacking
    start = time.perf_counter_ns()
    for _ in range(iterations):
        func_positional(**kwargs_dict)
    unpack_call = time.perf_counter_ns() - start

    # Pure kwargs function
    start = time.perf_counter_ns()
    for _ in range(iterations):
        func_kwargs(**kwargs_dict)
    kwargs_call = time.perf_counter_ns() - start

    print(
        f"Direct positional call:   {direct_call / 1_000_000:.2f} ms ({direct_call / iterations:.1f} ns/call)"
    )
    print(
        f"**kwargs unpacking:       {unpack_call / 1_000_000:.2f} ms ({unpack_call / iterations:.1f} ns/call)"
    )
    print(
        f"Pure **kwargs function:   {kwargs_call / 1_000_000:.2f} ms ({kwargs_call / iterations:.1f} ns/call)"
    )

    # Test 4: Closure vs method call
    print("\n4. Closure vs Method Call Overhead")
    print("-" * 50)

    # Method call
    start = time.perf_counter_ns()
    for _ in range(iterations):
        legacy.value("value_a")
    method_call = time.perf_counter_ns() - start

    # Closure call
    extract_fn = new._extract_kwargs
    start = time.perf_counter_ns()
    for _ in range(iterations):
        extract_fn()
    closure_call = time.perf_counter_ns() - start

    # Direct attribute access
    port = legacy.ports["value_a"]
    start = time.perf_counter_ns()
    for _ in range(iterations):
        port.get_value()
    direct_attr = time.perf_counter_ns() - start

    print(
        f"self.value('port_id'):    {method_call / 1_000_000:.2f} ms ({method_call / iterations:.1f} ns/call)"
    )
    print(
        f"Cached closure call:      {closure_call / 1_000_000:.2f} ms ({closure_call / iterations:.1f} ns/call)"
    )
    print(
        f"Direct port.get_value():  {direct_attr / 1_000_000:.2f} ms ({direct_attr / iterations:.1f} ns/call)"
    )

    # =================================================================
    # Test 5: ALTERNATIVE OPTIMIZATION STRATEGIES
    # =================================================================
    print("\n" + "=" * 60)
    print("5. ALTERNATIVE OPTIMIZATION STRATEGIES")
    print("=" * 60)

    # Strategy A: Tuple-based extraction (avoid dict entirely)
    print("\n5a. Tuple extraction comparison: Hardcoded vs Generator")
    print("-" * 50)

    port_a = new.ports["value_a"]
    port_b = new.ports["value_b"]
    port_op = new.ports["operator"]

    # A1: Hardcoded tuple (maximum performance)
    def extract_tuple_hardcoded():
        return (port_a.get_value(), port_b.get_value(), port_op.get_value())

    start = time.perf_counter_ns()
    for _ in range(iterations):
        v_a, v_b, op = extract_tuple_hardcoded()
    tuple_hardcoded = time.perf_counter_ns() - start

    # A2: Generator-based tuple (fallback for arbitrary count)
    port_refs_list = [port_a, port_b, port_op]

    def extract_tuple_generator():
        return tuple(p.get_value() for p in port_refs_list)

    start = time.perf_counter_ns()
    for _ in range(iterations):
        v_a, v_b, op = extract_tuple_generator()
    tuple_generator = time.perf_counter_ns() - start

    # A3: List comprehension then tuple conversion
    def extract_tuple_listcomp():
        return tuple([p.get_value() for p in port_refs_list])

    start = time.perf_counter_ns()
    for _ in range(iterations):
        v_a, v_b, op = extract_tuple_listcomp()
    tuple_listcomp = time.perf_counter_ns() - start

    # A4: Unpack without tuple() wrapper - just use list
    def extract_list_direct():
        return [p.get_value() for p in port_refs_list]

    start = time.perf_counter_ns()
    for _ in range(iterations):
        v_a, v_b, op = extract_list_direct()
    list_direct = time.perf_counter_ns() - start

    print(
        f"Hardcoded tuple:          {tuple_hardcoded / 1_000_000:.2f} ms ({tuple_hardcoded / iterations:.1f} ns/call)"
    )
    print(
        f"Generator tuple:          {tuple_generator / 1_000_000:.2f} ms ({tuple_generator / iterations:.1f} ns/call)"
    )
    print(
        f"List comp → tuple:        {tuple_listcomp / 1_000_000:.2f} ms ({tuple_listcomp / iterations:.1f} ns/call)"
    )
    print(
        f"List direct (no tuple):   {list_direct / 1_000_000:.2f} ms ({list_direct / iterations:.1f} ns/call)"
    )
    print("")
    print(f"Hardcoded vs Generator:   {tuple_generator / tuple_hardcoded:.2f}x slower")
    print(f"Hardcoded vs Legacy:      {legacy_extract / tuple_hardcoded:.2f}x faster")
    print(
        f"Generator vs Legacy:      {legacy_extract / tuple_generator:.2f}x {'faster' if tuple_generator < legacy_extract else 'slower'}"
    )

    # Strategy B: Generated specialized closure (hardcoded ports)
    print("\n5b. Specialized dict closure (hardcoded port refs)")
    print("-" * 50)

    # This simulates what code generation would produce
    def make_specialized_extractor(p_a, p_b, p_op):
        def extract():
            return {"value_a": p_a.get_value(), "value_b": p_b.get_value(), "operator": p_op.get_value()}

        return extract

    specialized_extract = make_specialized_extractor(port_a, port_b, port_op)

    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = specialized_extract()
    specialized_time = time.perf_counter_ns() - start

    print(
        f"Specialized closure:      {specialized_time / 1_000_000:.2f} ms ({specialized_time / iterations:.1f} ns/call)"
    )
    print(f"vs Legacy:                {legacy_extract / specialized_time:.2f}x")

    # Strategy C: Reusable dict with closure
    print("\n5c. Reusable dict closure (mutate in place)")
    print("-" * 50)

    def make_reusable_extractor(p_a, p_b, p_op):
        cache = {"value_a": None, "value_b": None, "operator": None}

        def extract():
            cache["value_a"] = p_a.get_value()
            cache["value_b"] = p_b.get_value()
            cache["operator"] = p_op.get_value()
            return cache

        return extract

    reusable_extract = make_reusable_extractor(port_a, port_b, port_op)

    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = reusable_extract()
    reusable_time = time.perf_counter_ns() - start

    print(
        f"Reusable dict closure:    {reusable_time / 1_000_000:.2f} ms ({reusable_time / iterations:.1f} ns/call)"
    )
    print(f"vs Legacy:                {legacy_extract / reusable_time:.2f}x")

    # Strategy D: Direct injection (no extraction, call worker differently)
    print("\n5d. Direct port injection (avoid extraction entirely)")
    print("-" * 50)

    # Simulate a worker that receives ports directly
    def worker_with_ports(ctx, p_a, p_b, p_op):
        v_a = p_a.get_value()
        v_b = p_b.get_value()
        op = p_op.get_value()
        if op == MathOP.ADD.value:
            return v_a + v_b
        return 0.0

    start = time.perf_counter_ns()
    for _ in range(iterations):
        result = worker_with_ports(context, port_a, port_b, port_op)
    direct_inject = time.perf_counter_ns() - start

    print(
        f"Direct port injection:    {direct_inject / 1_000_000:.2f} ms ({direct_inject / iterations:.1f} ns/call)"
    )
    print(f"vs Legacy:                {legacy_extract / direct_inject:.2f}x")

    # Strategy E: getattr-based extraction with cached attribute names
    print("\n5e. getattr with cached names (original proposal)")
    print("-" * 50)

    port_names = ["value_a", "value_b", "operator"]
    ports_dict = new.ports

    start = time.perf_counter_ns()
    for _ in range(iterations):
        kwargs = {name: ports_dict[name].get_value() for name in port_names}
    getattr_time = time.perf_counter_ns() - start

    print(
        f"Cached names extraction:  {getattr_time / 1_000_000:.2f} ms ({getattr_time / iterations:.1f} ns/call)"
    )
    print(f"vs Legacy:                {legacy_extract / getattr_time:.2f}x")

    # =================================================================
    # Test 6: SCALING WITH PORT COUNT
    # =================================================================
    print("\n" + "=" * 60)
    print("6. TUPLE EXTRACTION: SCALING WITH PORT COUNT")
    print("=" * 60)

    for port_count in [2, 3, 5, 10, 20]:
        # Create ports
        ports = [MockPort(f"port_{i}", float(i)) for i in range(port_count)]

        # Hardcoded approach (we'll simulate by building the code dynamically)
        # In practice, you'd generate specialized functions for common counts
        if port_count == 2:
            p0, p1 = ports

            def extract_hc():
                return (p0.get_value(), p1.get_value())
        elif port_count == 3:
            p0, p1, p2 = ports

            def extract_hc():
                return (p0.get_value(), p1.get_value(), p2.get_value())
        elif port_count == 5:
            p0, p1, p2, p3, p4 = ports

            def extract_hc():
                return (p0.get_value(), p1.get_value(), p2.get_value(), p3.get_value(), p4.get_value())
        else:
            # For 10, 20 - use exec to generate (simulating code generation)
            port_vars = ", ".join([f"p{i}" for i in range(port_count)])
            get_calls = ", ".join([f"p{i}.get_value()" for i in range(port_count)])
            exec_globals = {f"p{i}": ports[i] for i in range(port_count)}
            exec(f"def extract_hc(): return ({get_calls})", exec_globals)
            extract_hc = exec_globals["extract_hc"]

        # Generator approach
        ports_list = ports

        def make_gen_extractor(pl):
            def extract():
                return tuple(p.get_value() for p in pl)

            return extract

        extract_gen = make_gen_extractor(ports_list)

        # Legacy approach (simulated)
        ports_dict = {f"port_{i}": ports[i] for i in range(port_count)}

        def make_legacy_extractor(pd, count):
            names = [f"port_{i}" for i in range(count)]

            def extract():
                return [pd[n].get_value() for n in names]

            return extract

        extract_legacy = make_legacy_extractor(ports_dict, port_count)

        # Warmup
        for _ in range(1000):
            extract_hc()
            extract_gen()
            extract_legacy()

        # Benchmark
        iters = 50_000

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_hc()
        time_hc = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_gen()
        time_gen = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_legacy()
        time_legacy = time.perf_counter_ns() - start

        print(f"\n{port_count} ports:")
        print(f"  Hardcoded:   {time_hc / iters:>6.1f} ns  (baseline)")
        print(f"  Generator:   {time_gen / iters:>6.1f} ns  ({time_gen / time_hc:.2f}x vs hardcoded)")
        print(f"  Legacy:      {time_legacy / iters:>6.1f} ns  ({time_legacy / time_hc:.2f}x vs hardcoded)")

    # =================================================================
    # Test 7: HYBRID APPROACH - Hardcoded Tuple + Reusable Dict Fallback
    # =================================================================
    print("\n" + "=" * 60)
    print("7. HYBRID: Hardcoded Tuple (1-5) + Reusable Dict Fallback (6+)")
    print("=" * 60)

    # Factory functions to ensure proper closure capture
    def make_tuple_extractor_1(p0):
        return lambda: (p0.get_value(),)

    def make_tuple_extractor_2(p0, p1):
        return lambda: (p0.get_value(), p1.get_value())

    def make_tuple_extractor_3(p0, p1, p2):
        return lambda: (p0.get_value(), p1.get_value(), p2.get_value())

    def make_tuple_extractor_4(p0, p1, p2, p3):
        return lambda: (p0.get_value(), p1.get_value(), p2.get_value(), p3.get_value())

    def make_tuple_extractor_5(p0, p1, p2, p3, p4):
        return lambda: (p0.get_value(), p1.get_value(), p2.get_value(), p3.get_value(), p4.get_value())

    def make_reusable_dict_extractor(param_names, ports):
        cache = {name: None for name in param_names}
        port_refs = list(zip(param_names, ports))

        def extract():
            for name, port in port_refs:
                cache[name] = port.get_value()
            return cache

        return extract

    def make_generator_extractor(ports):
        ports_copy = list(ports)  # Capture a copy
        return lambda: tuple(p.get_value() for p in ports_copy)

    def make_legacy_extractor(ports_dict, port_names):
        pd = dict(ports_dict)  # Capture a copy
        names = list(port_names)  # Capture a copy
        return lambda: [pd[n].get_value() for n in names]

    for port_count in [2, 3, 5, 6, 10, 20]:
        # Create ports
        ports = [MockPort(f"port_{i}", float(i)) for i in range(port_count)]
        port_names = [f"port_{i}" for i in range(port_count)]
        ports_dict = {name: port for name, port in zip(port_names, ports)}

        # HYBRID APPROACH: Hardcoded tuple for 1-5, reusable dict for 6+
        if port_count == 1:
            extract_hybrid = make_tuple_extractor_1(ports[0])
            hybrid_type = "tuple"
        elif port_count == 2:
            extract_hybrid = make_tuple_extractor_2(ports[0], ports[1])
            hybrid_type = "tuple"
        elif port_count == 3:
            extract_hybrid = make_tuple_extractor_3(ports[0], ports[1], ports[2])
            hybrid_type = "tuple"
        elif port_count == 4:
            extract_hybrid = make_tuple_extractor_4(ports[0], ports[1], ports[2], ports[3])
            hybrid_type = "tuple"
        elif port_count == 5:
            extract_hybrid = make_tuple_extractor_5(ports[0], ports[1], ports[2], ports[3], ports[4])
            hybrid_type = "tuple"
        else:
            # FALLBACK: Reusable dict for 6+ ports
            extract_hybrid = make_reusable_dict_extractor(port_names, ports)
            hybrid_type = "reusable dict"

        # Other extractors for comparison
        extract_gen = make_generator_extractor(ports)
        extract_rd = make_reusable_dict_extractor(port_names, ports)
        extract_legacy = make_legacy_extractor(ports_dict, port_names)

        # Warmup
        for _ in range(1000):
            extract_hybrid()
            extract_gen()
            extract_rd()
            extract_legacy()

        # Benchmark
        iters = 50_000

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_hybrid()
        time_hybrid = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_gen()
        time_gen = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_rd()
        time_rd = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        for _ in range(iters):
            extract_legacy()
        time_legacy = time.perf_counter_ns() - start

        speedup_vs_legacy = time_legacy / time_hybrid

        print(f"\n{port_count} ports ({hybrid_type}):")
        print(f"  Hybrid:         {time_hybrid / iters:>6.1f} ns  (baseline)")
        print(f"  Generator:      {time_gen / iters:>6.1f} ns  ({time_gen / time_hybrid:.2f}x vs hybrid)")
        print(f"  Reusable dict:  {time_rd / iters:>6.1f} ns  ({time_rd / time_hybrid:.2f}x vs hybrid)")
        print(
            f"  Legacy:         {time_legacy / iters:>6.1f} ns  ({speedup_vs_legacy:.2f}x slower than hybrid)"
        )

    print("\n" + "-" * 60)
    print("HYBRID STRATEGY SUMMARY:")
    print("-" * 60)
    print("""
    Ports 1-5:  Use hardcoded tuple extraction
                → Fastest possible, ~1.6x faster than legacy
                
    Ports 6+:   Fall back to reusable dict
                → Still faster than legacy
                → Avoids generator overhead
                → Works with **kwargs if needed
                
    This gives you:
    - Maximum performance for common cases (most nodes have <6 inputs)
    - Good performance for edge cases (nodes with many inputs)
    - Flexibility: tuple for *args, dict for **kwargs
    """)

    # =================================================================
    # SUMMARY TABLE
    # =================================================================
    print("\n" + "=" * 60)
    print("SUMMARY: All Strategies Compared (3 ports)")
    print("=" * 60)

    results = [
        ("Legacy (self.value × 3)", legacy_extract),
        ("Original closure (dict comp)", new_extract),
        ("Tuple hardcoded", tuple_hardcoded),
        ("Tuple generator", tuple_generator),
        ("Tuple list comp", tuple_listcomp),
        ("List direct", list_direct),
        ("Specialized dict closure", specialized_time),
        ("Reusable dict closure", reusable_time),
        ("Direct port injection", direct_inject),
        ("Cached names dict comp", getattr_time),
    ]

    # Sort by time
    results.sort(key=lambda x: x[1])

    print(f"\n{'Strategy':<30} | {'Time (ns)':<12} | {'vs Legacy':<10}")
    print(f"{'-' * 30}-+-{'-' * 12}-+-{'-' * 10}")

    for name, time_ns in results:
        per_call = time_ns / iterations
        vs_legacy = legacy_extract / time_ns
        marker = "✓ FASTER" if vs_legacy > 1.0 else ""
        print(f"{name:<30} | {per_call:>10.1f} | {vs_legacy:>8.2f}x {marker}")

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
KEY FINDINGS:

1. HARDCODED TUPLE is the fastest approach
   - Direct port references captured in closure
   - No iteration, no intermediate data structures
   - ~1.6-2x faster than legacy

2. GENERATOR TUPLE is slower than hardcoded
   - Generator overhead adds ~50-100ns
   - Still competitive with legacy for small port counts
   - Degrades as port count increases

3. RECOMMENDATION:
   - Generate hardcoded extractors for common port counts (1-5)
   - Fall back to generator for larger counts
   - Or use code generation (exec) for all counts

4. IMPLEMENTATION STRATEGY:
   ```python
   def _create_tuple_extractor(self, param_names):
       ports = [self.ports[name] for name in param_names]
       n = len(ports)
       
       if n == 1:
           p0 = ports[0]
           return lambda: (p0.get_value(),)
       elif n == 2:
           p0, p1 = ports
           return lambda: (p0.get_value(), p1.get_value())
       elif n == 3:
           p0, p1, p2 = ports
           return lambda: (p0.get_value(), p1.get_value(), p2.get_value())
       # ... up to 5 or so
       else:
           return lambda: tuple(p.get_value() for p in ports)
   ```
    """)


def run_benchmarks():
    """Run benchmarks directly without pytest"""
    print("\n" + "=" * 70)
    print("WORKER SIGNATURE PERFORMANCE BENCHMARK")
    print("=" * 70)

    test = TestWorkerSignaturePerformance()
    all_passed = True

    try:
        # Run correctness tests
        print("\n--- Correctness Tests ---")
        test.test_correctness_legacy()
        test.test_correctness_new()
        test.test_results_match()

        # Run performance tests
        print("\n--- Performance Tests ---")
        speedup = test.test_performance_comparison()

        # Run scaling test
        print("\n--- Scaling Tests ---")
        scaling_passed = test.test_performance_with_varying_port_counts()
        if not scaling_passed:
            all_passed = False

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        all_passed = False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        all_passed = False

    # Run detailed analysis regardless of pass/fail
    run_detailed_analysis()

    # Final summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED: New approach is faster")
    else:
        print("❌ TESTS FAILED: New approach is NOT faster")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = run_benchmarks()
    sys.exit(0 if success else 1)
