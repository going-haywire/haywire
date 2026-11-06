"""Resolve Model — the local file of a model reference, with its digest and size."""

from __future__ import annotations

from pathlib import Path

from haybale_models import consumer
from haybale_models.consumer import resolve_port
from haybale_models.store.layout import volume_path_of
from haybale_models.value.model_ref import ModelRef

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath


@node(
    label="Resolve Model",
    description="Gives the file of a model on this machine, with its sha256 and size",
    menu="models",
    search_tags=["model", "resolve", "file", "path", "weights", "catalog", "sha256"],
    node_type=NodeType.DATA,
)
class ResolveModelNode(BaseNode):
    """Gives the file of a model on this machine, with its sha256 and size.

    Pick the model on the card: a catalog entry, or a file by its address
    (`hf://` or `https://`) or from the Models or Hugging Face cache folder.
    Nothing is downloaded here: a model that is not on this machine is an
    error until it is fetched in the Models editor.

    - `Path`: the file, as a path inside the `Models` or `Hugging Face cache`
      volume. For a model made of several files, or a whole-repo `hf://`
      address, the folder holding them.
    - `sha256`: the file's digest, empty when it is not known yet.
    - `Size`: the size in bytes, of all files together for a model made of
      several files.

    For a catalog entry with several variants, the first one on disk in the
    port's preferred order is used.
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import FILE_PATH, INT, STRING

        from haybale_models.types.model_ref import MODEL_REF

        self.add(MODEL_REF.as_inlet("model", label="Model", description="Model to look up"))
        self.add(FILE_PATH.as_outlet("path", label="Path", description="The model's file on this machine"))
        self.add(STRING.as_outlet("sha256", label="sha256", description="The file's sha256 checksum"))
        self.add(INT.as_outlet("size", label="Size", description="The file's size in bytes"))

    def worker(self, context: ExecutionContext, model: ModelRef) -> None:
        resolved = resolve_port(self, "model")
        self.out("path", _volume_path(resolved.path))
        self.out("sha256", resolved.sha256)
        self.out("size", resolved.size)
        return None


def _volume_path(path: Path) -> VolumePath:
    """Return *path* as a path inside a model volume; ``ValueError`` if in none."""
    found = volume_path_of(path, consumer.models_state().sources)
    if found is None:
        raise ValueError(f"model file {path} is in no model volume")
    return found
