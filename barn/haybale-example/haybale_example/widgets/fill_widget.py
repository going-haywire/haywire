"""FillWidget — kind + angle + colour-stop editor for FILL ports.

Like :class:`VecWidget`, this edits a value whose parts change independently,
so it talks to the model through ``get_value()``/``set_value()`` rather than
``bind()``. Unlike VecWidget the value is a ``BaseType`` instance, and
``BaseField.set_value`` fires ``on_changed`` only when handed a *different*
instance — mutating the held FILL in place would update nothing. Every edit
therefore builds a new FILL (see ``_emit``).
"""

from typing import Any

from nicegui import ui

from haybale_example.types.fill import KINDS, LINEAR, RADIAL, SOLID, FILL
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

_KIND_LABELS = {SOLID: "Solid", LINEAR: "Linear", RADIAL: "Radial"}


@widget(description="Background fill editor (solid / linear / radial)")
class FillWidget(BaseWidget):
    """Editor for a :class:`FILL` — a solid colour or a gradient.

    Layout is kind-driven: the angle row belongs to ``linear`` alone, and the
    stop list is meaningless for ``solid`` (which reads only the first stop),
    so both are shown and hidden rather than redrawn — rebuilding the rows on
    every kind change would drop focus from whichever control triggered it.
    """

    def build(self) -> Any:
        with ui.column().classes("w-full gap-1") as root:
            # data-fill-* hooks: the widget stacks several Quasar controls, so
            # positional locators ("the first input") land on whichever happens
            # to render first — the kind select's own readonly combobox input.
            self._kind = (
                ui.select(
                    options=_KIND_LABELS,
                    value=self._fill().kind,
                    on_change=lambda e: self._on_kind(e.value),
                )
                .classes("w-full text-xs")
                .props("dense outlined hide-bottom-space data-fill-kind")
            )

            # The angle carries its own meaning through a "135°" suffix rather
            # than a label column: the row is already narrow, and a label plus a
            # spinner leaves no width for the number itself.
            self._angle_row = ui.row().classes("w-full items-center gap-1 no-wrap")
            self._angle_row.props("data-fill-angle-row")
            with self._angle_row:
                # ui.input for the same reason as the stop positions: a
                # `type=number` field carries the browser's own spinner, which
                # Quasar's hide-spin-buttons cannot reach from NiceGUI.
                self._angle = (
                    ui.input(
                        value=str(self._fill().angle),
                        on_change=lambda e: self._on_angle(e.value),
                    )
                    .classes("flex-1")
                    .props(
                        "dense outlined hide-bottom-space data-fill-angle "
                        'inputmode=numeric suffix="°" placeholder="angle"'
                    )
                )

            self._stops_box = ui.column().classes("w-full gap-1")
            self._stops_box.props("data-fill-stops")

        self._render_stops()
        self._sync_visibility()
        return root

    # -- model access --------------------------------------------------
    def _fill(self) -> FILL:
        """The current value, always a FILL (a fresh default if unset)."""
        value = self.get_value()
        return value if isinstance(value, FILL) else FILL()

    def _emit(self, **changes: Any) -> None:
        """Write a NEW FILL built from the current one plus *changes*.

        A new instance is required, not a nicety: ``BaseField.set_value``
        compares identity/typing and fires ``on_changed`` for the replacement.
        """
        current = self._fill()
        stops = changes.pop("stops", None)
        self.set_value(
            FILL(
                kind=changes.get("kind", current.kind),
                angle=changes.get("angle", current.angle),
                stops=[dict(s) for s in (stops if stops is not None else current.stops)],
            )
        )

    # -- handlers ------------------------------------------------------
    def _on_kind(self, value: Any) -> None:
        if value not in KINDS:
            return
        # A gradient needs somewhere to go: promote a lone stop to a pair the
        # first time solid becomes a gradient, so the editor opens on something
        # visibly gradient-like instead of a flat run.
        current = self._fill()
        stops = current.stops
        if value in (LINEAR, RADIAL) and len(stops) < 2:
            first = dict(stops[0]) if stops else {"color": "#1e1e1eff", "at": 0}
            stops = [{**first, "at": 0}, {**first, "at": 100}]
        self._emit(kind=value, stops=stops)
        self._sync_visibility()
        self._render_stops()

    def _on_angle(self, value: Any) -> None:
        try:
            self._emit(angle=int(value) % 360)
        except (TypeError, ValueError):
            return

    def _on_stop_color(self, index: int, value: Any) -> None:
        stops = [dict(s) for s in self._fill().stops]
        if 0 <= index < len(stops):
            stops[index]["color"] = value
            self._emit(stops=stops)
            # Repaint this stop's swatch in place. Re-rendering the rows would
            # do it too, but at the cost of the focus the user is holding.
            handles = self._pickers.get(index)
            if handles is not None:
                swatch, _picker = handles
                self._paint_swatch(swatch, value)

    def _on_stop_at(self, index: int, value: Any) -> None:
        stops = [dict(s) for s in self._fill().stops]
        if not (0 <= index < len(stops)):
            return
        try:
            stops[index]["at"] = max(0, min(int(value), 100))
        except (TypeError, ValueError):
            return
        self._emit(stops=stops)

    def _add_stop(self) -> None:
        stops = [dict(s) for s in self._fill().stops]
        last = stops[-1] if stops else {"color": "#1e1e1eff", "at": 0}
        stops.append({"color": last["color"], "at": 100})
        self._emit(stops=stops)
        self._render_stops()

    def _remove_stop(self, index: int) -> None:
        stops = [dict(s) for s in self._fill().stops]
        # One stop is the floor — a fill with no colour has nothing to render.
        if len(stops) <= 1 or not (0 <= index < len(stops)):
            return
        stops.pop(index)
        self._emit(stops=stops)
        self._render_stops()

    # -- rendering -----------------------------------------------------
    def _sync_visibility(self) -> None:
        """Angle belongs to ``linear`` alone; the stops are always shown.

        Solid reads the first stop, so hiding the list would leave a solid fill
        with no editable colour at all. What ``solid`` hides is the *rest* of
        the list — handled per-row in ``_render_stops``.
        """
        self._angle_row.set_visibility(self._fill().kind == LINEAR)

    @staticmethod
    def _paint_swatch(button: Any, color: Any) -> None:
        """Make *button* show *color* — the swatch IS the control.

        Styled rather than classed: a Tailwind arbitrary value (``!bg-[#fff]``)
        cannot express the checkerboard, and an ``#rrggbbaa`` colour needs one
        to read as translucent instead of merely darker. Quasar's round QBtn
        also floors at 42px, which its own rule wins unless overridden inline.

        The swatch is the row's *flexible* element: it takes whatever the fixed
        position box and remove button leave behind, so a wider panel gives a
        wider colour bar rather than more empty space. ``min-width: 0`` is what
        lets it shrink — a flex item's default ``min-width: auto`` floors it at
        its content, and Quasar's own 42px floor would otherwise win on narrow
        panels and push the row into overflow.
        """
        text = str(color or "").strip()
        if not text or any(ch in text for ch in ";{}\\"):
            return
        # Luminance decides the icon colour so it stays legible on a light or a
        # dark stop. Alpha is ignored for that decision — the checkerboard
        # behind it is mid-grey, so the composite lands near the opaque
        # colour's own brightness.
        icon = "black"
        if len(text) in (7, 9) and text.startswith("#"):
            try:
                r, g, b = (int(text[i : i + 2], 16) for i in (1, 3, 5))
                icon = "black" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "white"
            except ValueError:
                pass
        # The colour is a gradient layer of its own so it paints ON TOP of the
        # checkerboard: `background-color` sits behind every image layer, which
        # would hide the checks for an opaque colour and show them unblended
        # through a translucent one.
        button.style(
            "min-width: 28px; min-height: 24px; width: 28px; height: 24px;"
            "padding: 0; flex: 1 1 auto;"
            f"background-image: linear-gradient({text}, {text}),"
            " linear-gradient(45deg, #999 25%, transparent 25%, transparent 75%, #999 75%),"
            " linear-gradient(45deg, #999 25%, #ccc 25%, #ccc 75%, #999 75%);"
            "background-size: auto, 8px 8px, 8px 8px;"
            "background-position: 0 0, 0 0, 4px 4px;"
        ).props(f'color="{icon}"')

    def _render_stops(self) -> None:
        """Rebuild the stop rows. Only called when the stop *count* changes —
        editing a colour or position leaves the rows in place."""
        self._stops_box.clear()
        # Rebuilt rows mean new elements; the old picker handles are dead.
        self._pickers: dict[int, Any] = {}
        fill = self._fill()
        is_gradient = fill.kind in (LINEAR, RADIAL)
        with self._stops_box:
            for index, stop in enumerate(fill.stops):
                # Solid reads stop 0 and nothing else: show that one as a plain
                # colour, and keep the rest in the model (so switching back to a
                # gradient restores them) without cluttering the panel.
                row = ui.row().classes("w-full items-center gap-1 no-wrap")
                row.props(f'data-fill-stop="{index}"')
                if index > 0 and not is_gradient:
                    row.set_visibility(False)
                with row:
                    # The swatch IS the control: a bare picker hung off a button
                    # rather than a QInput carrying one in its append slot. The
                    # hex text was never worth its width here — the colour is
                    # legible at a glance, and the picker's own popup has a text
                    # field for anyone who wants to type one.
                    color = stop.get("color", "#1e1e1eff")
                    swatch = ui.button(icon="colorize").props(f'flat dense data-fill-stop-color="{index}"')
                    with swatch:
                        picker = ui.color_picker(on_pick=lambda e, i=index: self._on_stop_color(i, e.color))
                    picker.q_color.props("format-model=hexa")
                    picker.set_color(color)
                    self._paint_swatch(swatch, color)
                    self._pickers[index] = (swatch, picker)
                    # Position and removal are gradient-only concerns.
                    #
                    # No spinner, no "%" suffix. Both are laid out ahead of the
                    # native input inside a dense QInput, and between them they
                    # left ~17px for the digits — the number was clipped to
                    # nothing at this width. The unit rides in the placeholder,
                    # which costs no space once a value is present.
                    # ui.input, not ui.number: the arrows are the BROWSER's
                    # spinner for `type=number`, and Quasar's `hide-spin-buttons`
                    # does not reach them (NiceGUI puts it on the <input> as a
                    # plain attribute, which the browser ignores). A text input
                    # with `inputmode=numeric` has no spinner to hide, and
                    # _on_stop_at already parses and clamps whatever arrives.
                    at = (
                        ui.input(
                            value=str(stop.get("at", 0)),
                            on_change=lambda e, i=index: self._on_stop_at(i, e.value),
                        )
                        # grow-0 as well as shrink-0: the swatch is the only
                        # element allowed to absorb the row's spare width, so
                        # every sibling has to be pinned at its own size.
                        .classes("w-12 shrink-0 grow-0")
                        .props(
                            "dense inputmode=numeric "
                            'placeholder="%" input-class="text-center" data-fill-stop-at'
                        )
                    )
                    at.set_visibility(is_gradient)
                    remove = (
                        ui.button(icon="close", on_click=lambda _, i=index: self._remove_stop(i))
                        .classes("shrink-0 grow-0")
                        .props("flat dense size=xs")
                    )
                    remove.set_visibility(is_gradient and len(fill.stops) > 1)
            add = (
                ui.button("Add stop", icon="add", on_click=lambda _: self._add_stop())
                .props("flat dense size=sm data-fill-add-stop")
                .classes("self-start")
            )
            add.set_visibility(is_gradient)

    def on_model_changed(self, value: Any) -> None:
        """Sync view from an external write (another panel, a reset).

        Guarded on each control's current value so a write this widget just
        emitted does not bounce back and steal focus from the control that
        produced it.
        """
        if not isinstance(value, FILL):
            return
        if self._kind.value != value.kind:
            self._kind.value = value.kind
            self._sync_visibility()
        # The angle field is a text input, so compare as text — an int/str
        # mismatch here would rewrite the field on every model change and take
        # the caret with it.
        if str(self._angle.value) != str(value.angle):
            self._angle.value = str(value.angle)
