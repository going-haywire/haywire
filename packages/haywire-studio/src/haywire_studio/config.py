"""
Global and project-level configuration management for Haywire.

Global config lives at ~/.haywire/ and stores user preferences,
marketplace sources, and recently opened projects.

Project config lives at <project>/.haywire/ and stores
project-specific overrides.
"""

import os
from pathlib import Path

import toml


GLOBAL_CONFIG_DIR = Path.home() / ".haywire"

DEFAULT_GLOBAL_CONFIG = {
    "haywire": {
        "version": "0.1.0",
    },
    "ui": {
        "theme": "modern",
    },
}

DEFAULT_MARKETPLACE = {
    "sources": [
        # Future: official marketplace URL
        # {'name': 'official', 'url': 'https://haywire.dev/marketplace.toml'},
    ],
}

DEFAULT_PROJECT_CONFIG = {
    "haywire": {
        "version": "0.1.0",
    },
}


def ensure_global_config():
    """Create ~/.haywire/ with defaults if it doesn't exist."""
    GLOBAL_CONFIG_DIR.mkdir(exist_ok=True)

    config_file = GLOBAL_CONFIG_DIR / "config.toml"
    if not config_file.exists():
        config_file.write_text(toml.dumps(DEFAULT_GLOBAL_CONFIG))

    marketplace_file = GLOBAL_CONFIG_DIR / "marketplace.toml"
    if not marketplace_file.exists():
        marketplace_file.write_text(toml.dumps(DEFAULT_MARKETPLACE))

    recent_file = GLOBAL_CONFIG_DIR / "recent_projects.toml"
    if not recent_file.exists():
        recent_file.write_text(toml.dumps({"projects": []}))


def get_global_config() -> dict:
    """Read ~/.haywire/config.toml."""
    ensure_global_config()
    return toml.loads((GLOBAL_CONFIG_DIR / "config.toml").read_text())


def get_marketplace_sources() -> list[dict]:
    """Read ~/.haywire/marketplace.toml and return source list."""
    ensure_global_config()
    data = toml.loads((GLOBAL_CONFIG_DIR / "marketplace.toml").read_text())
    return data.get("sources", [])


def get_recent_projects() -> list[str]:
    """Read ~/.haywire/recent_projects.toml."""
    ensure_global_config()
    data = toml.loads((GLOBAL_CONFIG_DIR / "recent_projects.toml").read_text())
    return data.get("projects", [])


def add_recent_project(project_path: str):
    """Add a project path to the recent projects list."""
    ensure_global_config()
    recent_file = GLOBAL_CONFIG_DIR / "recent_projects.toml"
    data = toml.loads(recent_file.read_text())
    projects = data.get("projects", [])

    # Normalize and deduplicate
    abs_path = os.path.abspath(project_path)
    if abs_path in projects:
        projects.remove(abs_path)
    projects.insert(0, abs_path)

    # Keep only last 20
    data["projects"] = projects[:20]
    recent_file.write_text(toml.dumps(data))


def ensure_project_config(project_dir: Path):
    """Create <project>/.haywire/ with defaults if it doesn't exist."""
    haywire_dir = project_dir / ".haywire"
    haywire_dir.mkdir(exist_ok=True)

    config_file = haywire_dir / "config.toml"
    if not config_file.exists():
        config_file.write_text(toml.dumps(DEFAULT_PROJECT_CONFIG))


def get_project_config(project_dir: Path) -> dict:
    """Read <project>/.haywire/config.toml."""
    config_file = project_dir / ".haywire" / "config.toml"
    if config_file.exists():
        return toml.loads(config_file.read_text())
    return {}


def get_disabled_libraries(project_dir: Path) -> list[str]:
    """Get the list of explicitly disabled library IDs for this project."""
    config = get_project_config(project_dir)
    return config.get("libraries", {}).get("disabled", [])


def set_disabled_libraries(project_dir: Path, disabled_ids: list[str]):
    """Persist the list of disabled library IDs to project config."""
    config_file = project_dir / ".haywire" / "config.toml"
    config = get_project_config(project_dir)
    if "libraries" not in config:
        config["libraries"] = {}
    config["libraries"]["disabled"] = sorted(disabled_ids)
    config_file.write_text(toml.dumps(config))
