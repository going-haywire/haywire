"""Persisted enable/disable state for libraries — as a FrameworkSettings.

Replaces the bespoke ``disabled_state_io.py`` round-trip in favour of the
framework's existing settings registry. ``LibraryEnableSettings`` is a
``FrameworkSettings`` (auto-registered at ``SettingsRegistry.__init__``
via the ``_pending_global`` queue), so its schema is available **before**
the library system enables any library — which is the timing the
bootstrap-apply path in ``create_library_system_service`` requires.

Two consumers:

* the **library system bootstrap** reads ``LibraryEnableSettings().disabled``
  between ``scan_for_libraries()`` and ``enable_all_libraries()`` to
  disable the listed libraries before the enable phase runs.
* the **runtime UI write path** (``LibraryEnableState`` in
  ``haybale-marketplace``) reassigns ``settings.disabled`` whenever the
  user toggles a library, and the registry persists it to
  ``<workspace>/.haywire/settings.toml`` via the standard debounced save.

No panel renders this schema. Settings panels in the codebase are
explicit (each ``*SettingsPanel`` hard-codes the schema it surfaces);
since nothing calls ``render_schema(LibraryEnableSettings, …)``, the
field is hidden from any user-facing UI by construction.

See ADR-0001 for the carve-out context that motivated moving persistence
off ``LibraryManager`` in the first place.
"""

from __future__ import annotations

from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings


class LibraryEnableSettings(FrameworkSettings, namespace="libraries"):
    """Workspace-tier list of library IDs the user has explicitly disabled."""

    disabled = setting[list](
        [],
        label="Disabled libraries",
        description=(
            "Library IDs the user has explicitly disabled. Honored at startup; "
            "the listed libraries skip the enable phase."
        ),
        category="libraries",
        order=10,
    )
