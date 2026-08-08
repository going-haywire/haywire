"""Project publishing — the Share editor and its flow.

Publishing is PROJECT-scoped, not library-scoped (ADR 0023): a haywire project
is one uv workspace root with one marketstall feed and one git remote, and
every ``barn/*`` library versions in lockstep. That is why this is its own
library rather than an editor inside haybale-marketplace, whose job is
*consuming* feeds — its own architecture doc says it is "not a publisher".

The engine lives in :mod:`haywire.core.publishing`; everything here is UI.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.ui.editor.registry import EditorTypeRegistry


@library(
    label="Share",
    id="share",
    linked_libraries=[],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Project publishing library — the Share editor."""

    def register_components(self):
        base_path = Path(__file__).parent

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        return True
