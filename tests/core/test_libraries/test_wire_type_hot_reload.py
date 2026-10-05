"""A wire type defined in a library hot-reloads into the types that use it.

A wire-type module is no registered component. It reloads as an unmanaged
module, and the dependency graph reloads the type modules importing it.
"""

import sys
import time

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import FileChangeEvent, FileEventType
from haywire.core.types import wire as wire_module
from haywire.core.types.registry import TypeRegistry
from haywire.core.types.wire import get_wire_type

pytestmark = [pytest.mark.unit, pytest.mark.core]

# No Library class in the temp package, so both ids take the '__system__' prefix.
WIRE_ID = "__system__:wire:DemoWire"
TYPE_KEY = "__system__:type:DemoValue"

# The "original" and "edited" kinds differ in length, so the .pyc size check cannot serve stale
# bytecode when both writes land in the same second.
_WIRE_SOURCE = """
from haywire.core.types.wire import WireRole, WireType


class DemoWire(WireType):
    role = WireRole.DEPENDENT
    pin_kind = "{kind}"
"""

_TYPE_SOURCE = """
from haywire.core.types import PrimitiveType, type

from {wire_module} import DemoWire


@type(wire_type=DemoWire, default={{"value": 0}})
class DemoValue(PrimitiveType[int]):
    '''A value on the demo wire.'''
"""


def _drop_demo_modules() -> None:
    for name in [m for m in sys.modules if m.startswith("haybale_wiredemo")]:
        del sys.modules[name]


@pytest.fixture(params=["root", "types"])
def library(request, tmp_path, monkeypatch):
    """A library whose type imports a wire type from the root, or from inside types/."""
    monkeypatch.setattr(wire_module, "_WIRE_BY_ID", dict(wire_module._WIRE_BY_ID))
    root = tmp_path / "haybale_wiredemo"
    (root / "types").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "types" / "__init__.py").write_text("")
    if request.param == "root":
        wire_path, wire_module_name = root / "wires.py", "haybale_wiredemo.wires"
    else:
        wire_path, wire_module_name = root / "types" / "wires.py", "haybale_wiredemo.types.wires"
    wire_path.write_text(_WIRE_SOURCE.format(kind="original"))
    (root / "types" / "demo_value.py").write_text(_TYPE_SOURCE.format(wire_module=wire_module_name))

    monkeypatch.syspath_prepend(str(tmp_path))
    _drop_demo_modules()
    identity = LibraryIdentity(
        name="wiredemo", label="Wire demo", folder_path=str(root), module_name="haybale_wiredemo"
    )
    yield root, identity, wire_path
    _drop_demo_modules()


def test_editing_a_wire_type_reaches_the_types_on_it(library):
    root, identity, wire_path = library
    registry = TypeRegistry()
    registry.add_folder(str(root / "types"), identity)
    value_type = registry.get(TYPE_KEY)
    assert value_type is not None
    wire_type = value_type.class_identity.wire_type
    assert wire_type is not None
    assert wire_type.pin_kind == "original"

    wire_path.write_text(_WIRE_SOURCE.format(kind="edited"))
    registry.event_dispatcher(
        FileChangeEvent(
            file_path=str(wire_path),
            event_type=FileEventType.MODIFIED,
            library_identity=identity,
            timestamp=time.time(),
        )
    )

    reloaded_type = registry.get(TYPE_KEY)
    assert reloaded_type is not None
    reloaded = reloaded_type.class_identity.wire_type
    assert reloaded is not None
    assert reloaded.id == WIRE_ID
    assert reloaded.pin_kind == "edited", "the type must be rebuilt on the edited wire type"
    wire_id_type = get_wire_type(WIRE_ID)
    assert wire_id_type is not None
    assert wire_id_type.pin_kind == "edited", "the id map must hold the edited class"
