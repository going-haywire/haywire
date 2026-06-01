from dataclasses import dataclass


@dataclass
class LibraryIdentity:
    """Metadata for a Haywire library"""

    label: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    folder_path: str  # Path to the library folder
    module_name: str  # Python module name
    id: str  # Unique identifier for the library
    dependencies: list[str] | None = None
    """Referenced haywire libraries (Python package names). Must be specified for
        hot-reload: this includes any library whose subclasses this one
        subscribes to — without the dependency, hot-reload
        leaves the subscriber holding a stale class reference"""
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes
    # Post-install requirements (author-declared; default False).
    needs_refresh: bool = False
    needs_restart: bool = False

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
