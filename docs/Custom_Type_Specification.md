# Custom Data Types System - Implementation Specification

## Overview

The Custom Data Types system allows library developers to define complex data structures (beyond primitives like `int`, `float`, `str`) that can be:
- Shared across libraries without direct Python imports
- Type-checked by IDEs for autocomplete and error detection
- Serialized for graph save/load operations
- Registered in a central registry for runtime lookup


## Problem description

Problem: If libraryB needs to implement a type defined by libraryA - there is no simple way to let libraryB import the module of mesh_data.py

```
haywire-repo/
├── libraries/
│   ├── libraryA/
│   │   └── types/
│   │       └── mesh_data.py
│   └── libraryB/
│       └── nodes/
│           └── mesh_processor.py -> needs references "libraryA.types.mesh_data.py"
├── src/
│   └── haywire/
│       └── libraries/
│           └── core/
│               └── types/
│                   └── base_types.py/
```

Solution1: using a centrally managed collection of stubs 

```
.haywire/
    stubs/           # This becomes importable as "stubs"
    ├── __init__.py
    └── libraries/           # This becomes importable as "stubs.libraries"
        ├── __init__.py
        └── libraryA/          # This becomes importable as "stubs.libraries.libraryA"
            ├── __init__.py
            └── mesh_data.pyi  # This becomes "stubs.libraries.libraryA.mesh_data"
```

Solution2: move all libraries one needs to reference to into the src/haywire/libraries folder

```
haywire-repo/
├── libraries/
│   └── libraryB/
│       └── nodes/
│           └── mesh_processor.py -> needs references "haywire.libraries.libraryA.types.mesh_data.py"
├── src/
│   └── haywire/
│       └── libraries/
│           ├── core/
│           │   └── types/
│           │       └── base_types.py/
│           ├── libraryA/
│           │   └── types/
│           │       └── mesh_data.py
```

## Architecture

### Key Components

1. **CustomType Dataclass**: User-defined data structures using Python dataclasses
2. **CustomTypeRegistry**: Registry inheriting from `BaseClassRegistry` for managing types
3. **Type Stub Generation**: Auto-generated `.pyi` files for IDE support
4. **IDE Configuration**: Auto-generated settings for VSCode/PyCharm
5. **DataFieldSpec Integration**: Support for custom types in pin specifications

### Design Pattern

The system uses **dual-path resolution**:
- **Runtime Path**: String-based registry lookup (`'libraryA.mesh_data'`)
- **IDE Path**: Type stub imports (`from haywire_stubs.libraries.libraryA.mesh_data import MeshData`)

This separation allows libraries to remain isolated (no direct imports) while providing full IDE support.

## Implementation Steps

### Step 1: Create Custom Type Infrastructure

````python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Type, Protocol, Optional
from pathlib import Path

