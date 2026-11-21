"""Haybale-Audio: audio blocks shared by speech, streaming and device libraries.

Provides:
  - AudioBlock (``haybale_audio.value``): one block of planar float32 samples with its
    sample rate, passed between nodes by reference and never mutated.

Component folders (registered in ``register_components``):
  - ``types``, ``nodes``: the AUDIO and AUDIO_CALLBACK types and the Audio Event node.
"""

from pathlib import Path

from haywire.api import BaseLibrary, NodeRegistry, TypeRegistry, library


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Audio library — audio block value, types and events."""

    def register_components(self):
        """Register the component folders with their registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

    def validate(self) -> bool:
        return True
