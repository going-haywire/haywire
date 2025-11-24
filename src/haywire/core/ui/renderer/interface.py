
from abc import ABC

class IBaseRenderer(ABC):
    """
    Abstract base class for all NodeRenderer classes.

    NodeRenderer classes define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """
    pass
