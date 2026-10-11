"""Key-combo strings: the canonical spelling, display formatting, browser-reserved combos.

A combo is ``+``-joined modifiers followed by one key, e.g. ``Mod+Shift+Z``.
``Mod`` is the platform command key (Cmd on macOS, Ctrl elsewhere); ``Ctrl``
is the physical Control key on macOS. Canonical order is ``Mod``, ``Ctrl``,
``Alt``, ``Shift``, then the key. A single-character key is upper-cased; a
named key keeps its ``KeyboardEvent.key`` spelling (``Delete``, ``Escape``).
"""

from __future__ import annotations

_MODIFIER_ORDER: tuple[str, ...] = ("Mod", "Ctrl", "Alt", "Shift")
_MODIFIERS: dict[str, str] = {m.lower(): m for m in _MODIFIER_ORDER}

_NAMED_KEYS: dict[str, str] = {
    k.lower(): k
    for k in (
        "Delete",
        "Backspace",
        "Escape",
        "Enter",
        "Tab",
        "Space",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
    )
}

_MAC_GLYPHS: dict[str, str] = {"Mod": "⌘", "Ctrl": "⌃", "Alt": "⌥", "Shift": "⇧"}
_MAC_KEYS: dict[str, str] = {"Delete": "Del", "Backspace": "⌫"}
_OTHER_KEYS: dict[str, str] = {"Delete": "Del"}

# Combos the browser handles before the page sees them; binding one never works.
RESERVED_COMBOS: frozenset[str] = frozenset(
    {
        "Mod+W",
        "Mod+T",
        "Mod+N",
        "Mod+Q",
        "Mod+Shift+N",
        "Mod+Shift+T",
        "Mod+Shift+W",
    }
)


def normalize_combo(combo: str) -> str:
    """Return ``combo`` in canonical spelling, e.g. ``"shift+mod+z"`` -> ``"Mod+Shift+Z"``.

    Raises:
        ValueError: If ``combo`` is empty, has an empty segment (``"Mod+"``),
            repeats a modifier, or has no key after its modifiers.
    """
    parts = combo.split("+")
    if any(not p for p in parts):
        raise ValueError(f"Malformed key combo {combo!r}")
    *mods, key = parts
    seen: set[str] = set()
    for raw in mods:
        canonical = _MODIFIERS.get(raw.lower())
        if canonical is None:
            raise ValueError(f"Unknown modifier {raw!r} in key combo {combo!r}")
        if canonical in seen:
            raise ValueError(f"Repeated modifier {canonical!r} in key combo {combo!r}")
        seen.add(canonical)
    if key.lower() in _MODIFIERS:
        raise ValueError(f"Key combo {combo!r} has no key after its modifiers")
    if len(key) == 1:
        key = key.upper()
    else:
        key = _NAMED_KEYS.get(key.lower(), key)
    return "+".join([m for m in _MODIFIER_ORDER if m in seen] + [key])


def format_combo(combo: str, *, mac: bool) -> str:
    """Return ``combo`` as a display string: ``⌘⇧Z`` on macOS, ``Ctrl+Shift+Z`` elsewhere."""
    *mods, key = normalize_combo(combo).split("+")
    if mac:
        return "".join(_MAC_GLYPHS[m] for m in mods) + _MAC_KEYS.get(key, key)
    return "+".join(["Ctrl" if m == "Mod" else m for m in mods] + [_OTHER_KEYS.get(key, key)])
