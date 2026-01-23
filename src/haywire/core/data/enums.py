from enum import Enum

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

class SocketType(Enum):
    """
    Direction of data flow through a port.
    
    - INLET: Receives data/control
    - OUTLET: Sends data/control
    """
    INLET = "inlet"
    OUTLET = "outlet"