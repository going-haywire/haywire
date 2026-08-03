"""``hui.select_field(in_popup=...)`` — the Quasar-overlay stacking contract.

A Quasar QMenu (the dropdown panel) defaults to ``z-index: 6000``. The haywire
``Popup`` card renders at ``7001``. A select inside a popup therefore opens its
option list *behind* the card, where it is invisible and unclickable — the
select looks empty. See .insights/feedback_nicegui_nested_menu_flyouts.md (#2).

The lift is opt-in rather than always-on because the QMenu teleports to
``<body>``: lifting unconditionally would let the dropdown of a panel or node
widget sitting *behind* a popup float above that popup.
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


def test_default_select_does_not_lift_its_dropdown() -> None:
    """Panels and node widgets must keep Quasar's default stacking — their
    dropdowns have to stay behind an open Popup, not punch through it."""
    select = _build(options=["a", "b"])

    assert _LIFT not in select._props


def test_in_popup_select_lifts_its_dropdown_above_the_popup_card() -> None:
    select = _build(options=["a", "b"], in_popup=True)

    assert select._props[_LIFT] == f"z-index: {hui.POPUP_MENU_Z}"


def test_the_lift_clears_the_popup_card() -> None:
    """The token must resolve above the card (7001), not merely above the
    QMenu default (6000) — a value between the two still renders behind."""
    import re

    fallback = re.search(r",\s*(\d+)\s*\)", hui.POPUP_MENU_Z)
    assert fallback, f"expected a numeric fallback in {hui.POPUP_MENU_Z!r}"
    assert int(fallback.group(1)) > 7001


def test_shell_defines_the_z_tokens_the_lift_refers_to() -> None:
    """``var(--hw-z-popup-menu)`` is only meaningful if the shell injects it.
    The literal fallback covers pages rendered without the shell CSS."""
    from pathlib import Path

    shell = Path("packages/haywire-core/src/haywire/ui/app/shell.py").read_text()
    assert "--hw-z-popup-menu:" in shell
    assert "--hw-z-popup:" in shell


def test_in_popup_keeps_the_standard_select_configuration() -> None:
    """The lift is additive — it must not drop dense/text-sm/min-width."""
    select = _build(options=["a"], in_popup=True)

    assert select._props.get("dense")
    assert "text-sm" in select._classes
    assert "min-width" in select._style
