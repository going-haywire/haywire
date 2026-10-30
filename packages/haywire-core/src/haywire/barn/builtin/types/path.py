"""PATH, FILE_PATH and FOLDER_PATH — a location inside a named volume."""

from haywire.barn.builtin import widget_keys
from haywire.core.types import PrimitiveType
from haywire.core.types import type as type_decorator
from haywire.core.volumes import VolumePath
from ..wires import DataWire


@type_decorator(
    wire_type=DataWire,
    label="Path",
    description=(
        "A file or folder inside a named volume such as `project` or `models`. "
        "The graph stores the volume and the path within it, so it keeps working on another machine."
    ),
    color="#c9a66b",
    default={"value": {"volume": "project", "relative": ""}},
    widget_key=widget_keys.PATH_WIDGET,
)
class PATH(PrimitiveType[VolumePath]):
    """A file or folder inside a named volume such as `project` or `models`.

    Pick the volume, then type or browse to the path within it.
    """

    def to_dict(self) -> dict:
        return {"value": self._value.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> VolumePath:
        return VolumePath.from_dict(data.get("value", {}))


@type_decorator(
    wire_type=DataWire,
    label="File path",
    description="A file inside a named volume such as `project` or `models`.",
    color="#c9a66b",
    default={"value": {"volume": "project", "relative": ""}},
    widget_key=widget_keys.PATH_WIDGET,
    widget_config={"properties": {"mode": "file"}},
)
class FILE_PATH(PATH):
    """A file inside a named volume. Browsing offers files only."""


@type_decorator(
    wire_type=DataWire,
    label="Folder path",
    description="A folder inside a named volume such as `project` or `models`.",
    color="#c9a66b",
    default={"value": {"volume": "project", "relative": ""}},
    widget_key=widget_keys.PATH_WIDGET,
    widget_config={"properties": {"mode": "folder"}},
)
class FOLDER_PATH(PATH):
    """A folder inside a named volume. Browsing offers folders only."""
