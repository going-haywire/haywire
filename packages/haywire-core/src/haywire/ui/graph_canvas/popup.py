from nicegui import ui
from typing import Optional, Callable


class Popup(ui.element, component="popup.vue"):
    """
    A draggable, positionable popup built as a Vue SFC.

    Usage (context-manager):
        popup = Popup(title="My Popup", closable=True, position_x=200, position_y=150)
        with popup:
            ui.label("Hello")
        popup.open()

    The Vue component owns all position/drag state; Python is a thin wrapper
    that forwards calls via run_method() and props.
    """

    def __init__(
        self,
        title: Optional[str] = None,
        width: str = "auto",
        height: str = "auto",
        closable: bool = False,
        backdrop_click_close: bool = False,
        escape_close: bool = False,
        backdrop_color: str = "var(--hw-bg-overlay)",
        position_x: Optional[float] = None,
        position_y: Optional[float] = None,
        draggable: bool = False,
        clamp_to_viewport: bool = False,
    ):
        # Attach to the page layout so the element is in the DOM even when
        # instantiated dynamically inside an event handler (where the slot
        # stack is empty).
        with ui.context.client.layout:
            super().__init__()

        self._on_close_callback: Optional[Callable] = None
        self._escape_close = escape_close
        self._is_open = False

        # Push all config as Vue props
        self._props["title"] = title
        self._props["popup-width"] = width
        self._props["popup-height"] = height
        self._props["closable"] = closable
        self._props["backdrop-click-close"] = backdrop_click_close
        self._props["backdrop-color"] = backdrop_color
        self._props["initial-x"] = position_x
        self._props["initial-y"] = position_y
        self._props["draggable"] = draggable
        self._props["clamp-to-viewport"] = clamp_to_viewport
        self._props["start-visible"] = False

        # Listen for close/position events emitted by the Vue component
        self.on("popup-close", self._handle_vue_close)
        self.on("popup-position-update", self._handle_position_update)

        # Content column lives inside the Vue default slot.
        # Use the slot directly here (not __enter__) to avoid the chicken-and-egg
        # problem where __enter__ references self._content before it is assigned.
        with self.default_slot:
            self._content = ui.column().classes("hw-popup-content-col w-full")

    # ------------------------------------------------------------------
    # Context manager — children go into the content column
    # ------------------------------------------------------------------

    def __enter__(self):
        return self._content.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        result = self._content.__exit__(exc_type, exc_val, exc_tb)
        if self._escape_close:
            ui.keyboard(self._handle_escape_key)
        return result

    # ------------------------------------------------------------------
    # Public API (mirrors old Popup)
    # ------------------------------------------------------------------

    def open(self):
        if not self._is_open:
            self._is_open = True
            self.run_method("open")

    def close(self):
        if self._is_open:
            self._is_open = False
            self.run_method("close")
            if self._on_close_callback:
                self._on_close_callback()

    def toggle(self):
        self.run_method("toggle")
        self._is_open = not self._is_open

    def delete(self):
        self._is_open = False
        super().delete()

    def on_close(self, callback: Callable) -> "Popup":
        self._on_close_callback = callback
        return self

    @property
    def is_open(self) -> bool:
        return self._is_open

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------

    def _handle_vue_close(self, _e):
        """Vue emitted 'popup-close' (user clicked X or backdrop)."""
        self._is_open = False
        if self._on_close_callback:
            self._on_close_callback()

    def _handle_position_update(self, e):
        """Vue emitted final drag position."""
        if e.args:
            self._props["initial-x"] = e.args.get("x", self._props.get("initial-x"))
            self._props["initial-y"] = e.args.get("y", self._props.get("initial-y"))

    def _handle_escape_key(self, e):
        if e.key == "Escape" and self._is_open:
            self.close()

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @classmethod
    def create_context_menu(cls, title: str, x: float, y: float, **kwargs) -> "Popup":
        defaults = {
            "width": "auto",
            "height": "auto",
            "backdrop_click_close": True,
            "backdrop_color": "transparent",
            "closable": True,
            "draggable": True,
            "clamp_to_viewport": True,
        }
        config = {**defaults, **kwargs}
        return cls(title=title, position_x=x, position_y=y, **config)


if __name__ in {"__main__", "__mp_main__"}:

    def show_clamped_popup():
        popup = Popup(
            title="Clamped Popup",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
            draggable=True,
            position_x=200,
            position_y=150,
            clamp_to_viewport=True,
        )
        with popup:
            ui.label("This popup is clamped to the viewport")
            ui.label("Try dragging it — it won't go outside the window")
        popup.open()

    def show_unclamped_popup():
        popup = Popup(
            title="Unclamped Popup",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
            draggable=True,
            position_x=200,
            position_y=150,
            clamp_to_viewport=False,
        )
        with popup:
            ui.label("This popup is NOT clamped to the viewport")
            ui.label("You can drag it outside the window boundaries")
        popup.open()

    ui.label("Popup Vue Component Test").classes("text-2xl font-bold")
    ui.button("Open Clamped Popup", on_click=show_clamped_popup).classes("mt-4")
    ui.button("Open Unclamped Popup", on_click=show_unclamped_popup).classes("mt-2")

    ui.run()