class CustomType(Protocol):
    """Protocol that all custom types must implement"""
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for graph storage"""
        ...
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomType:
        """Deserialize from dict when loading graph"""
        ...

@dataclass
class CustomTypeDescriptor:
    """Metadata about a registered custom type"""
    registry_id: str  # Format: 'library_name.type_name'
    type_class: Type
    label: str
    description: str = ''
    library_id: str = ''
    
    def create_instance(self, **kwargs) -> Any:
        """Factory for creating instances"""
        return self.type_class(**kwargs)
    
    def validate(self, value: Any) -> bool:
        """Check if value is instance of this type"""
        return isinstance(value, self.type_class)

def custom_type(
    registry_id: str,
    label: str,
    description: str = '',
    library_id: str = ''
):
    """Decorator to register a dataclass as a custom type
    
    Example:
        @custom_type(
            registry_id='mesh_data',
            label='3D Mesh',
            library_id='libraryA'
        )
        @dataclass
        class MeshData:
            vertices: list = field(default_factory=list)
            
            def to_dict(self) -> dict:
                return asdict(self)
            
            @classmethod
            def from_dict(cls, data: dict) -> MeshData:
                return cls(**data)
    """
    def decorator(cls: Type) -> Type:
        # Validate required methods
        if not hasattr(cls, 'to_dict') or not hasattr(cls, 'from_dict'):
            raise TypeError(
                f"{cls.__name__} must implement to_dict() and from_dict()"
            )
        
        # Store metadata as class attribute
        cls.class_identity = CustomTypeDescriptor(
            registry_id=registry_id,
            type_class=cls,
            label=label,
            description=description,
            library_id=library_id
        )
        
        return cls
    
    return decorator
````

### Step 2: Create CustomTypeRegistry

````python
from __future__ import annotations
import sys
import json
import shutil
from pathlib import Path
from typing import Type, Optional
import inspect
import logging

from ..class_registry import BaseClassRegistry
from ..library_identity import LibraryIdentity
from ...data.custom_types import CustomTypeDescriptor

class CustomTypeRegistry(BaseClassRegistry):
    """Registry for custom data types with IDE stub generation"""
    
    def __init__(self):
        super().__init__()
        self._stub_root = Path.cwd() / '.haywire' / 'stubs' / 'libraries'
        self._setup_stub_infrastructure()
    
    def _setup_stub_infrastructure(self):
        """Create stub directory and configure Python import path"""
        # Create directory structure
        self._stub_root.mkdir(parents=True, exist_ok=True)
        
        # Make it a package
        init_file = self._stub_root.parent / '__init__.py'
        if not init_file.exists():
            init_file.write_text('"""Haywire type stubs - auto-generated"""\n')
        
        # Add to sys.path for runtime imports
        stub_parent = str(self._stub_root.parent.parent)  # .haywire/stubs -> .haywire
        if stub_parent not in sys.path:
            sys.path.insert(0, stub_parent)
        
        # Configure IDE settings
        self._configure_ide_settings()
    
    def _configure_ide_settings(self):
        """Generate IDE configuration files"""
        stub_path = '.haywire/stubs'  # Relative path for portability
        
        # VSCode configuration
        vscode_dir = Path.cwd() / '.vscode'
        vscode_dir.mkdir(exist_ok=True)
        settings_file = vscode_dir / 'settings.json'
        
        if settings_file.exists():
            with open(settings_file) as f:
                settings = json.load(f)
        else:
            settings = {}
        
        extra_paths = settings.get('python.analysis.extraPaths', [])
        if stub_path not in extra_paths:
            extra_paths.append(stub_path)
            settings['python.analysis.extraPaths'] = extra_paths
            
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        
        # pyproject.toml configuration
        pyproject = Path.cwd() / 'pyproject.toml'
        if pyproject.exists():
            content = pyproject.read_text()
            if 'tool.pyright' not in content:
                with open(pyproject, 'a') as f:
                    f.write(f'\n[tool.pyright]\nextraPaths = ["{stub_path}"]\n')
    
    def _class_filter(self, cls: Type) -> bool:
        """Filter for custom type classes"""
        return (
            inspect.isclass(cls) and
            hasattr(cls, 'class_identity') and
            isinstance(cls.class_identity, CustomTypeDescriptor)
        )
    
    def _register_class(self, cls: Type, library_identity: LibraryIdentity) -> str | None:
        """Register custom type and generate stub"""
        descriptor: CustomTypeDescriptor = cls.class_identity
        
        # Create registry key: library_id:type_registry_id
        from ..utils import reg_key
        registry_key = reg_key(library_identity.id, descriptor.registry_id)
        
        # Register in base class
        super()._register(registry_key, cls, library_identity)
        
        # Generate stub file
        self._generate_stub(descriptor, library_identity)
        
        logging.info(
            f"Library '{library_identity.label}': Registered custom type "
            f"'{descriptor.label}' with key '{registry_key}'"
        )
        
        return registry_key
    
    def _unregister_class(self, registry_key: str) -> Type | None:
        """Unregister custom type and remove stub"""
        cls = super()._unregister(registry_key)
        
        if cls and hasattr(cls, 'class_identity'):
            descriptor = cls.class_identity
            library_id = cls.class_library.id
            self._remove_stub(descriptor.registry_id, library_id)
        
        return cls
    
    def _generate_stub(self, descriptor: CustomTypeDescriptor, library_identity: LibraryIdentity):
        """Generate .pyi stub file for IDE support"""
        lib_stub_dir = self._stub_root / library_identity.id
        lib_stub_dir.mkdir(exist_ok=True)
        
        # Generate stub content
        stub_content = self._generate_stub_content(descriptor)
        
        # Write stub file
        stub_file = lib_stub_dir / f'{descriptor.registry_id}.pyi'
        stub_file.write_text(stub_content)
        
        # Update library __init__.pyi
        self._update_library_init(library_identity.id, descriptor)
    
    def _generate_stub_content(self, descriptor: CustomTypeDescriptor) -> str:
        """Generate .pyi content from dataclass"""
        cls = descriptor.type_class
        lines = [
            '"""Auto-generated type stub"""',
            'from typing import Any',
            'from dataclasses import dataclass',
            '',
            '@dataclass',
            f'class {cls.__name__}:',
            f'    """{descriptor.description}"""'
        ]
        
        # Add fields from dataclass
        if hasattr(cls, '__annotations__'):
            for field_name, field_type in cls.__annotations__.items():
                type_str = str(field_type).replace('typing.', '')
                lines.append(f'    {field_name}: {type_str}')
        
        # Add methods
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not name.startswith('_') or name in ['__init__']:
                sig = inspect.signature(method)
                lines.append(f'    def {name}{sig}: ...')
        
        return '\n'.join(lines)
    
    def _update_library_init(self, library_id: str, descriptor: CustomTypeDescriptor):
        """Update library's __init__.pyi to export types"""
        lib_stub_dir = self._stub_root / library_id
        init_file = lib_stub_dir / '__init__.pyi'
        
        # Read existing content
        existing_types = set()
        if init_file.exists():
            content = init_file.read_text()
            for line in content.split('\n'):
                if line.startswith('from .'):
                    parts = line.split()
                    if len(parts) >= 4:
                        existing_types.add(parts[3])
        
        # Add new type
        existing_types.add(descriptor.type_class.__name__)
        
        # Write updated content
        lines = ['"""Auto-generated type stubs"""']
        for type_name in sorted(existing_types):
            # Find module name from registry
            module_name = descriptor.registry_id
            lines.append(f'from .{module_name} import {type_name}')
        
        lines.append(f'\n__all__ = {sorted(list(existing_types))}')
        init_file.write_text('\n'.join(lines))
    
    def _remove_stub(self, type_registry_id: str, library_id: str):
        """Remove stub file when type is unregistered"""
        stub_file = self._stub_root / library_id / f'{type_registry_id}.pyi'
        if stub_file.exists():
            stub_file.unlink()
    
    def create_instance(self, registry_key: str, **kwargs) -> Any:
        """Create instance of custom type by registry key"""
        cls = self.get(registry_key)
        if cls is None:
            raise KeyError(f"Custom type not found: {registry_key}")
        return cls(**kwargs)
    
    def get_type_class(self, registry_key: str) -> Type:
        """Get custom type class by registry key"""
        cls = self.get(registry_key)
        if cls is None:
            raise KeyError(f"Custom type not found: {registry_key}")
        return cls
