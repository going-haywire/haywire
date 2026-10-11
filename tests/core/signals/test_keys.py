"""Key-combo normalization and display formatting."""

import pytest

from haywire.core.signals.keys import RESERVED_COMBOS, format_combo, normalize_combo


def test_normalize_uppercases_single_char_key_and_capitalizes_modifiers():
    assert normalize_combo("mod+shift+z") == "Mod+Shift+Z"


def test_normalize_orders_modifiers_canonically():
    assert normalize_combo("Shift+Mod+a") == "Mod+Shift+A"


def test_normalize_keeps_named_key_spelling():
    assert normalize_combo("Delete") == "Delete"


@pytest.mark.parametrize("bad", ["", "Mod+", "Hyper+A", "+"])
def test_normalize_rejects_malformed_combos(bad):
    with pytest.raises(ValueError, match="key combo"):
        normalize_combo(bad)


def test_format_mac_uses_glyphs():
    assert format_combo("Mod+Shift+Z", mac=True) == "⌘⇧Z"


def test_format_other_platforms_spells_ctrl():
    assert format_combo("Mod+Shift+Z", mac=False) == "Ctrl+Shift+Z"


def test_format_named_keys():
    assert format_combo("Delete", mac=True) == "Del"
    assert format_combo("Backspace", mac=True) == "⌫"
    assert format_combo("Backspace", mac=False) == "Backspace"


def test_reserved_combos_cover_browser_shortcuts():
    assert "Mod+W" in RESERVED_COMBOS
    assert "Mod+Shift+N" in RESERVED_COMBOS
