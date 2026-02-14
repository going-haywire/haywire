from enum import Enum, IntFlag

class FlowType(Enum):
    """
    Type of data flow through a port.
    
    - NONE: Configuration port (no flow, not a pin)
    - CONTROL: Execution flow (determines when nodes execute)
    - DATA: Data flow (passes values between nodes)
    - CALLBACK: Callback registration (event nodes declare interest)
    """
    CONTROL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'

class PortType(Enum):
    """
    - INLET: Can receives data/control via Inlets
    - OUTLET: Sends data/control via Outlets
    - CONFIG: Has neither Inlets nor Outlets
    """
    INLET = "inlet"
    OUTLET = "outlet"
    CONFIG = "config"


class StoreStrategy(IntFlag):
    """
    Bitwise flags for store behavior.
    HAS_WIDGET stores when the port has a widget (whether the user changes the value or not)
    WHEN_LINKED stores when the port pin is linked
    NODE_SET stores when the value was changed by the node
    ALWAYS stores in any case

    Example:
        It is possible to combine the HAS_WIDGET, WHEN_LINKED and NODE_SET strategies,
        But only in OR - logic:

        .. code-block:: python
            store_strategy = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET

        This stores when HAS_WIDGET is True **OR** NODE_SET is True

    Caveat:
        It is **NOT** possible to combine them in AND logic, like
        store only if HAS_WIDGET is True **AND** WHEN_LINKED is True
    """
    NEVER    = 1
    HAS_WIDGET  = 2
    WHEN_LINKED    = 4   
    NODE_SET = 8 
    ALWAYS  = HAS_WIDGET | WHEN_LINKED | NODE_SET # 14