````

### Step 3: Update DataFieldSpec

````python
# ...existing code...

@dataclass
class DataFieldSpec:
    type: DataType
    container: DataContainerType = DataContainerType.SINGLE
    value: Any = None
    custom_type_id: str | None = None  # NEW: Registry key for custom types
    id: str | None = None
    label: str | None = None
    description: str | None = None
    widget: str | None = None
    ui: dict[str, Any] = field(default_factory=dict)

    def create_field(self, is_pooled: bool = False) -> DataField:
        """Create DataField with custom type support"""
        # Handle custom types
        if self.custom_type_id:
            from haywire.core.di.config import get_library_system
            registry = get_library_system().custom_type_registry
            default_value = registry.create_instance(self.custom_type_id)
        else:
            default_value = self.value
        
        if is_pooled:
            return PooledField(type=self.type, value={}, is_pooled=True)
        else:
            return SingleField(type=self.type, value=default_value, is_pooled=False)
````

### Step 4: Register CustomTypeRegistry in DI Container

````python
# ...existing code...

from haywire.core.library.registries.reg_custom_type import CustomTypeRegistry

class LibrarySystemService:
    def __init__(self):
        # ...existing code...
        self.custom_type_registry = CustomTypeRegistry()
        # ...existing code...
````

## Usage Guide

### For Library A Developer (Type Provider)

**Step 1: Define Custom Type**

````python
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from haywire.core.data.custom_types import custom_type

