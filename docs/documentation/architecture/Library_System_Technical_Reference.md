# Haywire Library System - Technical Reference

## Overview

The Haywire library system uses a dual-structure, multi-priority loading architecture that combines Python entry points, file system scanning, and intelligent module resolution to support both internal (core) and external (pip-installable) libraries.

## Architecture Components

### 1. Library Discovery (`src/haywire/core/library/discovery.py`)

**Purpose**: Scan installed Python packages for Haywire libraries via entry points.

**Key Classes**:

```python
class InstallType(Enum):
    REGULAR = "regular"    # Standard pip install
    EDITABLE = "editable"  # pip install -e (development mode)
    FOLDER = "folder"      # Direct folder scanning

@dataclass
class DiscoveredLibrary:
    name: str              # Library display name
    library_id: str        # Unique identifier
    entry_point: str       # Entry point name
    location: str          # File system path
    install_type: InstallType
```

**LibraryDiscovery Class**:

```python
class LibraryDiscovery:
    ENTRY_POINT_GROUP = "haywire.libraries"
    
    def discover_installed_libraries(self) -> List[DiscoveredLibrary]:
        """Scan all installed packages for haywire.libraries entry points"""
        # Uses importlib.metadata.entry_points()
        # Detects install type via .locate() path inspection
        # Returns metadata without importing libraries
```

**Install Type Detection**:
- **Editable**: Path contains `/` separator and points to source directory
- **Regular**: Path is a module identifier without file separators

### 2. Library Registry (`src/haywire/core/library/registries/reg_library.py`)

**Purpose**: Central registry managing library discovery, loading, and lifecycle.

**Configuration Attributes**:

```python
class LibraryRegistry:
    load_core_libraries: bool = True    # Enable core library loading
    load_pip_packages: bool = True      # Enable pip package discovery
    core_libraries_path: str = None     # Path to core libraries
    _library_sources: Dict[str, str]    # Track library source paths
```

**4-Priority Loading System**:

```python
def scan_for_libraries(self):
    """
    Priority 1: Core libraries (src/haywire/libraries/)
    Priority 2: Regular pip installs (site-packages)
    Priority 3: Editable pip installs (development mode)
    Priority 4: Manual folder paths
    """
    discovered = {}
    
    # Priority 1: Core libraries
    if self.load_core_libraries:
        discovered.update(self._discover_core_libraries())
    
    # Priority 2 & 3: Pip packages
    if self.load_pip_packages:
        for lib in LibraryDiscovery().discover_installed_libraries():
            if lib.library_id not in discovered:
                discovered[lib.library_id] = lib
    
    # Priority 4: Folder paths
    for lib in self._discover_folder_libraries():
        if lib.library_id not in discovered:
            discovered[lib.library_id] = lib
    
    # Instantiate and register
    self._instantiate_libraries(discovered)
```

**Duplicate Prevention Logic**:
- Uses `library_id` as unique key
- First occurrence wins (highest priority)
- Subsequent occurrences logged and skipped
- Prevents multiple registrations of same library

### 3. Library Structure Detection

**Two Supported Patterns**:

**Pattern 1: Flat Structure (Core Libraries)**
```
src/haywire/libraries/core/
├── __init__.py          # Library class here
├── adapters/
├── nodes/
├── widgets/
└── renderers/
```
- Module path: `haywire.libraries.core`
- Used for: Core libraries bundled with Haywire
- Detection: `__init__.py` exists at `library_path/`

**Pattern 2: Package Structure (External Libraries)**
```
libraries/example/
├── pyproject.toml
└── example/             # Package folder (same name as library_id)
    ├── __init__.py      # Library class here
    ├── adapters/
    ├── nodes/
    ├── widgets/
    └── renderers/
```
- Module path: `example` (not `example.example`)
- Used for: Pip-installable external libraries
- Detection: `__init__.py` exists at `library_path/library_id/`

**Structure Detection Logic**:

```python
def _check_library_structure(self, library_id: str, library_path: str) -> bool:
    # Pattern 1: Flat structure
    flat_init = os.path.join(library_path, '__init__.py')
    if os.path.exists(flat_init):
        return True
    
    # Pattern 2: Package structure  
    package_init = os.path.join(library_path, library_id, '__init__.py')
    if os.path.exists(package_init):
        return True
    
    return False
```

### 4. Module Resolution (`src/haywire/core/library/folder_scan.py`)

**Purpose**: Calculate correct Python module names for both library structures.

**Algorithm**:

```python
def resolve_module_name(
    self, 
    file_path: str, 
    library_root: str,      # LibraryIdentity.folder_path
    module_prefix: str      # LibraryIdentity.module_name
) -> str:
    """
    Examples:
    
    Flat structure:
      file_path: /src/haywire/libraries/core/nodes/math.py
      library_root: /src/haywire/libraries/core
      module_prefix: haywire.libraries.core
      → Returns: haywire.libraries.core.nodes.math
    
    Package structure:
      file_path: /libraries/example/example/nodes/math.py
      library_root: /libraries/example/example
      module_prefix: example
      → Returns: example.nodes.math
    """
    # Calculate relative path from library root
    rel_path = Path(file_path).relative_to(Path(library_root))
    
    # Build parts: dirs + filename (without .py)
    parts = list(rel_path.parts[:-1]) + [rel_path.stem]
    
    # Combine prefix with relative parts
    return f"{module_prefix}.{'.'.join(parts)}"
```

