# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py
"""
Pin context-menu panels — the surface ``PinMenu``.

Reached structurally now: the canvas detects a pin from ``data-pin-id``,
which ``render_pin`` emits on every pin from every skin, so every skin gains
this menu and none can suppress it. Every panel below is safe under that:
the "Edit…" rows are read-only navigation, and the removal verb polls true
only on a pin the user added.

"Edit…" holds the components behind the pin — its data type, and the widget
editing its value — and the selection menu carries the same submenu over its
own subjects, so one gesture answers "what is this made of" everywhere. See
``..component_rows`` for why those rows are not gated on developer mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from haywire.core.types.enums import PortOrigin, ShowWidgetStrategy

from ..component_rows import component_row, identity_of, key_and_label
from .....surfaces import PinEditMenu, PinMenu, PinWidgetMenu, PortActions
from .....state.edit_state import EditState


if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _type_identity(ctx: "SessionContext") -> Any | None:
    """The identity of the active pin's data type, or None."""
    port = ctx.data[EditState].active_port
    if port is None:
        return None
    return identity_of(port.stored_type)


def _widget_identity(ctx: "SessionContext") -> Any | None:
    """The identity of the widget editing the active pin, or None.

    ``widget_key`` is resolved through the global widget registry rather than
    trusted: a key naming a widget that is not installed resolves to None, as
    does a port with no widget at all (an outlet, or an inlet whose type
    carries no editor).
    """
    from haywire.ui.widget.globals import get_widget_class

    port = ctx.data[EditState].active_port
    if port is None or not port.widget_key:
        return None
    return identity_of(get_widget_class(port.widget_key))


@panel(
    surface=PinMenu,
    hosts=(PinEditMenu,),
    label="Edit",
    icon=hui.icon.node_source,
    order=10,
)
class PinEditMenuPanel(BasePanel):
    """The "Edit…" row — a submenu over the components behind this pin.

    It draws the row and the flyout, and pipes the ``PortActions`` host
    one hop further to the rows inside.
    """

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _type_identity(ctx) is not None or _widget_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Edit", icon=hui.icon.node_source):
                self.render_surface(PinEditMenu, ctx)


@panel(
    surface=PinEditMenu,
    label="Type",
    icon=hui.icon.type,
    order=10,
)
class PortTypeMenuPanel(BasePanel):
    """The pin's data type, as a row that opens the type's source."""

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _type_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        port = ctx.data[EditState].active_port
        fallback = getattr(port.stored_type, "__name__", "") if port is not None else ""
        key, label = key_and_label(_type_identity(ctx), fallback)
        with layout:
            component_row(ctx, label, key, hui.icon.type)


@panel(
    surface=PinEditMenu,
    label="Widget",
    icon=hui.icon.widget,
    order=20,
)
class PortWidgetMenuPanel(BasePanel):
    """The widget editing this pin, as a row that opens the widget's source.

    Polls false on a port with no widget, so the row never advertises a
    component that isn't there.
    """

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _widget_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        key, label = key_and_label(_widget_identity(ctx))
        with layout:
            component_row(ctx, label, key, hui.icon.widget)


def _promoted_setting(ctx: "SessionContext"):
    """The (bag, descriptor) behind the active pin, or ``None``.

    ``None`` for an unpromoted pin, a pin with no node, or one matching no
    setting — a library changed under a saved graph. Every value verb below
    polls through this, so none of them can act on a pin that has no field.
    """
    state = ctx.data[EditState]
    port, wrapper = state.active_port, state.active_node
    if port is None or wrapper is None or not port.promoted:
        return None
    try:
        from haywire.core.node.promotion import _resolve_promoted

        return _resolve_promoted(wrapper.node, port.id)
    except KeyError:
        return None


@panel(
    surface=PinMenu,
    label="Reset to default",
    icon=hui.icon.undo,
    order=15,
)
class ResetSettingMenuPanel(BasePanel):
    """Put the backing setting back to its declared default, from the pin.

    The Properties row has offered this all along; the pin had not, which was
    a real gap once a promoted pin can carry its own editable widget: a value
    typed into the widget on the card could only be undone somewhere else.

    Greyed rather than hidden on a clean or unpromoted pin — the convention
    every panel on this surface follows, and load-bearing here for the same
    reason ``DetachSettingMenuPanel`` documents: this surface needs at least
    one leaf or the popup is deleted entirely.
    """

    actions: PortActions

    _LABEL = "Reset to default"

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        resolved = _promoted_setting(ctx)
        if resolved is None:
            return False
        bag, descriptor = resolved
        # Enabled only where it would DO something — the same "transient facts
        # disable" rule the settings row applies to its own Reset.
        return bag._is_locally_set(descriptor._attr_name)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.undo,
                on_click=lambda pid=port.id: self.actions.reset_setting(pid),
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.undo,
                enabled=False,
                tooltip="Only a promoted setting holding its own value can be reset",
            )