@custom_type(
    registry_id='mesh_data',
    label='3D Mesh',
    description='Polygon mesh with vertices and faces',
    library_id='libraryA'
)
@dataclass
class MeshData:
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> MeshData:
        return cls(**data)
    
    def get_vertex_count(self) -> int:
        return len(self.vertices)
````

**Step 2: Register Type Folder in Library**

````python
from haywire.core.library.library import library, BaseLibrary
from haywire.core.library.registries.reg_custom_type import CustomTypeRegistry

@library(label='libraryA', version='1.0.0')
class Library(BaseLibrary):
    def register_components(self):
        types_path = Path(__file__).parent / 'types'
        self.add_folder_to_registry(
            folder_path=str(types_path),
            registry_cls=CustomTypeRegistry
        )
````

**Step 3: Use in Nodes**

````python
from __future__ import annotations
from typing import TYPE_CHECKING

from haywire.core.node.base_node import node, BaseNode
from haywire.core.node.elements import PinBuilder
from haywire.core.data.specs import specs_factory
from haywire.core.data.enums import DataType

if TYPE_CHECKING:
    from haywire_stubs.libraries.libraryA.mesh_data import MeshData

MESH_DATA_TYPE = 'libraryA:mesh_data'

@node(label='Mesh Generator')
class MeshGenerator(BaseNode):
    mesh_out = PinBuilder.outlet(
        spec=specs_factory(
            type=DataType.OBJECT,
            custom_type_id=MESH_DATA_TYPE
        ),
        label='Mesh'
    )
    
    def worker(self, context: dict) -> dict | None:
        from haywire.core.data.custom_types import create_custom_instance
        
        mesh: MeshData = create_custom_instance(MESH_DATA_TYPE)
        mesh.vertices.append((0, 0, 0))
        
        self.get_outlet('mesh_out').data.set_value(mesh)
        return None
````

### For Library B Developer (Type Consumer)

````python
from __future__ import annotations
from typing import TYPE_CHECKING

from haywire.core.node.base_node import node, BaseNode
from haywire.core.node.elements import PinBuilder
from haywire.core.data.specs import specs_factory
from haywire.core.data.enums import DataType

# Import type for IDE support (not evaluated at runtime)
if TYPE_CHECKING:
    from haywire_stubs.libraries.libraryA.mesh_data import MeshData

# Runtime reference
MESH_DATA_TYPE = 'libraryA:mesh_data'

@node(label='Mesh Analyzer')
class MeshAnalyzer(BaseNode):
    mesh_in = PinBuilder.inlet(
        spec=specs_factory(
            type=DataType.OBJECT,
            custom_type_id=MESH_DATA_TYPE
        ),
        label='Mesh Input'
    )
    
    def worker(self, context: dict) -> dict | None:
        # Full IDE autocomplete available
        mesh: MeshData = self.get_inlet('mesh_in').data.get_value()
        count = mesh.get_vertex_count()  # ✅ IDE shows method
        return None
````

## IDE Setup

### Automatic Configuration

The system auto-generates:

1. **`.vscode/settings.json`**:
```json
{
  "python.analysis.extraPaths": [".haywire/stubs"]
}
```

2. **pyproject.toml**:
```toml
[tool.pyright]
extraPaths = [".haywire/stubs"]
```

### Manual Verification

After first run, verify:
- `.haywire/stubs/libraries/` exists
- Stub files present: `.haywire/stubs/libraries/libraryA/mesh_data.pyi`
- VSCode settings updated
- Restart IDE to reload configurations

## Runtime Flow

1. **Application Start**: `CustomTypeRegistry.__init__()` adds `.haywire/stubs` to `sys.path`
2. **Library Load**: Types scanned, registered, stubs generated
3. **IDE Analysis**: Reads stubs from `.haywire/stubs/libraries/`
4. **Code Execution**: `TYPE_CHECKING` is `False`, no imports occur
5. **Runtime Lookup**: Registry resolves string keys to classes

## Key Concepts

- **`from __future__ import annotations`**: Makes all type hints into strings automatically
- **`TYPE_CHECKING`**: `False` at runtime, `True` during IDE analysis
- **Registry Keys**: Format `library_id:type_registry_id` (e.g., `'libraryA:mesh_data'`)
- **Stub Path**: `.haywire/stubs/libraries/libraryA/mesh_data.pyi`
- **Import Path**: `from haywire_stubs.libraries.libraryA.mesh_data import MeshData`