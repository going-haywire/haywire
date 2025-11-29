
from typing import TYPE_CHECKING, Any
from ..data.enums import FlowType
from haywire.core.types.utils import create_port_base

class TypeToDataPort:
    """
    Mixin providing methods to create data ports from this type.

    These are convenience classmethods that delegate to shared utilities.
    """

    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> Any:
        """
        Create an inlet from this type.

        Args:
            id: Port identifier within the node (e.g., 'input_value')
            **kwargs: Override identity attributes or add port-specific fields

        Returns:
            PortInlet configured with this type's identity

        Example:
            FLOAT.as_inlet('value', default=1.0)
            Temperature.as_inlet('temp', default=25.0, ui={'unit': '°C'})
        """
        from .ports import PortInlet
        return create_port_base(cls, PortInlet, id, **kwargs)

    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> Any:
        """
        Create an outlet from this type.

        Args:
            id: Port identifier within the node (e.g., 'output_result')
            **kwargs: Override identity attributes or add port-specific fields

        Returns:
            PortOutlet configured with this type's identity

        Example:
            FLOAT.as_outlet('result')
            MeshData.as_outlet('mesh')
        """
        from .ports import PortOutlet
        return create_port_base(cls, PortOutlet, id, **kwargs)

    @classmethod
    def as_config(cls, id: str, **kwargs) -> any:
        """
        Create a config inlet (no visible pin) from this type.

        Args:
            id: Config identifier within the node
            **kwargs: Override identity attributes

        Returns:
            PortInlet with flow_type=NONE (no visible pin)

        Example:
            FLOAT.as_config('threshold', default=0.5)
        """
        return cls.as_inlet(id, flow_type=FlowType.NONE, **kwargs)