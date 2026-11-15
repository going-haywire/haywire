"""Project publishing — the Share editor and its flow.

Publishing is PROJECT-scoped, not library-scoped: a haywire project is one uv
workspace root with one marketstall feed and one git remote, and every
``barn/*`` library versions in lockstep.

The engine lives in :mod:`haywire.core.publishing`; everything here is UI.
"""

from pathlib import Path

from haywire.api import BaseLibrary, library
from haywire.api.workbench import EditorRegistry


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Project publishing library — the Share editor."""

    def register_components(self):
        base_path = Path(__file__).parent

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorRegistry,
        )

    def validate(self) -> bool:
        return True
