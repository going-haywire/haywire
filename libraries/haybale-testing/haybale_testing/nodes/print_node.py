from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode

@node(
    label='Print Message',
    menu='test/simple'
)
class PrintMessageNode(BaseNode):
    """Simple control node that prints a message"""
    
    def initialize(self):
        self.behavior.is_control_node = True
        self.behavior.is_data_node = False
        self.behavior.is_loopback = False

        from haybale_core.types.specs import EXEC, STRING
        
        # Control flow
        self.add(EXEC.as_inlet('exec'))
        self.add(EXEC.as_outlet('done'))
        
        # Data input
        self.add(STRING.as_inlet('message', default='Hello, World!'))
    
    def worker(self, context):
        message = self.value('message')
        print(f"[PrintMessage] {message}")
        return 'done', ()