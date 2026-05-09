"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


# --8<-- [start:edge_link_test_node]
@node(
    label="Edge Link TestNode",
    search_tags=["testing", "edge", "link", "inlet", "outlet", "connection", "adapter"],
    menu="testing/testbed",
    node_type=NodeType.CONTROL,
)
class EdgeLinkTestNode(BaseNode):
    """
    Node specificly to test connection behaviors
    in the UI. It has a wide variety of inlet and outlet types
    to test all the different connection rules.
    It does not perform any actual logic in its worker,
    it just serves as a testbed for connections.
    """

    def init(self):
        from haybale_core.types import ArrayType
        from haybale_core.types import PooledType
        from haybale_core.types import CALLBACK, EXEC
        from haybale_testing.types.test_types import (
            TEST_BOOL,
            TEST_FLOAT,
            TEST_INT,
            TEST_STRING,
        )

        from haybale_testing.types.test_types import TEST_TEMPERATURE

        with self.rejig():
            self.add(CALLBACK.as_inlet(id="callback_inlet"))

            # Add control inlet (no type, just execution flow)
            self.add(EXEC.as_inlet(id="execute_inlet"))

            self.add(TEST_BOOL.as_inlet(id="bool_inlet", label="Boolean Inlet", default=True))

            self.add(TEST_INT.as_inlet(id="int_inlet", label="Int Inlet", default=42))

            self.add(TEST_FLOAT.as_inlet(id="float_inlet", label="Float Inlet", default=50.0))

            self.add(
                TEST_STRING.as_inlet(
                    id="string_inlet",
                    label="String Input",
                    default="Hello, Haywire!",
                )
            )

            # Temperature inlet (derived from FLOAT — tests type hierarchy)
            self.add(
                TEST_TEMPERATURE.as_inlet(id="temperature_inlet", label="Temperature Inlet", default=20.0)
            )

            self.add(PooledType[TEST_BOOL].as_inlet(id="pooled_bool_inlet", label="Pooled BOOL Inlet"))

            self.add(PooledType[TEST_INT].as_inlet(id="pooled_int_inlet", label="Pooled INT Inlet"))

            self.add(PooledType[TEST_FLOAT].as_inlet(id="pooled_float_inlet", label="Pooled FLOAT Inlet"))

            self.add(
                PooledType[TEST_TEMPERATURE].as_inlet(
                    id="pooled_temperature_inlet", label="Pooled Temperature Inlet"
                )
            )

            self.add(PooledType[TEST_STRING].as_inlet(id="pooled_string_inlet", label="Pooled STRING Inlet"))

            self.add(
                PooledType[ArrayType[TEST_STRING]].as_inlet(
                    id="pooled_array_string_inlet", label="Pooled ARRAY[STRING] Inlet"
                )
            )

            # Add outlets

            self.add(CALLBACK.as_outlet(id="callback_outlet"))

            self.add(EXEC.as_outlet(id="execute_out"))

            self.add(TEST_BOOL.as_outlet(id="bool_outlet", label="Boolean Output"))

            self.add(TEST_INT.as_outlet(id="int_outlet", label="Integer Output"))

            self.add(TEST_FLOAT.as_outlet(id="float_outlet", label="Float Output"))

            self.add(TEST_TEMPERATURE.as_outlet(id="temperature_outlet", label="Temperature Output"))

            self.add(TEST_STRING.as_outlet(id="string_outlet", label="Text Output"))

            self.add(ArrayType[TEST_BOOL].as_outlet(id="array_bool_outlet", label="ARRAY[TEST_BOOL]"))

            self.add(ArrayType[TEST_INT].as_outlet(id="array_int_outlet", label="ARRAY[TEST_INT]"))

            self.add(ArrayType[TEST_FLOAT].as_outlet(id="array_float_outlet", label="ARRAY[TEST_FLOAT]"))

            self.add(
                ArrayType[TEST_TEMPERATURE].as_outlet(
                    id="array_temperature_outlet", label="ARRAY[TEST_TEMPERATURE]"
                )
            )

            self.add(ArrayType[TEST_STRING].as_outlet(id="array_string_outlet", label="ARRAY[TEST_STRING]"))

    def redraw(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        self.wrapper.redraw()

    def worker(self, context: ExecutionContext) -> str | None:
        """Execute the node - return the constant value"""
        return None


# --8<-- [end:edge_link_test_node]
