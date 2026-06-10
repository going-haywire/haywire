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
                with hui.expansion_section("Details", state=layout.state_bag,
                                           panel_key="details"):
                    hui.info_row("Key", node.registry_key)

    The optional ``state_bag`` dict (passed at construction) is the host's
    persistence mechanism for panel UI state (collapsed sections, scroll
    position, form selections, etc.). The owning editor holds it as an
    instance field so UI state survives rebuilds without leaking into
    shared session state. Panels read from and write to this dict via
    UI components. Hosts that construct a transient layout (e.g. context-menu
    popups) leave it ``None`` — UI state doesn't persist for ephemeral panels,
    which is correct.
    """

    def __init__(self, container: Any, *, state_bag: dict[str, Any] | None = None):
        self._container = container
        self._state_bag = state_bag

    @property
    def container(self) -> Any:
        """The underlying NiceGUI container element."""
        return self._container

    @property
    def state_bag(self) -> dict[str, Any] | None:
        """Host-owned dict for panel UI state persistence.

        Use namespaced keys to avoid collisions across panels:
        - "expansion:my_section"
        - "scroll:my_container"
        - "tab:active_tab"

        ``None`` when the host constructed a transient layout (ephemeral).
        """
        return self._state_bag

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._container.__enter__()
        return self

    def __exit__(self, *args):
        return self._container.__exit__(*args)
