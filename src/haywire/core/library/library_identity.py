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
    id: str = None  # Unique identifier for the library, defaults to label if not set
    dependencies: list[str] = None # List of referenced haywire libraries. For hot reloading to work, the dependencies must be specified.
    file_watcher: bool = False  # Whether to watch for file changes
    folder_path: str = None  # Path to the library folder, auto set during registration
    module_name: str = None  # Python module name, auto set during registration

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []