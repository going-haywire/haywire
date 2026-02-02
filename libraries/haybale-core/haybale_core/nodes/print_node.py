from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType
from haywire.ui.console_bridge import console_print

@node(
    label='Print Log',
    menu='core/utils',
    node_type=NodeType.CONTROL
)
class PrintLogNode(BaseNode):
    """Prints a message to the haywire ui console"""
    
    def init(self):
        from haybale_core.types.specs import EXEC, STRING
        
        # Control flow
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        
        # Data input
        self.add(STRING.as_inlet('message', default='Hello, World!'))
    
    def worker(self, context):
        message = self.value('message')
        console_print(message)  # Thread-safe, appears in UI
        return 'done'