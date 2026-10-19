"""``WidgetNode``, the base of the widget nodes."""

from typing import Any, ClassVar

from haybale_core.keys import WIDGET_NODE_SKIN
from haywire.barn.builtin.nodes.annotation import H_ALIGNS
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, INT, OPTIONAL
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode
from haywire.core.settings import NodeSettings, Promotable, Settings, setting, settings_fields
from haywire.core.skin.fonts import FONTS
from haywire.core.skin.settings import _widget_node_stage_skin_choices
from haywire.core.types.enums import ShowWidgetStrategy
from haywire.core.types.interface import IType


#: Where the stage face puts the node label.
LABEL_POSITIONS = ("left", "above", "hidden")

_NONE = Promotable.NONE


class WidgetNode(BaseNode):
    """A DATA node whose outlet's widget is the node: it shows what flows in and sends what is set.

    A subclass declares its types, its widget and, optionally, a settings bag
    that drives the widget's config. The node has two ports:

    - ``in``: an inlet with no widget. A value an edge brings is sent on from
      ``value``. When the edge goes, ``value`` keeps the last value.
    - ``value``: an outlet whose widget always shows. Last write wins, so a fed
      control is a display: a value set on it lasts until the next one arrives.

    Example::

        @node(label="Float Slider", menu="core/widgets/float_slider", node_type=NodeType.DATA)
        class FloatSliderNode(WidgetNode):
            value_type = FLOAT
            widget_key = SLIDER_WIDGET
            default_value = 0.0
            config_bag = "range"

            class range(NodeSettings):
                min = setting[FLOAT](0.0, label="Min")
                max = setting[FLOAT](1.0, label="Max")

            def _widget_properties(self) -> dict[str, Any]:
                return {"min": self.range.min, "max": self.range.max}
    """

    #: The type of ``value``, and of ``in`` unless ``inlet_type`` says otherwise.
    value_type: ClassVar[type[IType]]
    #: The type of ``in``; ``None`` takes ``value_type``.
    inlet_type: ClassVar[type[IType] | None] = None
    #: Registry key of the widget ``value`` shows.
    widget_key: ClassVar[str]
    #: The value ``value`` starts at.
    default_value: ClassVar[Any]
    #: Widget properties no setting drives.
    base_properties: ClassVar[dict[str, Any]] = {}
    #: Accessor of the settings bag whose fields drive the widget's config, or ``None``.
    config_bag: ClassVar[str | None] = None

    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        """Binds the widget-node skin on the stage."""

        # Bound by registry-key string: importing the skin would pull nicegui
        # onto the headless execution path.
        stage_skin = setting[CHOICES](
            WIDGET_NODE_SKIN,
            label="Stage Skin",
            description="Widget nodes draw as their control on the stage",
            category="appearance",
            order=11,
            widget_config={"options": _widget_node_stage_skin_choices},
        )

    class style(NodeSettings):
        """How the node looks on the stage: its label, its card, and where the label sits."""

        label_position = setting[CHOICES](
            "left",
            label="Label Position",
            description="Where the label sits: left of the control, above it, or not at all",
            category="layout",
            order=1,
            widget_config={"options": list(LABEL_POSITIONS)},
            promotable=_NONE,
        )
        max_label_width = setting[OPTIONAL[INT]](
            None,
            min=40,
            max=600,
            label="Max Label Width",
            description="The widest the label gets when it is on the left: it takes half the row up to "
            "this width. None is 9rem, as in the properties panel",
            category="layout",
            order=2,
            promotable=_NONE,
        )
        label_align = setting[CHOICES](
            "left",
            label="Label Alignment",
            category="layout",
            order=3,
            widget_config={"options": list(H_ALIGNS)},
            promotable=_NONE,
        )
        font = setting[CHOICES](
            "sans",
            label="Font",
            category="font",
            order=10,
            widget_config={"options": list(FONTS)},
            promotable=_NONE,
        )
        font_size = setting[INT](
            14,
            min=6,
            max=72,
            label="Text Size",
            description="Size of the label in pixels",
            category="font",
            order=11,
            promotable=_NONE,
        )
        bold = setting[BOOL](False, label="Bold", category="font", order=12, promotable=_NONE)
        italic = setting[BOOL](False, label="Italic", category="font", order=13, promotable=_NONE)
        label_color = setting[COLOR](
            "",
            label="Label Color",
            description="Empty uses the theme's text color",
            category="colors",
            order=20,
            promotable=_NONE,
        )
        background = setting[COLOR](
            "",
            label="Background",
            description="Fill behind the label and control; empty draws none",
            category="colors",
            order=21,
            promotable=_NONE,
        )
        border = setting[BOOL](
            False,
            label="Border",
            description="Draw the theme's node border around the card",
            category="colors",
            order=22,
            promotable=_NONE,
        )

    def init(self) -> None:
        inlet = self.inlet_type or self.value_type
        self.add(
            inlet.as_inlet("in", label="In", show_widget=ShowWidgetStrategy.NEVER, on_change="_forward")
        )
        properties = {**self.base_properties, **_present(self._widget_properties())}
        self.add(
            self.value_type.as_outlet(
                "value",
                label="Value",
                default=self.default_value,
                show_widget=ShowWidgetStrategy.ALWAYS,
                widget={"key": self.widget_key, "config": {"properties": properties}},
            )
        )

    def post_init(self) -> None:
        bag = self._config_settings()
        if bag is not None:
            for name in settings_fields(bag):
                bag._subscribe_field(name, self._on_config_setting)
        # The stage face draws every style field.
        style: Any = self.style
        for name in settings_fields(type(style)):
            style._subscribe_field(name, self._redraw_card)
        self._apply_widget_config()

    def _widget_properties(self) -> dict[str, Any]:
        """Return the widget properties the node's settings set now; a ``None`` value removes one."""
        return {}

    def _config_settings(self) -> Settings | None:
        return getattr(self, self.config_bag) if self.config_bag else None

    def _on_config_setting(self, _value: Any, _old: Any) -> None:
        self._apply_widget_config()

    def _redraw_card(self, _value: Any, _old: Any) -> None:
        if self.wrapper is not None:
            self.wrapper.redraw()

    def _apply_widget_config(self) -> None:
        port = self.ports["value"]
        for key, value in self._widget_properties().items():
            port.set_widget_config(key, value)

    def _forward(self, port: Any, value: Any) -> None:
        # Only an edge's value is sent on; the own value an unlink reveals is not.
        if port.data.has_linked_value():
            self.out("value", value)

    def worker(self, context: ExecutionContext) -> None:
        return None


def _present(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if value is not None}
