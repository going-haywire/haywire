"""
HarnessApp — isolated NiceGUI app for settings UI development and testing.

Usage:
    uv run python tests/ui/harness/app.py

Runs on http://localhost:8090.

Routes:
    GET  /status               — liveness probe
    GET  /node?class=...&bag=  — render a NodeSettings bag
    GET  /schema?class=...     — render a LibrarySettings/FrameworkSettings schema
    POST /api/set?key=&value=  — write to SettingsRegistry (for test teardown)
"""

import os
import sys
import tempfile
from pathlib import Path

from nicegui import ui, app

from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector
from haywire.core.di.context import set_workspace_root

# Resolve barn/ relative to repo root (two levels up from tests/ui/harness/)
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent  # tests/ui/harness/app.py → repo root
_BARN = str(_REPO_ROOT / "barn")

# Ensure repo root is on sys.path so `tests.ui.harness.routes` is importable
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main():
    workspace_root = str(_REPO_ROOT)

    library_paths = [_BARN] if os.path.isdir(_BARN) else []

    # workspace_settings_path split from workspace_root: the harness needs the
    # REAL repo root for library discovery, but the workspace settings tier is
    # the one the app writes back to — a harness route that flips a
    # FrameworkSettings value (e.g. viewport culling) would otherwise persist
    # straight into the developer's own <repo>/.haywire/settings.json. See
    # .insights/project_tests_wrote_workspace_settings.md.
    workspace_settings_path = os.path.join(
        tempfile.mkdtemp(prefix="haywire-harness-settings-"), "settings.json"
    )

    library_service = create_library_system_service(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=False,
        watch_settings=False,
        workspace_settings_path=workspace_settings_path,
    )
    set_library_system(library_service)
    set_global_injector(library_service.injector)
    set_workspace_root(workspace_root)

    # Register routes (imports NiceGUI page decorators — must happen after library boot)
    from tests.ui.harness.routes import register_routes

    register_routes(library_service)

    app.on_shutdown(lambda: library_service.cleanup() if hasattr(library_service, "cleanup") else None)

    ui.run(
        port=8090,
        show=False,
        title="Haywire Settings Harness",
        reload=False,
    )


if __name__ == "__main__":
    main()