**Why This Approach**:
- **No directory walking**: Direct calculation from known roots
- **Consistent results**: Same inputs always produce same output
- **Structure agnostic**: Works for both flat and package layouts
- **No __init__.py dependency**: Doesn't rely on walking until no `__init__.py`

### 5. Module Loading

**For Core Libraries (Flat Structure)**:

```python
# Core library at: src/haywire/libraries/core/
# Python already knows about haywire.libraries.core via package structure
module = importlib.import_module("haywire.libraries.core")
```

**For External Libraries (Package Structure)**:

```python
# Library at: /libraries/example/example/
# Need to add parent to sys.path temporarily

parent_dir = os.path.dirname(library_path)  # /libraries/example
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
# For flat structure (__init__.py at library_path/):
module = importlib.import_module(library_id)  # "example"

# For package structure (__init__.py at library_path/library_id/):
module = importlib.import_module(f"{library_id}.{library_id}")  # "example.example"

# Clean up sys.path
sys.path.remove(parent_dir)
```

### 6. LibraryIdentity Metadata

**Fields Used by System**:

```python
@dataclass
class LibraryIdentity:
    id: str                # Unique identifier (e.g., "example", "haywire.core")
    folder_path: str       # Absolute path to library root
    module_name: str       # Python module path (e.g., "example", "haywire.libraries.core")
    label: str             # Human-readable name
    version: str           # Semantic version
    dependencies: list     # List of required library IDs
    file_watcher: bool     # Enable hot-reload
```

**Auto-Set During Registration**:
- `folder_path`: Set to discovered library location
- `module_name`: Set based on structure pattern
- `id`: Defaults to library class attribute if not specified

### 7. Hot-Reload System

**File Watching Integration**:

```python
# In BaseLibrary
if self.identity.file_watcher or self.enforce_file_watching:
    self.file_watcher.watch_directory(
        folder_path,
        callback=self._on_file_change
    )
```

**Hot-Reload by Source Type**:

| Source | Hot-Reload | Mechanism |
|--------|------------|-----------|
| Core libraries | ✅ Yes | FileWatcher on source directory |
| Regular pip | ❌ No | Files in site-packages (immutable) |
| Editable pip | ✅ Yes | FileWatcher on linked source directory |
| Folder paths | ✅ Yes | FileWatcher on source directory |

**Module Reload Process**:

```python
def _on_change(self, module_name: str, library_identity: LibraryIdentity):
    # 1. Unregister old classes from registries
    self._unregister_classes(module_name)
    
    # 2. Reload module
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    
    # 3. Re-scan and register new classes
    classes, _ = self.folder_scan_for_classes(
        file_path, 
        class_filter=self.filter
    )
    for cls in classes:
        self.register(cls, library_identity)
```

### 8. Dependency Injection Configuration

**DI Setup** (`src/haywire/core/di/config.py`):

```python
@singleton
@provider
def provide_library_registry(self) -> LibraryRegistry:
    registry = LibraryRegistry()
    
    # Configure core libraries path
    if self.project_root:
        core_path = os.path.join(
            self.project_root, 
            'src/haywire/libraries'
        )
        registry.core_libraries_path = core_path
        
        # Don't scan core as folder (already loaded as Priority 1)
        if core_path in self.library_paths:
            self.library_paths.remove(core_path)
    
    # Enable pip discovery
    registry.load_pip_packages = True
    
    # Add manual folder paths
    for path in self.library_paths:
        registry.add_library_root_path(path)
    
    return registry
```

### 9. Entry Point Configuration

**In Library's pyproject.toml**:

```toml
[project.entry-points."haywire.libraries"]
library_id = "package_name:Library"
```

**Examples**:

```toml
# Simple package (flat within)
[project.entry-points."haywire.libraries"]
example = "example:Library"

# Nested package
[project.entry-points."haywire.libraries"]
my_nodes = "haywire_my_nodes.library:Library"
```

**Entry Point Resolution**:
1. `importlib.metadata.entry_points(group='haywire.libraries')`
2. For each entry point: `ep.load()` returns Library class
3. Verify class has `class_identity` attribute (from @library decorator)
4. Extract `library_id`, `name`, `location`

### 10. Class Registry Integration

**FolderScanMixin Usage**:

```python
# In BaseClassRegistry (nodes, widgets, adapters, etc.)
class NodeRegistry(BaseClassRegistry, FolderScanMixin):
    
    def scan_folder(self, folder_path: str, library_identity: LibraryIdentity):
        # Get all .py files
        file_paths = self.folder_scan_for_pyfiles(folder_path)
        
        for file_path in file_paths:
            # Resolve module name using library context
            module_name = self.resolve_module_name(
                file_path,
                library_identity.folder_path,
                library_identity.module_name
            )
            
            # Import and register
            self._on_creation(module_name, library_identity)
```

