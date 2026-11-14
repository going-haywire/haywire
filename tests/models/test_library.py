"""haybale-models library scaffold."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import entry_points


def test_library_is_discoverable():
    eps = {ep.name: ep for ep in entry_points(group="haywire.libraries")}
    assert eps["models"].value == "haybale_models:Library"
    assert eps["models"].load().__module__ == "haybale_models"


def test_import_without_torch():
    code = (
        "import sys, haybale_models, haybale_models.states.models_state;"
        "sys.exit(1 if 'torch' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
