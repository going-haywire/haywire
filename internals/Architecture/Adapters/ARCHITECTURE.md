Connection Request
       ↓
1. Editor: create_connection(source, target)
       ↓
2. Graph: add_edge validates nodes/pins
       ↓
3. Graph: Gets ports from node wrappers
       ↓
4. Pipe: __init__ calls target_inlet.data.is_compatible_with()
       ↓
5. DataField: Returns (bool, reason, adapter_chain)
       ↓
6. Pipe: Stores adapter_chain
       ↓
7. Graph: Stores edge and pipe
       ↓
8. Editor: Returns (success, message) with feedback

Runtime Propagation
       ↓
1. Outlet: Value changes
       ↓
2. Outlet: Propagates to all pipes
       ↓
3. Pipe: Applies adapter_chain
       ↓
4. Inlet: Receives converted value