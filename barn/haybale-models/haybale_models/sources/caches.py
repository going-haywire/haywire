"""The built-in cache sources: where torch hub, rembg, Keras and Ultralytics keep their model files.

Each ``*_dir`` function returns the absolute folder the framework itself would use on this
machine, read from environment variables and files only; no framework is imported.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from haybale_models.sources.folder import FolderSource, TorchHubSource

if TYPE_CHECKING:
    from haybale_models.store.records import FetchRecords


def _absolute(text: str | Path) -> Path:
    """Return ``text`` as an absolute path, expanding ``~`` when it can be resolved.

    An unresolvable ``~user`` or a missing home directory keeps the ``~`` as a literal segment.
    """
    path = Path(text)
    try:
        path = path.expanduser()
    except RuntimeError:
        pass
    return path.absolute()


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


def torchhub_dir() -> Path:
    """The torch hub checkpoint folder: ``<torch home>/hub/checkpoints``."""
    torch_home = _env("TORCH_HOME")
    if torch_home is None:
        torch_home = str(_absolute(_env("XDG_CACHE_HOME") or "~/.cache") / "torch")
    return _absolute(torch_home) / "hub" / "checkpoints"


def rembg_dir() -> Path:
    """The rembg model folder.

    ``U2NET_HOME`` wins, then ``REMBG_HOME``. Otherwise the current default home
    (``$XDG_DATA_HOME/rembg`` or ``~/.rembg``) when it exists, else the flat ``~/.u2net`` folder
    that older rembg versions write and current ones still read.
    """
    legacy = _absolute(_env("U2NET_HOME") or Path(_env("XDG_DATA_HOME") or "~") / ".u2net")
    if _env("U2NET_HOME"):
        return legacy
    if _env("REMBG_HOME"):
        return _absolute(os.environ["REMBG_HOME"])
    xdg = _env("XDG_DATA_HOME")
    current = _absolute(Path(xdg) / "rembg" if xdg else "~/.rembg")
    return current if current.is_dir() else legacy


def keras_dir() -> Path:
    """The Keras application weights folder: ``<keras home>/models``."""
    return _absolute(_env("KERAS_HOME") or "~/.keras") / "models"


def _ultralytics_config_dir() -> Path:
    override = _env("YOLO_CONFIG_DIR")
    if override:
        return _absolute(override) / "Ultralytics"
    if sys.platform == "win32":
        return _absolute("~/AppData/Roaming") / "Ultralytics"
    if sys.platform == "darwin":
        return _absolute("~/Library/Application Support") / "Ultralytics"
    return _absolute(_env("XDG_CONFIG_HOME") or "~/.config") / "Ultralytics"


def ultralytics_dir() -> Path:
    """The Ultralytics weights folder: ``weights_dir`` of its ``settings.json``.

    Without the file or the key (or when it is unreadable), ``weights`` in the config dir
    (``<config dir>/weights``). This is a Haywire choice: Ultralytics' own default is
    ``<git root or cwd>/weights``, which would move with every launch of the studio.
    """
    config_dir = _ultralytics_config_dir()
    try:
        data = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
        weights = data["weights_dir"]
    except (OSError, ValueError, KeyError, TypeError):
        weights = None
    if isinstance(weights, str) and weights:
        return _absolute(weights)
    return config_dir / "weights"


def cache_sources(records: FetchRecords | None = None) -> list[FolderSource]:
    """The four built-in cache sources, in prefix order; *records* are the files fetched into them."""
    return [
        TorchHubSource(
            name="torchhub",
            label="Torch Hub",
            locate=torchhub_dir,
            description="Torch Hub checkpoints",
            records=records,
        ),
        FolderSource(
            name="rembg", label="rembg", locate=rembg_dir, description="rembg models", records=records
        ),
        FolderSource(
            name="keras",
            label="Keras",
            locate=keras_dir,
            description="Keras application weights",
            records=records,
        ),
        FolderSource(
            name="ultralytics",
            label="Ultralytics",
            locate=ultralytics_dir,
            description="Ultralytics weights",
            records=records,
        ),
    ]
