"""``MacroRegistry``: a .hwm becomes a component, or is refused with a reason."""

import json

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_EVENT = "haybale-testing:node:TestBeginPlayNode"


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


def _document(*registry_keys, description="", subgraphs=None):
    """A minimal BaseGraph.to_dict() shape holding the given node kinds."""
    return {
        "format_version": 1,
        "meta": {"description": description},
        "nodes": {
            f"n{i}": {"node_id": f"n{i}", "registry_key": key, "position": [0, 0]}
            for i, key in enumerate(registry_keys)
        },
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": subgraphs or {},
    }


def _write(folder, stem, document):
    path = folder / f"{stem}.hwm"
    path.write_text(json.dumps(document))
    return path


def _registry():
    from haywire.core.macro.registry import MacroRegistry

    return MacroRegistry()


def test_a_wellformed_macro_registers_with_a_node_identity(tmp_path, library_system):
    _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT, _ADD, description="Softens an image"))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    template = reg.get("testlib:macro:Blur")
    assert template is not None
    assert template.class_identity.label == "Blur"
    assert template.class_identity.registry_key == "testlib:macro:Blur"
    assert template.class_identity.description == "Softens an image"
    assert template.class_identity.menu == "macros/testlib"


def test_the_template_satisfies_the_registered_class_contract(tmp_path, library_system):
    """Kind-generic consumers read these two off get() and must not learn the difference."""
    _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    template = reg.get("testlib:macro:Blur")
    assert template.class_identity is not None
    assert template.class_library.name == "testlib"


def test_the_template_carries_the_interior_tables(tmp_path, library_system):
    """A placement instantiates from these; the file is the template."""
    _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT, _ADD))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    template = reg.get("testlib:macro:Blur")
    assert len(template.nodes) == 3
    assert template.edges == {}
    assert template.subgraphs == {}


def test_it_is_listed_as_a_visible_component(tmp_path, library_system):
    _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert "testlib:macro:Blur" in reg.list_visible_names()


def test_a_macro_missing_its_output_is_refused(tmp_path, library_system):
    """Containment (decision 13), checked against node classes without instantiating."""
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    _write(tmp_path, "Broken", _document(_INPUT))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Broken")
    event = reg.get_lastevent("testlib:macro:Broken")
    assert event is not None
    assert event.event_type is LifeCycleEventType.CLASS_RELOAD_FAILED
    assert "exactly one" in str(event.error.original_exception)


def test_a_macro_containing_an_event_node_is_refused(tmp_path, library_system):
    _write(tmp_path, "Evented", _document(_INPUT, _OUTPUT, _EVENT))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Evented")
    assert "EVENT or OUTPUT" in str(reg.get_lastevent("testlib:macro:Evented").error.original_exception)


def test_an_unknown_node_class_does_not_refuse_the_file(tmp_path, library_system):
    """An absent library is the placement's problem, not a malformed document."""
    _write(tmp_path, "Exotic", _document(_INPUT, _OUTPUT, "absent-lib:node:Whatever"))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert reg.has("testlib:macro:Exotic")


def test_a_nonconforming_filestem_is_skipped(tmp_path, library_system):
    """Decision 17: ^[A-Za-z][A-Za-z0-9_-]*$."""
    _write(tmp_path, "9lives", _document(_INPUT, _OUTPUT))
    _write(tmp_path, "Good", _document(_INPUT, _OUTPUT))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert reg.list_names() == ["testlib:macro:Good"]


def test_the_same_stem_twice_in_one_library_raises(tmp_path, library_system):
    """Distinct folders, one library — a duplicate key is an authoring error."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write(a, "Blur", _document(_INPUT, _OUTPUT))
    _write(b, "Blur", _document(_INPUT, _OUTPUT))
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.add_folder(str(a), identity)

    with pytest.raises(ValueError, match="Blur"):
        reg.add_folder(str(b), identity)


def test_a_self_referencing_macro_is_refused(tmp_path, library_system):
    """Cycle backstop (decision 14) for a file edited outside the studio."""
    _write(tmp_path, "Loop", _document(_INPUT, _OUTPUT, "testlib:macro:Loop"))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Loop")
    assert "places itself" in str(reg.get_lastevent("testlib:macro:Loop").error.original_exception)


def test_a_mutual_cycle_is_refused(tmp_path, library_system):
    """A placing B, B placing A: the one that closes the loop is refused, naming it.

    A is scanned first and has nothing to point at yet, so it registers; B
    closes the loop and is the one refused.
    """
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    _write(tmp_path, "A", _document(_INPUT, _OUTPUT, "testlib:macro:B"))
    _write(tmp_path, "B", _document(_INPUT, _OUTPUT, "testlib:macro:A"))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert reg.list_names() == ["testlib:macro:A"]
    event = reg.get_lastevent("testlib:macro:B")
    assert event.event_type is LifeCycleEventType.CLASS_RELOAD_FAILED
    assert "testlib:macro:A" in str(event.error.original_exception)


def test_a_macro_placing_another_macro_is_allowed(tmp_path, library_system):
    """Nesting is fine; only a cycle is not."""
    _write(tmp_path, "Inner", _document(_INPUT, _OUTPUT))
    _write(tmp_path, "Outer", _document(_INPUT, _OUTPUT, "testlib:macro:Inner"))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert reg.has("testlib:macro:Inner")
    assert reg.has("testlib:macro:Outer")


def test_unparseable_json_is_refused_with_a_reason(tmp_path, library_system):
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    (tmp_path / "Bad.hwm").write_text("{not json")
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Bad")
    event = reg.get_lastevent("testlib:macro:Bad")
    assert event is not None
    assert event.event_type is LifeCycleEventType.CLASS_RELOAD_FAILED


def test_editing_a_macro_file_reloads_its_template(tmp_path, library_system):
    """The watcher's MODIFIED is the only reload trigger (decision 9)."""
    from haywire.core.registry.events import FileChangeEvent, FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    path = _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT, description="first"))
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.add_folder(str(tmp_path), identity)

    path.write_text(json.dumps(_document(_INPUT, _OUTPUT, description="second")))
    reg.event_dispatcher(
        FileChangeEvent(
            file_path=str(path),
            event_type=FileEventType.MODIFIED,
            library_identity=identity,
            timestamp=0.0,
        )
    )

    assert reg.get("testlib:macro:Blur").class_identity.description == "second"
    assert reg.get_lastevent("testlib:macro:Blur").event_type is LifeCycleEventType.CLASS_RELOADED
