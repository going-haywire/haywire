"""
Example custom type: 3D Mesh data structure.

This demonstrates how to create a custom type that can be passed
between nodes in the Haywire system.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Tuple

from haywire.core.types.decorators import compound_type
from haywire.core.types.base import TypeBase


@compound_type(
    registry_id='mesh_data',
    label='3D Mesh',
    description='Polygonal mesh with vertices and faces',
    color='#4CAF50',
    icon='cube',
    help_url='https://haywire.io/docs/types/mesh-data'
)
@dataclass
class MeshData(TypeBase):
    """
    A 3D mesh data structure.
    
    Represents a polygonal mesh with vertices (3D points) and faces
    (triangular connections between vertices).
    
    Attributes:
        vertices: List of (x, y, z) coordinate tuples
        faces: List of (v1, v2, v3) vertex index tuples forming triangles
        name: Optional name for the mesh
    """
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)
    name: str = "Named Mesh"
    
    def to_dict(self) -> dict:
        """
        Serialize mesh data to dictionary format.
        
        Returns:
            Dictionary containing all mesh data
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MeshData':
        """
        Deserialize mesh data from dictionary format.
        
        Args:
            data: Dictionary containing mesh data
            
        Returns:
            New MeshData instance
        """
        return cls(**data)
    
    def vertex_count(self) -> int:
        """Get the number of vertices in the mesh."""
        return len(self.vertices)
    
    def face_count(self) -> int:
        """Get the number of faces in the mesh."""
        return len(self.faces)
    
    def add_vertex(self, x: float, y: float, z: float) -> int:
        """
        Add a vertex to the mesh.
        
        Args:
            x, y, z: Coordinates of the vertex
            
        Returns:
            Index of the newly added vertex
        """
        self.vertices.append((x, y, z))
        return len(self.vertices) - 1
    
    def add_face(self, v1: int, v2: int, v3: int) -> int:
        """
        Add a triangular face to the mesh.
        
        Args:
            v1, v2, v3: Indices of the vertices forming the triangle
            
        Returns:
            Index of the newly added face
        """
        self.faces.append((v1, v2, v3))
        return len(self.faces) - 1
    
    def __str__(self) -> str:
        """String representation of the mesh."""
        return f"MeshData('{self.name}', {self.vertex_count()} vertices, {self.face_count()} faces)"
