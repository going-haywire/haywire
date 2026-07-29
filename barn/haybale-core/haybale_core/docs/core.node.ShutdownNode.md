# Shutdown

`core:node:ShutdownNode` · kind: node

Triggered when execution is shutting down

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| timestamp | outlet | builtin:type:FLOAT | Decimal numberer |

## Notes

Triggered when execution is shutting down.

Use this node to perform cleanup operations before the interpreter stops.
For example:
- Close file handles
- Save state
- Release resources
- Log shutdown information

The node is triggered by SHUTDOWN system events, typically dispatched when:
- User stops the interpreter loop
- Application is closing
- System is shutting down

Outputs:
    exec: Control flow
    timestamp: Time when shutdown was triggered (seconds since epoch)

Examples:
    Shutdown → SaveState → PrintMessage("Cleanup complete")

    .. code-block:: python

        # In graph
        shutdown = graph.create_node_wrapper('shutdown')
        save = graph.create_node_wrapper('save_state')
        print_msg = graph.create_node_wrapper('print_message')

        # Connect shutdown flow
        graph.create_edge_wrapper(
            shutdown.node_id, 'exec',
            save.node_id, 'exec'
        )
        graph.create_edge_wrapper(
            save.node_id, 'done',
            print_msg.node_id, 'exec'
        )
