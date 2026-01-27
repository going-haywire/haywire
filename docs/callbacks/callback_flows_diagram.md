# Callback Flow Diagrams

## Diagram 1: Graph Structure with Nodes and Ports

This shows the two disconnected flows in the graph, with their nodes and relevant ports.

```mermaid
graph TB
    subgraph "Flow 1: Emitter Flow (Event: system:begin_play)"
        BP[BeginPlayNode]
        BP_exec_out["exec (outlet)"]
        BP_timestamp_out["timestamp (outlet)"]
        
        EC[EmitCallbackNode]
        EC_exec_in["exec (inlet)"]
        EC_done_out["done (outlet)"]
        EC_callback_name["callback_name (inlet)<br/>default: 'my_callback'"]
        EC_message["message (inlet)<br/>default: 'Hello!'"]
        
        BP --> BP_exec_out
        BP --> BP_timestamp_out
        BP_exec_out -->|Control Edge| EC_exec_in
        EC_exec_in --> EC
        EC --> EC_done_out
        EC --> EC_callback_name
        EC --> EC_message
    end
    
    subgraph "Flow 2: Listener Flow (Event: callback:my_callback)"
        CC[CustomCallbackNode<br/>EventNode]
        CC_listen_out["listen_callback (outlet)<br/>callback type<br/>event_filter: 'my_callback'"]
        CC_triggered_out["triggered (outlet)"]
        CC_payload_out["payload (outlet)"]
        
        PM[PrintMessageNode]
        PM_exec_in["exec (inlet)"]
        PM_done_out["done (outlet)"]
        PM_message_in["message (inlet)"]
        
        CC --> CC_listen_out
        CC --> CC_triggered_out
        CC --> CC_payload_out
        CC_triggered_out -->|Control Edge| PM_exec_in
        CC_payload_out -->|Data Edge| PM_message_in
        PM_exec_in --> PM
        PM --> PM_done_out
        PM --> PM_message_in
    end
    
    style BP fill:#90EE90
    style CC fill:#90EE90
    style BP_exec_out fill:#FFD700
    style EC_exec_in fill:#FFD700
    style EC_done_out fill:#FFD700
    style CC_triggered_out fill:#FFD700
    style PM_exec_in fill:#FFD700
    style PM_done_out fill:#FFD700
    style CC_listen_out fill:#FF6B6B
    style BP_timestamp_out fill:#87CEEB
    style CC_payload_out fill:#87CEEB
    style PM_message_in fill:#87CEEB
    style EC_callback_name fill:#87CEEB
    style EC_message fill:#87CEEB
    
    classDef eventNode fill:#90EE90,stroke:#333,stroke-width:3px
    classDef controlPort fill:#FFD700,stroke:#333,stroke-width:2px
    classDef dataPort fill:#87CEEB,stroke:#333,stroke-width:2px
    classDef callbackPort fill:#FF6B6B,stroke:#333,stroke-width:2px
```

**Legend:**
- 🟢 Green nodes = Event Nodes
- 🟡 Yellow ports = Control ports (exec)
- 🔵 Blue ports = Data ports
- 🔴 Red port = Callback port (special marker, not a graph connection)

**Note:** There are NO graph edges between Flow 1 and Flow 2. The callback connection happens at runtime through the CallbackManager.

---

## Diagram 2: Runtime Message Flow Between Components

This shows how the callback message flows through the system components at runtime.

```mermaid
sequenceDiagram
    autonumber
    
    participant User as External System
    participant Interp as Interpreter
    participant Sched1 as Flow1 Scheduler<br/>(Thread 1)
    participant VM as HaywireVM
    participant CBMgr as CallbackManager
    participant Sched2 as Flow2 Scheduler<br/>(Thread 2)
    
    rect rgb(240, 240, 240)
        Note over User,Sched2: ASSEMBLY TIME
        Interp->>Interp: load_graph()
        Interp->>Interp: assemble_graph()
        Interp->>Interp: register Flow1<br/>(event: system:begin_play)
        Interp->>Interp: register Flow2<br/>(event: callback:my_callback)
        Interp->>CBMgr: register_callback_listener<br/>('my_callback', Flow2)
        Note over CBMgr: callbacks['my_callback'] = [Flow2]
    end
    
    rect rgb(255, 250, 240)
        Note over User,Sched2: RUNTIME: BEGIN_PLAY Event
        User->>Interp: dispatch_system_event(BEGIN_PLAY)
        Interp->>Sched1: enqueue_trigger(Trigger)
        Note over Sched1: Trigger queued
        
        Sched1->>VM: execute_control_flow(Flow1, Trigger)
        Note over VM: Start execution<br/>at BeginPlayNode
        
        VM->>VM: execute BeginPlayNode.worker()
        VM->>VM: navigate to EmitCallbackNode
        VM->>VM: execute EmitCallbackNode.worker()
        
        Note over VM: EmitCallbackNode calls:<br/>context['emit_callback']()
        VM->>CBMgr: emit_callback('my_callback', payload)
    end
    
    rect rgb(240, 255, 240)
        Note over CBMgr,Sched2: CALLBACK BRIDGE (The Key Moment!)
        CBMgr->>CBMgr: lookup callbacks['my_callback']
        Note over CBMgr: Found: [Flow2]
        CBMgr->>CBMgr: Create Trigger<br/>(source: callback:my_callback)
        CBMgr->>Sched2: enqueue_trigger(Trigger)
        Note over Sched2: Callback trigger queued
    end
    
    rect rgb(255, 240, 240)
        Note over Sched2,VM: FLOW 2 EXECUTION
        Sched2->>VM: execute_control_flow(Flow2, Trigger)
        Note over VM: Start execution<br/>at CustomCallbackNode
        
        VM->>VM: execute CustomCallbackNode.worker()
        Note over VM: Extract payload<br/>from trigger
        VM->>VM: navigate to PrintMessageNode
        VM->>VM: evaluate data flow<br/>(payload → message)
        VM->>VM: execute PrintMessageNode.worker()
        Note over VM: Prints: "Hello!"
        
        VM->>Sched2: execution complete
    end
    
    rect rgb(240, 240, 240)
        Note over User,Sched2: COMPLETION
        Sched1->>Interp: Flow1 complete
        Sched2->>Interp: Flow2 complete
    end
```

