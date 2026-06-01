from enum import Enum, IntFlag


class FlowType(Enum):
    """
    Type of data flow through a port.

    - NONE: Configuration port (no flow, not a pin)
    - CONTROL: Execution flow (determines when nodes execute)
    - DATA: Data flow (passes values between nodes)
    - CALLBACK: Callback registration (event nodes declare interest)
    """

    CONTROL = "control"
    DATA = "data"
    CALLBACK = "callback"
    NONE = "none"


class PortType(Enum):
    """
    - INLET: Can receives data/control via Inlets
    - OUTLET: Sends data/control via Outlets
    - CONFIG: Has neither Inlets nor Outlets
    """

    UNDEFINED = "undefined"
    INLET = "inlet"
    OUTLET = "outlet"
    CONFIG = "config"


class StoreStrategy(IntFlag):
    """
    Bitwise flags for when a port stores its value.

    - NEVER: do not store
    - HAS_WIDGET: store when the port has a widget
    - WHEN_LINKED: store when the port pin is linked
    - NODE_SET: store when the value was changed by the node
    - ALWAYS: store in any case

    Combine flags with OR; they trigger if any flag matches (there is no AND combination)::

        store_strategy = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
    """

    NONE = 0
    NEVER = 1
    HAS_WIDGET = 2
    WHEN_LINKED = 4
    NODE_SET = 8
    ALWAYS = HAS_WIDGET | WHEN_LINKED | NODE_SET  # 14
