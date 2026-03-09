from haywire.core.node import node, BaseNode, NodeType
from haybale_core.types.specs import FLOAT, STRING

from haywire.core.settings.descriptors import setting
from haywire.core.settings.schema import NodeSettings

@node(
    label='Settings Test Node',
    description='Test the Settings for debugging',
    search_tags=['settings', 'debug', 'test', 'example'],
    menu='testing/testbed',
    node_type=NodeType.DATA
)
class SettingsNode(BaseNode):
    """Node that displays input values"""
    
    class node(NodeSettings, namespace='display_node'):
        example_setting: str = setting(
            'default value',
            label='Example Setting',
            description='An example setting for demonstration purposes',
            category='example',
        )

    def init(self):
        self.add(
            STRING.as_outlet(
                'settings', label='Settings', default='default value'
            )
        )   

    def post_init(self):
        # Accessing settings in post_init (after they are fully initialized)
        print(f"Post-init: example_setting = {self.settings.example_setting}")
    
    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        return None
