"""Workspace path helpers shared across editor libraries."""

from __future__ import annotations

from pathlib import Path


def default_save_dir(workspace_root: Path) -> Path:
    """Return ``workspace_root/graphs`` if it exists, else ``workspace_root``."""
    graphs_dir = workspace_root / "graphs"
    return graphs_dir if graphs_dir.is_dir() else workspace_root