@panel(
    surface=PinMenu,
    label="Set to none",
    icon=hui.icon.close,
    order=16,
)
class ClearSettingMenuPanel(BasePanel):
    """Clear the backing setting to ABSENCE — ``OPTIONAL[T]`` fields only.

    Distinct from Reset wherever the declared default is itself a value: Reset
    goes back to that value, this goes to "pass nothing". On a field whose
    default is already absence the two land in the same place, and both are
    still listed, because Reset greys when the field is clean and this one
    does not — which is exactly the state a user reaches by editing the pin's
    own widget.
    """

    actions: PortActions

    _LABEL = "Set to none"

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        resolved = _promoted_setting(ctx)
        if resolved is None:
            return False
        bag, descriptor = resolved
        if not descriptor._is_wrapper_type():
            return False
        # Nothing left to do once the value already IS absent.
        return getattr(bag, descriptor._attr_name) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.close,
                tooltip="Clear the value — pass nothing",
                on_click=lambda pid=port.id: self.actions.clear_setting(pid),
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.close,
                enabled=False,
                tooltip="Only an optional setting holding a value can be cleared",
            )


@panel(
    surface=PinMenu,
    label="Detach from setting",
    icon=hui.icon.delete,
    order=30,
)
class DetachSettingMenuPanel(BasePanel):
    """Removes a pin the user added, on the pin that carries it.

    One row for both kinds of user-created pin, reading "Detach from setting"
    on a promoted one and "Remove pin" on a slot resolved from an ``ANY``
    placeholder — the same act either way, since the user added the pin by a
    gesture and takes it away by one.
    """

    actions: PortActions

    #: Row label per origin. A declared pin cannot be removed, so its label is
    #: the one the greyed row carries.
    _LABELS = {
        PortOrigin.PROMOTED: "Detach from setting",
        PortOrigin.RESOLVED: "Remove pin",
        PortOrigin.DECLARED: "Remove pin",
    }

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        port = ctx.data[EditState].active_port
        return port is not None and port.is_user_removable()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout:
            hui.menu_row(
                self._LABELS[port.origin],
                icon=hui.icon.delete,
                on_click=lambda: self.actions.remove_port(port.id),
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The greyed form, on a pin the node's author declared."""
        port = ctx.data[EditState].active_port
        label = self._LABELS[port.origin] if port is not None else "Remove pin"
        with layout:
            hui.menu_row(
                label,
                icon=hui.icon.delete,
                enabled=False,
                tooltip=(
                    "Only a pin you added — promoted from a setting, or "
                    "resolved from an Any pin — can be removed"
                ),
            )


@panel(
    surface=PinMenu,
    hosts=(PinWidgetMenu,),
    label="Show widget",
    icon=hui.icon.widget,
    order=40,
)
class PinShowWidgetMenuPanel(BasePanel):
    """The "Show widget ▸" row — picks when this pin's Widget is rendered.

    A hosting panel over ``PinWidgetMenu``, mirroring ``PinEditMenuPanel``.
    Offered on **promoted** pins only

    Greys rather than vanishing on an unpromoted pin
    """

    actions: PortActions

    _LABEL = "Show widget"

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        port = ctx.data[EditState].active_port
        return port is not None and port.promoted

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row(self._LABEL, icon=hui.icon.widget):
                self.render_surface(PinWidgetMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The greyed form, on a pin that was never promoted."""
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.widget,
                enabled=False,
                tooltip="Only a promoted pin's widget visibility is the user's to set",
            )


@panel(
    surface=PinWidgetMenu,
    label="Strategy",
    icon=hui.icon.widget,
    order=10,
)
class PortShowWidgetStrategyPanel(BasePanel):
    """One row per ``ShowWidgetStrategy``, radio-marked with the port's current
    choice.

    The rows are mutually exclusive, hence ``radio_checked``/``radio_unchecked``
    rather than the checkbox pair.
    """

    actions: PortActions

    #: Rendered top-to-bottom. Labels are user-facing prose, not enum names —
    #: the enum's own spelling ("not_linked") is an implementation detail.
    _CHOICES: tuple[tuple[ShowWidgetStrategy, str], ...] = (
        (ShowWidgetStrategy.ALWAYS, "Always"),
        (ShowWidgetStrategy.NOT_LINKED, "When not connected"),
        (ShowWidgetStrategy.WHEN_LINKED, "When connected"),
        (ShowWidgetStrategy.NEVER, "Never"),
    )

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        current = port.show_widget
        with layout:
            for strategy, label in self._CHOICES:
                hui.menu_row(
                    label,
                    icon=(hui.icon.radio_checked if strategy is current else hui.icon.radio_unchecked),
                    on_click=(
                        lambda pid=port.id, value=strategy.value: self.actions.set_port_show_widget(
                            pid, value
                        )
                    ),
                )
