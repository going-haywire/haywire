"""Persisted-disabled-library state — file I/O.

Reads and writes the per-project list of library IDs that the user has
explicitly disabled. The file is ``<project>/.haywire/config.toml`` under
``[libraries].disabled`` — the same schema the studio used before the
haybale-marketplace carve-out (ADR-0001).

Two consumers:

* the **library system bootstrap** (``create_library_system_service``)
  reads the file between ``scan_for_libraries()`` and ``enable_all_libraries()``
  and disables the listed libraries before the enable phase runs.
* the **runtime UI write path** (``LibraryEnableState`` in
  ``haybale-marketplace``) calls ``write_disabled_ids`` when the user
  toggles a library on or off.

Keeping the read/write here — rather than on ``LibraryManager`` — means the
manager can move out of core without dragging the bootstrap-apply path
with it, and avoids the mid-bootstrap mutation cascade that owning
persistence on the manager would force.
"""

from __future__ import annotations

from pathlib import Path

import toml


def _config_file(project_dir: Path) -> Path:
    return project_dir / ".haywire" / "config.toml"


def read_disabled_ids(project_dir: Path) -> list[str]:
    """Return the explicitly disabled library IDs for ``project_dir``.

    Empty list if the file is missing or the section is absent.
    """
    config_file = _config_file(project_dir)
    if not config_file.exists():
        return []
    data = toml.loads(config_file.read_text())
    return data.get("libraries", {}).get("disabled", [])


def write_disabled_ids(project_dir: Path, disabled_ids: list[str]) -> None:
    """Persist the disabled library ID list to ``<project>/.haywire/config.toml``.

    The ``.haywire/`` directory and ``config.toml`` are created if absent.
    Other sections of the file are preserved verbatim.
    """
    haywire_dir = project_dir / ".haywire"
    haywire_dir.mkdir(exist_ok=True)
    config_file = haywire_dir / "config.toml"
    data: dict = toml.loads(config_file.read_text()) if config_file.exists() else {}
    data.setdefault("libraries", {})["disabled"] = sorted(disabled_ids)
    config_file.write_text(toml.dumps(data))
