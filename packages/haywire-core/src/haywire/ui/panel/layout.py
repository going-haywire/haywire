# packages/haywire-core/src/haywire/ui/panel/layout.py
"""PanelLayout — the container handle passed to BasePanel.draw()."""

from typing import Any


class PanelLayout:
    """
    Container handle passed to panel ``draw()`` methods.

    ``PanelLayout`` is **not** a façade over ``hui``. It is the panel's
    container bound as a context manager. Panels activate it and call
    ``hui.*`` functions directly — ``hui`` is the single rendering
    vocabulary (see ``docs/reference/design-guide.md`` §8)::

        def draw(self, ctx, layout):
            with layout:
                hui.section_label("PORTS")
                hui.info_row("Inlet", "Image")
                with hui.expansion_section("Details", state=layout.expansion_state,
                                           panel_key="details"):
                    hui.info_row("Key", node.registry_key)

    The optional ``expansion_state`` dict (passed at construction) is the
    persistence bag for ``hui.expansion_section``. The owning editor holds
    it as an instance field so collapsed/expanded sections survive rebuilds
    without leaking into shared session state; pass it through via
    ``layout.expansion_state``. Hosts that construct a transient layout
    (e.g. context-menu popups) leave it ``None`` — expansion is then
    non-persistent, which is correct for ephemeral popups.
    """

    def __init__(self, container: Any, *, expansion_state: dict[str, bool] | None = None):
        self._container = container
        self._expansion_state = expansion_state

    @property
    def container(self) -> Any:
        """The underlying NiceGUI container element."""
        return self._container

    @property
    def expansion_state(self) -> dict[str, bool] | None:
        """Caller-owned persistence bag for ``hui.expansion_section``.

        ``None`` when the host constructed a transient layout. Pass it
        straight to ``hui.expansion_section(..., state=layout.expansion_state)``.
        """
        return self._expansion_state

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._container.__enter__()
        return self

    def __exit__(self, *args):
        return self._container.__exit__(*args)
