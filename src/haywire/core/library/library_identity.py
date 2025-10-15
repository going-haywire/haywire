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
    dependencies: list[str] = None
    file_watcher: bool = False  # Whether to watch for file changes
    folder_path: str = None  # Path to the library folder, auto set during registration

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []