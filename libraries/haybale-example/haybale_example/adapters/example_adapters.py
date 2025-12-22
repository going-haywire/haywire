from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter
from haywire.libraries.core.types.specs import DICT

from ..types.mesh_data import MeshData

@adapter(
    description="Convert MeshData to Dict", 
    converts_from=MeshData, converts_to=DICT)
class MeshDataToDictAdapter(BaseAdapter):
    @override
    def convert(self, value: MeshData) -> dict:
        return value.to_dict()

@adapter(
    description="Convert Dict to MeshData", 
    converts_from=DICT, converts_to=MeshData)
class DictToMeshDataAdapter(BaseAdapter):
    @override
    def convert(self, value: dict) -> MeshData:
        return MeshData.from_dict(value)