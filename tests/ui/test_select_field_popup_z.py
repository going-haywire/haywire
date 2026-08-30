"""The overlay ladder — Popup vs. Quasar's interaction tier.

A Quasar QMenu (a dropdown, a context menu, a colour picker) hardcodes
``z-index: 6000``, and the haywire ``Popup`` card now renders *below* that at
``5001``. A menu opened inside a popup therefore clears the card on its own,
which is what lets a plain ``ui.context_menu()`` or ``ui.select`` work in a
popup with no lift and no wrapper.

``select_field(in_popup=)`` and ``POPUP_MENU_Z`` existed only because the Popup
used to sit at ``7001`` (bumped in d48f1161 to clear one ``ui.dialog()`` that
has since become a Popup itself). Both are gone; what remains is the ladder
itself and the one lift that still has a job — a dropdown body's content, which
must clear the dropdown because a dropdown *is* a QMenu.

See .insights/feedback_nicegui_nested_menu_flyouts.md (#2) for the original
diagnosis, and design-guide.md §2.9 for the ladder.
"""

from typing import Any, cast

import pytest
from nicegui import Client, ui
from nicegui import app as _app  # noqa: F401

from haywire.ui import elements as hui

pytestmark = pytest.mark.unit

_LIFT = "popup-content-style"


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _build(**kwargs) -> ui.select:
    """Build a select inside a headless client (the slot stack needs one)."""
    client = Client(cast(Any, _noop_page), request=None)
    with client, ui.column():
        return hui.select_field(**kwargs)


def test_a_select_never_lifts_itself() -> None:
    """A select carries no stacking of its own, anywhere. Inside a Popup its
    own 6000 already clears the card; inside a dropdown the *dropdown* lifts
    the whole body. An unconditional self-lift would let a panel's dropdown
    escape to <body> and float over overlays it should sit under."""
    select = _build(options=["a", "b"])

    assert _LIFT not in select._props


def test_shell_defines_the_overlay_ladder() -> None:
    """Every ``var(--hw-z-*)`` in the overlay tier is only meaningful if the
    shell injects it. The literal fallbacks cover pages rendered without the
    shell CSS (previews, tests)."""
    from pathlib import Path

    shell = Path("packages/haywire-core/src/haywire/ui/app/shell.py").read_text()
    assert "--hw-z-quasar-interaction:" in shell
    assert "--hw-z-popup:" in shell
    assert "--hw-z-menu-over-menu:" in shell


def test_the_popup_sits_below_quasars_interaction_tier() -> None:
    """The whole no-lift contract rests on this ordering: a QMenu (6000)
    opened inside a Popup must win over the card without any help, so a
    plain ``ui.context_menu()``/``ui.select`` works in a popup unaided.

    If someone raises the Popup above 6000 again, every menu inside a popup
    goes invisible and the per-site lift machinery comes back — that is the
    regression this guards (see design-guide.md §2.9)."""
    import re
    from pathlib import Path

    shell = Path("packages/haywire-core/src/haywire/ui/app/shell.py").read_text()
    values = {name: int(value) for name, value in re.findall(r"(--hw-z-[a-z-]+):\s*(\d+);", shell)}

    assert values["--hw-z-popup"] < values["--hw-z-quasar-interaction"]
    assert values["--hw-z-popup-backdrop"] < values["--hw-z-popup"]
    # A flyout is a QMenu inside a QMenu — it must clear the tier, not tie.
    assert values["--hw-z-menu-over-menu"] > values["--hw-z-quasar-interaction"]
    # Quasar's feedback tier (QTooltip 9000) stays above everything we draw.
    assert max(values.values()) < 9000


def test_select_field_keeps_the_standard_configuration() -> None:
    """Dropping the stacking parameter must not disturb the wrapper's chrome."""
    select = _build(options=["a"])

    assert select._props.get("dense")
    assert "text-sm" in select._classes
    assert "min-width" in select._style


def test_the_dropdown_lift_clears_the_dropdown_panel() -> None:
    """A dropdown body's lift must resolve ABOVE the dropdown's own rung.

    A ``hui.dropdown`` panel renders at ``--hw-z-menu-over-menu``; anything
    inside it that opens its own portal lands on the bare interaction tier
    *underneath* that panel unless lifted past it. Equal is not enough —
    a tie would leave the outcome to portal insertion order."""
    import re

    from haywire.ui.elements.flyout import _NESTED_POPUP_Z

    assert "--hw-z-menu-over-menu" in _NESTED_POPUP_Z
    fallback = re.search(r",\s*(\d+)\s*\)", _NESTED_POPUP_Z)
    assert fallback, f"expected a numeric fallback in {_NESTED_POPUP_Z!r}"
    # calc(<rung> + 1) — strictly above the panel, not tied with it.
    assert "+ 1" in _NESTED_POPUP_Z


def test_the_dropdown_lift_reaches_a_bare_context_menu() -> None:
    """``ui.context_menu()`` must be lifted alongside ``ui.menu``.

    ``ContextMenu`` is a *sibling* of ``Menu`` — both subclass ``Element``
    directly — so an ``isinstance(el, ui.menu)`` test misses every row menu.
    That is precisely how a settings row's right-click menu came to open
    behind the dropdown panel that spawned it."""
    from haywire.ui.elements.flyout import _lift_nested_popups

    assert not issubclass(ui.context_menu, ui.menu), (
        "ContextMenu is no longer a sibling of Menu — the lift's isinstance "
        "check can be simplified, but verify it still matches row menus."
    )

    client = Client(cast(Any, _noop_page), request=None)
    with client, ui.column() as body:
        menu = ui.context_menu()

    _lift_nested_popups(body)

    assert "z-index" in menu._style
