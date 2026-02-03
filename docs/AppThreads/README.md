

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