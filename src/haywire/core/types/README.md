# ============================================================================
# SIMPLE PRIMITIVES - Use decorator default directly
# ============================================================================

@type(
    registry_id='float',
    default={'value': 2.0}
)
@dataclass
class FLOAT(PrimitiveType[float]):
    pass

FLOAT.create_default()  # ✅ Returns FLOAT(2.0)


# ============================================================================
# DERIVED TYPES - Inherit parent's default
# ============================================================================

@type(registry_id='temperature')
class Temperature(FLOAT):
    pass

Temperature.create_default()  # ✅ Returns Temperature(0.0) - inherited


# ============================================================================
# OVERRIDE PARENT'S DEFAULT
# ============================================================================

@type(
    registry_id='temperature',
    default={'value': 20.0}  # Override
)
class Temperature(FLOAT):
    pass

Temperature.create_default()  # ✅ Returns Temperature(20.0)


# ============================================================================
# COMPLEX PRIMITIVES - Override create_default()
# ============================================================================

@type(
    registry_id='numpyarray',
    label='Numpy Array',
    default={'value': None}  # Just a serialization hint
)
class NumpyArray(PrimitiveType[np.ndarray]):
    @classmethod
    def create_default(cls) -> 'NumpyArray':
        """Create default with actual numpy array."""
        return cls(np.zeros((2, 3), dtype=np.int32))

NumpyArray.create_default()  # ✅ Returns NumpyArray with np.zeros((2, 3))


# ============================================================================
# BASE TYPES - Use decorator default
# ============================================================================

@type(
    registry_id='mesh_data',
    default={'vertices': [], 'faces': [], 'name': 'Default Mesh'}
)
@dataclass
class MeshData(BaseType):
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)
    name: str = "Unnamed Mesh"

MeshData.create_default()  # ✅ Returns MeshData(vertices=[], faces=[], name='Default Mesh')


# ============================================================================
# BASE TYPES - default
# ============================================================================

@type(
    registry_id='color',
    default={'r': 0, 'g': 255, 'b': 0, 'a': 1.0}
)
@dataclass
class Color(BaseType):
    r: int = 0
    g: int = 0
    b: int = 0
    a: float = 1.0
    

Color.create_default()  # ✅ Returns Color(0, 255, 0, 1.0)

# ============================================================================
# BASE TYPES - Override for computed defaults
# ============================================================================

@type(
    registry_id='color',
    default={'r': 0, 'g': 0, 'b': 0, 'a': 1.0}
)
@dataclass
class Color(BaseType):
    r: int = 0
    g: int = 0
    b: int = 0
    a: float = 1.0
    
    @classmethod
    def create_default(cls) -> 'Color':
        """Create default white color."""
        return cls(r=255, g=255, b=255, a=1.0)

Color.create_default()  # ✅ Returns Color(255, 255, 255, 1.0)