from typing import override

from haywire.core.adapter.base_adapter import BaseAdapter
from haywire.core.adapter.base_adapter import adapter
from ..types.mesh_data import MeshData

@adapter(
    description="Convert MeshData to Dict", 
    converts_from=MeshData, converts_to=dict)
class MeshDataToDictAdapter(BaseAdapter):
    source_type = MeshData
    target_type = dict

    @override
    def convert(self, value: MeshData) -> dict:
        return value.to_dict()

@adapter(
    description="Convert Dict to MeshData", 
    converts_from=dict, converts_to=MeshData)
class DictToMeshDataAdapter(BaseAdapter):
    source_type = dict
    target_type = MeshData

    @override
    def convert(self, value: dict) -> MeshData:
        return MeshData.from_dict(value)