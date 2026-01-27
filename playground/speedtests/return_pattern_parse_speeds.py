import timeit
import statistics
from typing import Any, Optional

# Simulate the self.out() method
class MockNode:
    def __init__(self):
        self.output_calls = 0
    
    def out(self, outlet_id: str, value: Any):
        self.output_calls += 1

# Current implementation (nested tuples)
def parse_nested(node: MockNode, result: Any) -> Optional[str]:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    
    next_outlet, outputs = result
    if not outputs:
        return next_outlet
    
    for item in outputs:
        outlet_id, value = item
        node.out(outlet_id, value)
    
    return next_outlet

# Flat implementation with unrolling
def parse_flat_unrolled(node: MockNode, result: Any) -> Optional[str]:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    
    n = len(result)
    if n == 1:
        return result[0]
    
    next_outlet = result[0]
    
    # Unrolled for common cases
    if n == 3:
        node.out(result[1], result[2])
    elif n == 5:
        node.out(result[1], result[2])
        node.out(result[3], result[4])
    elif n == 7:
        node.out(result[1], result[2])
        node.out(result[3], result[4])
        node.out(result[5], result[6])
    else:
        for i in range(1, n, 2):
            node.out(result[i], result[i + 1])
    
    return next_outlet

# Flat implementation without unrolling
def parse_flat_simple(node: MockNode, result: Any) -> Optional[str]:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    
    n = len(result)
    if n == 1:
        return result[0]
    
    next_outlet = result[0]
    for i in range(1, n, 2):
        node.out(result[i], result[i + 1])
    
    return next_outlet

# Smart detection (proposed earlier)
def parse_smart_detect(node: MockNode, result: Any) -> Optional[str]:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    
    next_outlet, outputs = result
    if not outputs:
        return next_outlet
    
    first = outputs[0]
    if isinstance(first, str):
        node.out(first, outputs[1])
    else:
        for outlet_id, value in outputs:
            node.out(outlet_id, value)
    
    return next_outlet

# Test scenarios
test_cases = {
    "none": (None, None),
    "string_only": ('next', 'next'),
    "flow_no_outputs": (('next', ()), ('next',)),
    "single_output_nested": (('next', (('out1', 10),)), ('next', 'out1', 10)),
    "two_outputs_nested": (('next', (('out1', 10), ('out2', 20))), ('next', 'out1', 10, 'out2', 20)),
    "five_outputs_nested": (
        ('next', (('o1', 1), ('o2', 2), ('o3', 3), ('o4', 4), ('o5', 5))),
        ('next', 'o1', 1, 'o2', 2, 'o3', 3, 'o4', 4, 'o5', 5)
    ),
}

# Run benchmarks
results = {}
iterations = 100000

print("=" * 80)
print("PERFORMANCE BENCHMARK: Worker Result Parsing")
print("=" * 80)
print(f"Iterations per test: {iterations:,}")
print()

for test_name, (nested_input, flat_input) in test_cases.items():
    print(f"\n{'=' * 80}")
    print(f"Test: {test_name}")
    print(f"  Nested input: {nested_input}")
    print(f"  Flat input:   {flat_input}")
    print(f"{'=' * 80}")
    
    # Run multiple trials for each implementation
    trials = 5
    
    implementations = [
        ("Nested (current)", parse_nested, nested_input),
        ("Flat unrolled", parse_flat_unrolled, flat_input),
        ("Flat simple", parse_flat_simple, flat_input),
        ("Smart detect", parse_smart_detect, nested_input),
    ]
    
    test_results = {}
    
    for impl_name, impl_func, test_input in implementations:
        times = []
        for _ in range(trials):
            node = MockNode()
            time_taken = timeit.timeit(
                lambda: impl_func(node, test_input),
                number=iterations
            )
            times.append(time_taken)
        
        mean_time = statistics.mean(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        test_results[impl_name] = {
            'mean': mean_time,
            'std': std_dev,
            'per_call_ns': (mean_time / iterations) * 1_000_000_000
        }
    
    # Display results
    baseline = test_results["Nested (current)"]['mean']
    
    for impl_name, metrics in test_results.items():
        speedup = ((baseline - metrics['mean']) / baseline) * 100 if baseline > 0 else 0
        print(f"\n{impl_name:20s}")
        print(f"  Total time:    {metrics['mean']:.6f}s (±{metrics['std']:.6f}s)")
        print(f"  Per call:      {metrics['per_call_ns']:.1f}ns")
        print(f"  vs baseline:   {speedup:+.1f}%")
    
    results[test_name] = test_results

# Summary table
print("\n" + "=" * 80)
print("SUMMARY: Time per call (nanoseconds)")
print("=" * 80)
print(f"{'Test Case':<25} {'Nested':<12} {'Flat-Unroll':<12} {'Flat-Simple':<12} {'Smart':<12}")
print("-" * 80)

for test_name in test_cases.keys():
    row = [test_name[:24]]
    for impl in ["Nested (current)", "Flat unrolled", "Flat simple", "Smart detect"]:
        ns = results[test_name][impl]['per_call_ns']
        row.append(f"{ns:.1f}")
    print(f"{row[0]:<25} {row[1]:<12} {row[2]:<12} {row[3]:<12} {row[4]:<12}")

print("\n" + "=" * 80)
print("PERFORMANCE GAINS (vs Nested baseline)")
print("=" * 80)
print(f"{'Test Case':<25} {'Flat-Unroll':<12} {'Flat-Simple':<12} {'Smart':<12}")
print("-" * 80)

for test_name in test_cases.keys():
    baseline = results[test_name]["Nested (current)"]['per_call_ns']
    row = [test_name[:24]]
    for impl in ["Flat unrolled", "Flat simple", "Smart detect"]:
        ns = results[test_name][impl]['per_call_ns']
        gain = ((baseline - ns) / baseline) * 100
        row.append(f"{gain:+.1f}%")
    print(f"{row[0]:<25} {row[1]:<12} {row[2]:<12} {row[3]:<12}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
Based on the benchmark results:

1. For MAXIMUM PERFORMANCE: Use flat unrolled if gains are >20% consistently
2. For SIMPLICITY + GOOD PERFORMANCE: Use flat simple if gains are >10%
3. For READABILITY: Keep nested if performance difference is <10%
4. Smart detect: Only if you need backward compatibility

The actual recommendation depends on your use case:
- High-frequency node execution (millions/sec): Every nanosecond matters
- Normal usage (thousands/sec): Readability trumps minor performance gains
""")