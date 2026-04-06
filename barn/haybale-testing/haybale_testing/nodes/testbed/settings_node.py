from haywire.core.node import node, BaseNode, NodeType
from haybale_core.types.specs import STRING

from haywire.core.settings import NodeSettings, field, shadow, watch, Color, Vec2i, Vec3f, Vec4f
from haybale_testing.settings.testing import TestingSettings


@node(
    label="Settings Test Node",
    description="Test the Settings for debugging",
    search_tags=["settings", "debug", "test", "example"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SettingsNode(BaseNode):
    """Node that exercises all field() — suppress spurious delete test."""

    class example(NodeSettings):
        # --- type_ ---
        example_string: str = field(
            "default string",
            label="Example String",
            description="An example string setting",
            category="type",
        )
        example_int: int = field(
            3,
            min=0,
            max=100,
            label="Example Int",
            description="An example integer setting",
            category="type",
        )
        example_float: float = field(
            5,
            min=0.0,
            max=1.0,
            label="Example Float",
            description="A float setting with explicit type_ override",
            category="type",
            type_=float,
        )
        example_bool: bool = field(
            False,
            label="Example Bool",
            description="An example boolean setting",
            category="type",
        )
        example_choices: str = field(
            "fast",
            choices=["fast", "balanced", "quality"],
            label="Example Choices",
            description="An example choices setting",
            category="type",
        )
        example_color: Color = field(
            "#00ff00",
            label="Example Color",
            description="An example color setting",
            category="type",
            widget="color",
        )
        example_vec2i: Vec2i = field(
            [4, 8],
            label="Example Vec2i",
            description="A 2-component integer vector",
            category="type",
        )
        example_vec3f: Vec3f = field(
            [1.0, 2.0, 3.0],
            label="Example Vec3f",
            description="A 3-component float vector",
            category="type",
        )
        example_vec4f: Vec4f = field(
            [0.0, 0.0, 0.0, 1.0],
            label="Example Vec4f",
            description="A 4-component float vector (e.g. RGBA or homogeneous coords)",
            category="type",
        )

        # --- read only ---
        read_only_value: float = field(
            1.0,
            label="Read-Only Value",
            description="Read-only stored setting",
            category="stored",
            read_only=True,
        )

        # --- stored ---
        persistent_value: float = field(
            1.0,
            label="Persistent Value",
            description="Normal stored setting (stored=True by default)",
            category="stored",
        )
        transient_value: float = field(
            0.0,
            label="Transient Value",
            description="Ephemeral setting excluded from serialization",
            category="stored",
            stored=False,
        )

        # --- mirrors (shadow = writable, watch = read-only) ---
        intensity: float = shadow(TestingSettings.default_intensity, label="Intensity", category="mirrors")
        count_mirror: int = shadow(TestingSettings.default_count, label="Count Mirror", category="mirrors")
        label_mirror: str = shadow(TestingSettings.default_label, label="Label Mirror", category="mirrors")
        enabled: bool = shadow(TestingSettings.default_enabled, label="Enabled", category="mirrors")
        mode: str = shadow(TestingSettings.default_mode, label="Mode", category="mirrors")
        tint: Color = shadow(TestingSettings.default_color, label="Tint", category="mirrors")
        offset: Vec2i = shadow(TestingSettings.default_offset, label="Offset", category="mirrors")
        position: Vec3f = shadow(TestingSettings.default_position, label="Position", category="mirrors")
        intensity_ro: float = watch(
            TestingSettings.default_intensity, label="Intensity (read-only)", category="mirrors"
        )
        count_ro: int = watch(TestingSettings.default_count, label="Count (read-only)", category="mirrors")
        label_ro: str = watch(TestingSettings.default_label, label="Label (read-only)", category="mirrors")
        enabled_ro: bool = watch(
            TestingSettings.default_enabled, label="Enabled (read-only)", category="mirrors"
        )
        mode_ro: str = watch(TestingSettings.default_mode, label="Mode (read-only)", category="mirrors")
        tint_ro: Color = watch(TestingSettings.default_color, label="Tint (read-only)", category="mirrors")
        offset_ro: Vec2i = watch(
            TestingSettings.default_offset, label="Offset (read-only)", category="mirrors"
        )
        position_ro: Vec3f = watch(
            TestingSettings.default_position, label="Position (read-only)", category="mirrors"
        )

        # --- validator ---
        validated_string: str = field(
            "hello",
            label="Validated String",
            description="Must be non-empty",
            category="validator",
            validator=lambda v: isinstance(v, str) and len(v) > 0,
        )
        clamped_positive: float = field(
            1.0,
            min=0.0,
            max=100.0,
            label="Clamped Positive",
            description="Must be positive (validator rejects <= 0)",
            category="validator",
            validator=lambda v: isinstance(v, (int, float)) and v > 0,
        )
        even_int: int = field(
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
