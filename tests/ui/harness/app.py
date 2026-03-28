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
from pathlib import Path

from nicegui import ui, app

from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector

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

    library_service = create_library_system_service(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=False,
        watch_settings=False,
    )
    set_library_system(library_service)
    set_global_injector(library_service.injector)

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
