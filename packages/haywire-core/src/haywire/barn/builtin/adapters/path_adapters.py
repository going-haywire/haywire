"""Path conversion adapters."""

from typing_extensions import override

from haywire.barn.builtin.types import PATH, STRING
from haywire.core.adapter.base import BaseAdapter, adapter
from haywire.core.volumes import PROJECT_KEY, VolumePath


@adapter(
    description="Convert a path to text: the volume's name and the path inside it",
    converts_from=PATH,
    converts_to=STRING,
)
class PathToStringAdapter(BaseAdapter):
    """Convert a path to its display form, `volume name:relative`, the same on every machine.

    For the location on this machine, use the Resolve Path node.
    """

    @override
    def convert(self, value: VolumePath) -> str:
        return str(value)

    def get_test_value(self) -> VolumePath:
        return VolumePath(PROJECT_KEY, "images/a.png")
