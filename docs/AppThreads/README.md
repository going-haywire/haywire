

## Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                         MAIN THREAD                                  │
│  - NiceGUI event loop                                               │
│  - ALL UI updates (marshaled via ui.timer)                          │
│  - User interactions                                                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ starts
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  INTERPRETER LOOP THREAD                            │
│  - Dispatches TICK at target FPS                                    │
│  - Backpressure: skips frames if behind                             │
│  - Lock-free FPS tracking (atomic counters)                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ enqueues (with backpressure)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FLOW EXECUTION THREADS (up to 10)                      │
│  - Independent, no shared node state                                │
│  - Minimal locking (just queue operations)                          │
│  - Signals completion for backpressure                              │
└─────────────────────────────────────────────────────────────────────┘


                                │
                                │ on validation requests
                                ▼       
┌─────────────────────────────────────────────────────────────────────┐
│                    VALIDATION TIMER THREAD                          │
│  ValidationManager._validate_batch()                                │
│       │                                                             │
│       ▼                                                             │
│  _notify_subscribers(result)                                        │
│       │                                                             │
│       ▼                                                             │
│  App._on_global_graph_change(result)  ← Just receives, no UI work   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ ui.timer(0, ...)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MAIN THREAD                                  │
│  App._handle_graph_change_ui(result)                                │
│       │                                                             │
│       ├─► canvas_manager._on_validated(result)  ← UI work here      │
│       └─► update_displays_for_session()                             │
└─────────────────────────────────────────────────────────────────────┘


# Preliminary Benchmark Results on the 3th of February, 2026

## Summary Table

| Iterations | Tick | For Loop | Control Switch | Math Op | Print Log | Frame Time | FPS |
|------------|------|----------|----------------|---------|-----------|------------|-----|
| 1 | 39,458 ns | 5,360 ns | 2,413 ns | 5,000 ns | 22,250 ns | 392 μs | 2,551 |
| 10 | 2,033 ns | 2,760 ns | 1,070 ns | 2,809 ns | 4,654 ns | 158 μs | 6,345 |
| 100 | 874 ns | 2,232 ns | 891 ns | 2,636 ns | 2,283 ns | 151 μs | 6,627 |
| 1000 | 727 ns | 2,206 ns | 842 ns | 2,488 ns | 1,953 ns | 118 μs | 8,458 |

## Key Observations

**1. Warm-up effect is dramatic:**
- Tick: 39,458 ns → 727 ns (**54x faster** after warm-up)
- Print Log: 22,250 ns → 1,953 ns (**11x faster**)

**2. Steady-state performance (at 1000 iterations):**
- Control Switch: **842 ns** (simplest node)
- Tick: **727 ns** 
- Print Log: **1,953 ns**
- For Loop: **2,206 ns**
- Math Operation: **2,488 ns**

**3. Frame time breakdown (at 1000 iterations):**
```
Total frame time: 118 μs

Node executions per frame:
  - Tick:           1 ×    727 ns =     727 ns
  - For Loop:      11 ×  2,206 ns =  24,266 ns  (loop runs 10 iterations + 1 setup)
  - Control Switch: 10 ×    842 ns =   8,420 ns
  - Math Operation: 10 ×  2,488 ns =  24,880 ns
  - Print Log:      1 ×  1,953 ns =   1,953 ns
                                    ──────────
  Total node time:                   60,246 ns ≈ 60 μs
```

So nodes account for ~60 μs out of 118 μs total frame time. The other **58 μs** is VM overhead (flow traversal, trigger creation, context setup, etc.).

## Comparison: Sync vs Threaded

| Environment | Frame Time | Node Overhead |
|-------------|------------|---------------|
| **Sync (1000 iter)** | 118 μs | ~60 μs |
| **Threaded (1000 iter)** | ~400 μs | ~60 μs + ~340 μs threading |

Threading adds ~280-340 μs per frame of overhead (queues, locks, context switches).

## Theoretical Maximum FPS

| Mode | Frame Time | Max FPS |
|------|------------|---------|
| **Sync (warmed up)** | 118 μs | **~8,500 FPS** |
| **Threaded** | 400 μs | **~2,500 FPS** |
| **Threaded + UI (NiceGUI)** | ~20 ms (sleep issue) | **~50 FPS** |

## Conclusions

1. **Your node code is fast** - 700-2500 ns per node is excellent
2. **VM overhead is ~58 μs per frame** - room for optimization if needed
3. **Threading adds ~300 μs** - acceptable for real-time apps
4. **The sleep issue is your main bottleneck** - fix `time.sleep()` precision to unlock 60+ FPS in the threaded version

Would you like to:
1. Profile the VM overhead to find where the 58 μs goes?
2. Implement the precise sleep fix for the threaded version?
3. Something else?