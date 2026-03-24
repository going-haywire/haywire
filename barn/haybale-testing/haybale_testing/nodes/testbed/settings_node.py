from haywire.core.node import node, BaseNode, NodeType
from haybale_core.types.specs import STRING

from haywire.core.settings import Settings, setting
from haybale_testing.settings.testing import TestingSettings


@node(
    label="Settings Test Node",
    description="Test the Settings for debugging",
    search_tags=["settings", "debug", "test", "example"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SettingsNode(BaseNode):
    """Node that exercises all prop() features from Issue #2: type_, stored, validator."""

    class example(Settings):
        # --- type_ ---
        example_string: str = setting(
            "default string",
            label="My Setting",
            description="An example setting for demonstration purposes",
            category="type",
        )
        example_float: float = setting(
            5,
            min=0.0,
            max=1.0,
            label="Example Float",
            description="A float setting with explicit type_ override",
            category="type",
            type_=float,
        )

        # --- read only ---
        read_only_value: float = setting(
            1.0,
            label="Read-Only Value",
            description="Read-only stored setting",
            category="stored",
            read_only=True,
        )

        # --- stored ---
        persistent_value: float = setting(
            1.0,
            label="Persistent Value",
            description="Normal stored setting (stored=True by default)",
            category="stored",
        )
        transient_value: float = setting(
            0.0,
            label="Transient Value",
            description="Ephemeral setting excluded from serialization",
            category="stored",
            stored=False,
        )

        # --- mirrors (shadow) ---
        intensity: float = setting(
            label="Intensity",
            description="Mirrors library-level default_intensity (override locally per node)",
            category="mirrors",
            mirrors=TestingSettings.default_intensity,
        )

        # --- validator ---
        clamped_positive: float = setting(
            1.0,
            min=0.0,
            max=100.0,
            label="Clamped Positive",
            description="Must be positive (validator rejects <= 0)",
            category="validator",
            validator=lambda v: isinstance(v, (int, float)) and v > 0,
        )
        even_int: int = setting(
            4,
            label="Even Integer",
            description="Must be an even integer",
            category="validator",
            type_=int,
            validator=lambda v: isinstance(v, int) and v % 2 == 0,
        )

    def init(self):
        self.add(STRING.as_outlet("settings", label="Settings", default="default value"))

    def post_init(self):
        print(f"Post-init: example_string = {self.example.example_string}")
        print(f"Post-init: example_float = {self.example.example_float}")
        print(f"Post-init: persistent = {self.example.persistent_value}")
        print(f"Post-init: transient = {self.example.transient_value}")
        print(f"Post-init: clamped_positive = {self.example.clamped_positive}")
        print(f"Post-init: even_int = {self.example.even_int}")

    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        return None
