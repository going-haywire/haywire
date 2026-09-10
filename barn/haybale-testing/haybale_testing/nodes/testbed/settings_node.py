from haywire.core.node import node, BaseNode, NodeType
from haywire.core.execution.execution_context import ExecutionContext

from haywire.core.settings import NodeSettings, setting, shadow, watch, Vec2i, Vec3f, Vec4f
from haybale_testing.settings.testing import TestingSettings
from haywire.barn.builtin.types import (
    BOOL,
    CHOICES,
    COLOR,
    FLOAT,
    INT,
    OPTIONAL,
    STRING,
    VEC2I,
    VEC3F,
    VEC4F,
)


@node(
    label="Settings Test Node",
    description="Test the Settings for debugging",
    search_tags=["settings", "debug", "test", "example"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SettingsNode(BaseNode):
    """Node that exercises all setting() — suppress spurious delete test."""

    # --8<-- [start:settings_node_class]
    class example(NodeSettings):
        # --- type_ ---
        example_string = setting[STRING](
            "default string",
            label="Example String",
            description="An example string setting",
            category="type",
        )
        example_int = setting[INT](
            3,
            min=0,
            max=100,
            label="Example Int",
            description="An example integer setting",
            category="type",
        )
        example_float = setting[FLOAT](
            5,
            min=0.0,
            max=1.0,
            label="Example Float",
            description="A float setting with explicit type_ override",
            category="type",
        )
        example_bool = setting[BOOL](
            False,
            label="Example Bool",
            description="An example boolean setting",
            category="type",
        )
        example_choices = setting[CHOICES](
            "fast",
            widget_config={"options": ["fast", "balanced", "quality"]},
            label="Example Choices",
            description="An example choices setting",
            category="type",
        )
        example_color = setting[COLOR](
            "#00ff00",
            label="Example Color",
            description="An example color setting",
            category="type",
        )
        example_vec2i = setting[VEC2I](
            Vec2i([4, 8]),
            label="Example Vec2i",
            description="A 2-component integer vector",
            category="type",
        )
        example_vec3f = setting[VEC3F](
            Vec3f([1.0, 2.0, 3.0]),
            label="Example Vec3f",
            description="A 3-component float vector",
            category="type",
        )
        example_vec4f = setting[VEC4F](
            Vec4f([0.0, 0.0, 0.0, 1.0]),
            label="Example Vec4f",
            description="A 4-component float vector (e.g. RGBA or homogeneous coords)",
            category="type",
        )

        # --- stored ---
        persistent_value = setting[FLOAT](
            1.0,
            label="Persistent Value",
            description="Normal stored setting",
            category="stored",
        )

        # --- mirrors (shadow = writable, watch = read-only) ---
        intensity = shadow(TestingSettings.default_intensity, label="Intensity", category="mirrors")
        count_mirror = shadow(TestingSettings.default_count, label="Count Mirror", category="mirrors")
        label_mirror = shadow(TestingSettings.default_label, label="Label Mirror", category="mirrors")
        enabled = shadow(TestingSettings.default_enabled, label="Enabled", category="mirrors")
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT its
        # per-setting widget_config — options must be re-supplied here.
        mode = shadow(
            TestingSettings.default_mode,
            label="Mode",
            category="mirrors",
            widget_config={"options": ["fast", "balanced", "quality"]},
        )
        tint = shadow(TestingSettings.default_color, label="Tint", category="mirrors")
        offset = shadow(TestingSettings.default_offset, label="Offset", category="mirrors")
        position = shadow(TestingSettings.default_position, label="Position", category="mirrors")
        intensity_ro = watch(
            TestingSettings.default_intensity, label="Intensity (read-only)", category="mirrors"
        )
        count_ro = watch(TestingSettings.default_count, label="Count (read-only)", category="mirrors")
        label_ro = watch(TestingSettings.default_label, label="Label (read-only)", category="mirrors")
        enabled_ro = watch(TestingSettings.default_enabled, label="Enabled (read-only)", category="mirrors")
        mode_ro = watch(
            TestingSettings.default_mode,
            label="Mode (read-only)",
            category="mirrors",
            widget_config={"options": ["fast", "balanced", "quality"]},
        )
        tint_ro = watch(TestingSettings.default_color, label="Tint (read-only)", category="mirrors")
        offset_ro = watch(TestingSettings.default_offset, label="Offset (read-only)", category="mirrors")
        position_ro = watch(
            TestingSettings.default_position, label="Position (read-only)", category="mirrors"
        )

        # --- validator ---
        validated_string = setting[STRING](
            "hello",
            label="Validated String",
            description="Must be non-empty",
            category="validator",
            validator=lambda v: isinstance(v, str) and len(v) > 0,
        )
        clamped_positive = setting[FLOAT](
            1.0,
            min=0.0,
            max=100.0,
            label="Clamped Positive",
            description="Must be positive (validator rejects <= 0)",
            category="validator",
            validator=lambda v: isinstance(v, (int, float)) and v > 0,
        )
        even_int = setting[INT](
            4,
            label="Even Integer",
            description="Must be an even integer",
            category="validator",
            validator=lambda v: isinstance(v, int) and v % 2 == 0,
        )

        # --- optional ---
        # A wrapper type: the field can hold a value of the wrapped IType, or
        # ABSENCE ("don't pass this parameter at all"). Absence is a value, not
        # an opinion about whether the tier is set — see ADR 0033.
        optional_int = setting[OPTIONAL[INT]](
            None,
            min=1,
            max=1000,
            label="Optional Int",
            description="Rests absent. The declared range is the REAL range — no sentinel to admit.",
            category="optional",
        )
        optional_float = setting[OPTIONAL[FLOAT]](
            None,
            min=0.0,
            max=1.0,
            label="Optional Float",
            description="A validator constrains the PRESENT domain only; absence is always allowed.",
            category="optional",
            validator=lambda v: 0.0 <= v <= 1.0,
        )
        optional_bool = setting[OPTIONAL[BOOL]](
            None,
            label="Optional Bool",
            description="Tri-state without a tri-state: True, False, or nothing.",
            category="optional",
        )
        optional_with_default = setting[OPTIONAL[INT]](
            -1,
            min=-1,
            max=100,
            label="Optional With Default",
            description="Rests at a VALUE and can still be cleared — so Reset and 'Set to none' differ.",
            category="optional",
        )
        optional_restore = setting[OPTIONAL[INT]](
            None,
            label="Optional Restore",
            description="Absent by default, but clicking 'none' enters 42 (per-use restore=).",
            category="optional",
            widget_config={"restore": 42},
        )

    # --8<-- [end:settings_node_class]

    def init(self):
        self.add(STRING.as_outlet("settings", label="Settings", default="default value"))

    def post_init(self):
        print(f"Post-init: example_string = {self.example.example_string}")
        print(f"Post-init: example_float = {self.example.example_float}")
        print(f"Post-init: persistent = {self.example.persistent_value}")
        print(f"Post-init: clamped_positive = {self.example.clamped_positive}")
        print(f"Post-init: even_int = {self.example.even_int}")

    def worker(self, context: ExecutionContext) -> str | None:
        """Execute the node - display the input value"""
        return None
