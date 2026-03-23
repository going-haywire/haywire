from haywire.core.node import node, BaseNode, NodeType
from haybale_core.types.specs import FLOAT, STRING

from haywire.core.settings import Settings, setting


@node(
    label='Settings Test Node',
    description='Test the Settings for debugging',
    search_tags=['settings', 'debug', 'test', 'example'],
    menu='testing/testbed',
    node_type=NodeType.DATA
)
class SettingsNode(BaseNode):
    """Node that demonstrates the Bag-based settings system."""

    class example(Settings):
        example_setting: str = setting(
            'default string',
            label='My Setting',
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
        # Accessing settings via the bag: self.<bag_name>.<field>
        print(f"Post-init: example_setting = {self.example.example_setting}")

    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        return None
