from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType

@node(
    label='Print Message',
    menu='testing/utils',
    node_type=NodeType.CONTROL
)
class PrintMessageNode(BaseNode):
    """Simple control node that prints a message"""
    
    def init(self):
        from haybale_core.types.specs import EXEC, STRING
        
        # Control flow
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        
        # Data input
        self.add(STRING.as_inlet('message', default='Hello, World!'))
    
    def worker(self, context: ExecutionContext) -> str | None:
        message = self.value('message')
        print(f"[PrintMessage] {message}")
        return 'done'