"""
Control Switch Node.

Routes control flow to its True or False outlet by comparing two values.
"""

import operator

from haywire.api import (
    EXEC,
    FLOAT,
    INT,
    STRING,
    BaseNode,
    ExecutionContext,
    NodeType,
    NumberWidget,
    MenuWidget,
    node,
)

# Mapping of condition strings to operator functions
OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "<": operator.lt,
    "<=": operator.le,
    "!=": operator.ne,
}


@node(
    label="Control Switch",
    description="Switches control flow based on condition",
    menu="core/control/switch",
    search_tags=["switch", "control", "flow", "event"],
    node_type=NodeType.CONTROL,
)
class ControlSwitchNode(BaseNode):
    """
    Triggered when execution is switching control flow based on condition.
    """

    def init(self):
        # Control output

        self.add(EXEC.as_inlet("exec", label="Execute"))

        self.add(
            STRING.as_config(
                "DataType",
                label="Data Type",
                description="",
                widget=MenuWidget.config(properties={"options": ["int", "float", "string"]}),
                default="int",
                on_change="hb_change",
            )
        )

        self.add(EXEC.as_outlet("true", label="True"))
        self.add(EXEC.as_outlet("false", label="False"))

        self.add(INT.as_outlet("test", label="Test"))

    def post_init(self):
        self.hb_change()

    def hb_change(self, *args, **kwargs) -> None:
        with self.rejig(exclude=["exec", "true", "false", "DataType", "test"]):
            if self.value("DataType") == "int":
                self.add(
                    STRING.as_config(
                        "condition",
                        label="Condition",
                        description="set form of comparison",
                        widget=MenuWidget.config(properties={"options": [">", ">=", "==", "<", "<=", "!="]}),
                        default="==",
                    )
                )
                self.add(INT.as_inlet("compare", label="Compare", widget=NumberWidget.config()))
                self.add(INT.as_inlet("with", label="With", widget=NumberWidget.config()))
            elif self.value("DataType") == "float":
                self.add(
                    STRING.as_config(
                        "condition",
                        label="Condition",
                        description="set form of comparison",
                        widget=MenuWidget.config(properties={"options": [">", ">=", "==", "<", "<=", "!="]}),
                        default="==",
                    )
                )
                self.add(FLOAT.as_inlet("compare", label="Compare", widget=NumberWidget.config()))
                self.add(FLOAT.as_inlet("with", label="With", widget=NumberWidget.config()))
            else:  # string
                self.add(
                    STRING.as_config(
                        "condition",
                        label="Condition",
                        widget=MenuWidget.config(properties={"options": ["==", "!="]}),
                        default="==",
                    )
                )
                self.add(STRING.as_inlet("compare", label="Compare", default=""))
                self.add(STRING.as_inlet("with", label="With", default=""))

    def worker(self, context: ExecutionContext, condition: str) -> str | None:
        data = self.value("compare")
        target = self.value("with")
        condition_str = self.value("condition")

        # Get the operator function and apply it
        op_func = OPERATORS.get(condition_str, operator.eq)
        result = op_func(data, target)

        # self.out('test', data)

        return "true" if result else "false"
