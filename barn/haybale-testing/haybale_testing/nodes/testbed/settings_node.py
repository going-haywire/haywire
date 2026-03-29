from haywire.core.node import node, BaseNode, NodeType
from haybale_core.types.specs import STRING

from haywire.core.settings import NodeSettings, setting, Color
from haybale_testing.settings.testing import TestingSettings


@node(
    label="Settings Test Node",
    description="Test the Settings for debugging",
    search_tags=["settings", "debug", "test", "example"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SettingsNode(BaseNode):
    """Node that exercises all setting() features from Issue #2: type_, stored, validator."""

    class example(NodeSettings):
        # --- type_ ---
        example_string: str = setting(
            "default string",
            label="Example String",
            description="An example string setting",
            category="type",
        )
        example_int: int = setting(
            3,
            min=0,
            max=100,
            label="Example Int",
            description="An example integer setting",
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
        example_bool: bool = setting(
            False,
            label="Example Bool",
            description="An example boolean setting",
            category="type",
        )
        example_choices: str = setting(
            "fast",
            choices=["fast", "balanced", "quality"],
            label="Example Choices",
            description="An example choices setting",
            category="type",
        )
        example_color: Color = setting(
            "#00ff00",
            label="Example Color",
            description="An example color setting",
            category="type",
            widget="color",
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
            description="Mirrors library-level default_intensity",
            category="mirrors",
            mirrors=TestingSettings.default_intensity,
        )
        count_mirror: int = setting(
            label="Count Mirror",
            description="Mirrors library-level default_count",
            category="mirrors",
            mirrors=TestingSettings.default_count,
            min=0,
            max=100,
        )
        label_mirror: str = setting(
            label="Label Mirror",
            description="Mirrors library-level default_label",
            category="mirrors",
            mirrors=TestingSettings.default_label,
        )
        enabled: bool = setting(
            label="Enabled",
            description="Mirrors library-level default_enabled",
            category="mirrors",
            mirrors=TestingSettings.default_enabled,
        )
        mode: str = setting(
            label="Mode",
            description="Mirrors library-level default_mode",
            category="mirrors",
            mirrors=TestingSettings.default_mode,
            choices=["fast", "balanced", "quality"],
        )
        tint: Color = setting(
            label="Tint",
            description="Mirrors library-level default_color",
            category="mirrors",
            mirrors=TestingSettings.default_color,
            widget="color",
        )
        intensity_ro: float = setting(
            label="Intensity (read-only)",
            description="Read-only mirror of default_intensity",
            category="mirrors",
            mirrors=TestingSettings.default_intensity,
            read_only=True,
        )
        count_ro: int = setting(
            label="Count (read-only)",
            description="Read-only mirror of default_count",
            category="mirrors",
            mirrors=TestingSettings.default_count,
            read_only=True,
        )
        label_ro: str = setting(
            label="Label (read-only)",
            description="Read-only mirror of default_label",
            category="mirrors",
            mirrors=TestingSettings.default_label,
            read_only=True,
        )
        enabled_ro: bool = setting(
            label="Enabled (read-only)",
            description="Read-only mirror of default_enabled",
            category="mirrors",
            mirrors=TestingSettings.default_enabled,
            read_only=True,
        )
        mode_ro: str = setting(
            label="Mode (read-only)",
            description="Read-only mirror of default_mode",
            category="mirrors",
            mirrors=TestingSettings.default_mode,
            read_only=True,
        )
        tint_ro: Color = setting(
            label="Tint (read-only)",
            description="Read-only mirror of default_color",
            category="mirrors",
            mirrors=TestingSettings.default_color,
            read_only=True,
        )

        # --- validator ---
        validated_string: str = setting(
            "hello",
            label="Validated String",
            description="Must be non-empty",
            category="validator",
            validator=lambda v: isinstance(v, str) and len(v) > 0,
        )
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
