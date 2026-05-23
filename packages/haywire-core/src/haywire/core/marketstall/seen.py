"""seen.toml tracker — spec §7.4 first-install scoping.

Records which haybale names the user has previously seen-and-installed on
this machine. Used by the Library Overview Editor's Install button to decide
whether to show the first-install safety modal.

File lives at ~/.haywire/db/haybale-marketplace/seen.toml. Schema:

    seen = ["haybale-foo", "haybale-bar"]

Per spec §7.4: scoped per-haybale-name (not per-version, not per-source).
Reinstall of a previously-installed-and-uninstalled haybale skips the modal
(the user already decided once).
"""

from __future__ import annotations

from pathlib import Path

import toml


def _default_seen_path() -> Path:
    """Production seen.toml location: ~/.haywire/db/haybale-marketplace/seen.toml."""
    return Path.home() / ".haywire" / "db" / "haybale-marketplace" / "seen.toml"


def _load(seen_path: Path) -> list[str]:
    """Return the seen list, or [] if file missing or malformed (fail closed)."""
    if not seen_path.is_file():
        return []
    try:
        data = toml.loads(seen_path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError:
        return []
    seen = data.get("seen", [])
    if not isinstance(seen, list):
        return []
    return [s for s in seen if isinstance(s, str)]


def is_seen(name: str, *, seen_path: Path | None = None) -> bool:
    """True if `name` has been previously marked as seen on this machine."""
    path = seen_path if seen_path is not None else _default_seen_path()
    return name in _load(path)


def mark_seen(name: str, *, seen_path: Path | None = None) -> None:
    """Append `name` to the seen list. Idempotent (no duplicates)."""
    path = seen_path if seen_path is not None else _default_seen_path()
    seen = _load(path)
    if name in seen:
        return
    seen.append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(toml.dumps({"seen": seen}), encoding="utf-8")