**Registry Types**:
- `NodeRegistry`: Manages `@node` decorated classes
- `WidgetRegistry`: Manages `@widget` decorated classes  
- `SkinRegistry`: Manages `@renderer` decorated classes
- `AdapterRegistry`: Manages `@adapter` decorated classes

Each registry inherits `FolderScanMixin` for consistent module resolution.

## Data Flow

### Library Loading Sequence

```
1. Application Start
   ↓
2. DI Container Setup
   ↓
3. LibraryRegistry.scan_for_libraries()
   ├─→ Priority 1: Core libraries
   ├─→ Priority 2: Regular pip
   ├─→ Priority 3: Editable pip
   └─→ Priority 4: Folder paths
   ↓
4. _instantiate_libraries()
   ├─→ _check_library_structure()
   ├─→ _load_module_and_metadata()
   └─→ _register_library_instance()
   ↓
5. Library.enable()
   ├─→ register_components()
   ├─→ scan folders (nodes, widgets, etc.)
   └─→ start file watchers
   ↓
6. Component Registries Populated
   ├─→ NodeRegistry
   ├─→ WidgetRegistry
   ├─→ SkinRegistry
   └─→ AdapterRegistry
```

### Module Resolution Flow

```
File Path: /libraries/example/example/nodes/math.py
Library Identity: {
    folder_path: /libraries/example/example
    module_name: example
}
   ↓
resolve_module_name()
   ↓
Relative Path: nodes/math.py
   ↓
Parts: ['nodes', 'math']
   ↓
Module Name: example.nodes.math
   ↓
importlib.import_module('example.nodes.math')
   ↓
Module Loaded & Classes Registered
```

## Performance Considerations

### Entry Point Scanning
- **Overhead**: ~200ms at startup
- **Frequency**: Once per application start
- **Optimization**: Results cached in `_libraries` dict

### Module Resolution
- **Overhead**: Minimal (path operations only)
- **Frequency**: Once per file during initial scan
- **Optimization**: Direct calculation, no directory walking

### Hot-Reload
- **File Watching**: Debounced (default 0.5s delay)
- **Module Reload**: Only changed modules reloaded
- **Registry Update**: Incremental (only affected classes)

### Memory
- **Library Instances**: One per library (lightweight)
- **Module Cache**: sys.modules (shared with Python)
- **Registry Storage**: Dict-based (efficient lookup)

## Security Considerations

1. **Entry Point Validation**
   - Verifies class has `@library` decorator
   - Checks for required attributes
   - Catches and logs import errors

2. **Path Validation**
   - Checks library structure before loading
   - Validates file paths during scanning
   - Prevents path traversal in relative calculations

3. **Module Isolation**
   - Each library has own namespace
   - sys.path modifications are temporary and cleaned up
   - No arbitrary code execution

## Error Handling

### Discovery Errors
```python
try:
    library_class = entry_point.load()
except Exception as e:
    logging.error(f"Error loading entry point: {e}")
    continue  # Skip this library, continue with others
```

### Structure Validation
```python
if not self._check_library_structure(library_id, library_path):
    logging.warning(f"Invalid structure for {library_id}")
    return None
```

### Import Failures
```python
try:
    module = importlib.import_module(module_name)
except ImportError as e:
    logging.error(f"Failed to import {module_name}: {e}")
    # Library marked as invalid, not registered
```

## Extension Points

### Custom Discovery
Implement custom discovery by extending `LibraryRegistry`:

```python
class CustomLibraryRegistry(LibraryRegistry):
    def _discover_custom_sources(self):
        # Your custom discovery logic
        pass
    
    def scan_for_libraries(self):
        discovered = super().scan_for_libraries()
        discovered.update(self._discover_custom_sources())
        return discovered
```

### Custom Module Resolution
Override `resolve_module_name` in `FolderScanMixin`:

```python
class CustomFolderScan(FolderScanMixin):
    def resolve_module_name(self, file_path, library_root, module_prefix):
        # Custom resolution logic
        return custom_module_name
```

## Testing

### Unit Tests
```python
def test_library_discovery():
    discovery = LibraryDiscovery()
    libs = discovery.discover_installed_libraries()
    assert len(libs) > 0
    assert all(isinstance(lib, DiscoveredLibrary) for lib in libs)

def test_module_resolution():
    mixin = FolderScanMixin()
    module_name = mixin.resolve_module_name(
        "/path/to/lib/nodes/test.py",
        "/path/to/lib",
        "mylib"
    )
    assert module_name == "mylib.nodes.test"
```

### Integration Tests
```bash
python scripts/test_library_discovery.py
```

## Future Enhancements

1. **Dependency Resolution**
   - Topological sort for load order
   - Circular dependency detection
   - Version constraint validation

2. **Plugin Ecosystem**
   - Additional entry point groups
   - Plugin marketplace integration
   - Auto-update checking

3. **Performance**
   - Lazy loading of libraries
   - Parallel discovery
   - Cached discovery results

4. **Debugging**
   - Detailed logging modes
   - Library dependency graph visualization
   - Load time profiling
