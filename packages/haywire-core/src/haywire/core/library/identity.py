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
    # Unique identifier for the library, defaults to label if not set
    id: str = None
    # List of referenced haywire libraries.
    # For hot reloading to work, the dependencies must be specified.
    # This includes any library whose ``ContextSignal`` subclasses this
    # library subscribes to in editor poll() methods — without the
    # dependency, hot-reload of the signal-declaring library can leave
    # the subscriber holding a stale class reference, causing
    # ``isinstance`` checks to spuriously return False.
    dependencies: list[str] = None
    tags: list[str] = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes
    folder_path: str = None  # Path to the library folder, auto set during registration
    module_name: str = None  # Python module name, auto set during registration

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
