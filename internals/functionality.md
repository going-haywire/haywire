# Functionality descisions and design rationale for Haywire.

## Port Value Serialization (13.02.2026)

There is only one value to serialize. A value that is set via inlet will be displayed in the UI. Any values set by the user via UI prior to the connection forming will be overridden by the value coming from the inlet. This is a design choice to ensure that the UI always reflects the current state of the node, and to avoid confusion about which value is active.