**Key Moments in the Flow:**

1-6. **Assembly**: Flows registered, Flow2 registers interest in 'my_callback'
7-11. **Flow1 Starts**: BEGIN_PLAY event triggers Flow1
12-13. **Callback Emission**: EmitCallbackNode calls emit_callback()
14-17. **The Bridge**: CallbackManager looks up listeners and triggers Flow2
18-24. **Flow2 Executes**: CustomCallbackNode receives callback and continues

---

## Diagram 3: Component Relationships (Static Structure)

This shows how components are wired together.

```mermaid
graph TB
    subgraph "Interpreter (Main Coordinator)"
        Interp[Interpreter]
        ES[event_subscriptions<br/>Dict]
        AGM[assembly_manager]
    end
    
    subgraph "Shared Components"
        VM[HaywireVM]
        CBM[CallbackManager]
    end
    
    subgraph "Flow 1 (Thread 1)"
        F1[Flow 1<br/>event: system:begin_play]
        S1[Scheduler 1]
        CG1[ControlFlowGraph]
        BP[BeginPlayNode]
        EC[EmitCallbackNode]
    end
    
    subgraph "Flow 2 (Thread 2)"
        F2[Flow 2<br/>event: callback:my_callback]
        S2[Scheduler 2]
        CG2[ControlFlowGraph]
        CC[CustomCallbackNode]
        PM[PrintMessageNode]
    end
    
    Interp -->|manages| AGM
    Interp -->|owns| ES
    Interp -->|owns| VM
    Interp -->|owns| CBM
    VM -.->|references| CBM
    
    Interp -->|registered in| ES
    F1 -->|registered in| ES
    F2 -->|registered in| ES
    
    F1 -->|owns| S1
    F1 -->|owns| CG1
    CG1 -->|contains| BP
    CG1 -->|contains| EC
    
    F2 -->|owns| S2
    F2 -->|owns| CG2
    CG2 -->|contains| CC
    CG2 -->|contains| PM
    
    S1 -.->|uses| VM
    S2 -.->|uses| VM
    
    F2 -->|registered in| CBM
    
    EC -.->|emit_callback| VM
    VM -.->|forward to| CBM
    CBM -.->|trigger| S2
    
    style Interp fill:#FFE4B5
    style VM fill:#FFD700
    style CBM fill:#FF6B6B
    style F1 fill:#90EE90
    style F2 fill:#87CEEB
    style ES fill:#F0E68C
    style AGM fill:#F0E68C
    
    classDef shared fill:#FFD700,stroke:#333,stroke-width:3px
```

**Component Roles:**

- **Interpreter**: Main coordinator, owns all other components
- **CallbackManager**: THE BRIDGE - shared state connecting flows
- **HaywireVM**: Executes flows, has reference to CallbackManager
- **Flow Schedulers**: Thread + queue per flow
- **Flows**: Independent execution units with their own control graphs

---

## Key Insights from the Diagrams

1. **Graph Structure**: Flows are completely disconnected at the graph level
2. **Assembly Registration**: Flow2 registers interest in 'my_callback' during assembly
3. **Runtime Bridge**: CallbackManager is the shared component that connects flows
4. **Thread Isolation**: Each flow runs in its own thread via its scheduler
5. **Message Path**: EmitCallback → VM → CallbackManager → Flow2 Scheduler → CustomCallback

The callback system enables **decoupled inter-flow communication** without requiring graph edges!