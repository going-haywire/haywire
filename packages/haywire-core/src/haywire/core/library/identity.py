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
    # List of referenced haywire libraries.
    # For hot reloading to work, the dependencies must be specified.
    # This includes any library whose ``ContextSignal`` subclasses this
    # library subscribes to in editor poll() methods — without the
    # dependency, hot-reload of the signal-declaring library can leave
    # the subscriber holding a stale class reference, causing
    # ``isinstance`` checks to spuriously return False.
    dependencies: list[str] | None = None
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
