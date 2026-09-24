"""Writing a planned node, and waiting for the registry's answer.

The file watcher is never started here. The tests play its part by handing a
``FileChangeEvent`` to a real ``NodeRegistry``, from a worker thread as the
watcher does, so the registration path under test is the shipped one.
"""

import asyncio
import threading
import time
from pathlib import Path

import pytest

from haywire.core.authoring import (
    NodeFields,
    RegistrationWatch,
    linked_additions,
    plan_node,
    undeclared_imports,
    write_node,
)
from haywire.core.errors.ledger import ErrorLedger
from haywire.core.library.haybale_toml import read_haybale_toml, union_linked_libraries
from haywire.core.node.registry import NodeRegistry
from haywire.core.registry.base import FileChangeEvent, FileEventType

from .conftest import BROKEN, FakeLibraries

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _fields(class_name="BlurNode") -> NodeFields:
    return NodeFields(label="Blur", class_name=class_name, menu="mine", search_tags=[], description="")


def _event(path: Path, identity, event_type=FileEventType.CREATED) -> FileChangeEvent:
    return FileChangeEvent(
        file_path=str(path), event_type=event_type, library_identity=identity, timestamp=time.time()
    )


def _dispatch_later(registry: NodeRegistry, event: FileChangeEvent) -> threading.Thread:
    """Deliver ``event`` from another thread, as the watcher's debounce timer would."""
    thread = threading.Thread(target=registry.event_dispatcher, args=(event,))
    thread.start()
    return thread


@pytest.fixture
def src_libraries(dst_identity) -> FakeLibraries:
    """Installed libraries in which ``haybale_src`` is a registered haywire library."""
    return FakeLibraries(dst_identity, dists={"src": "haybale-src"})


# ── the write ────────────────────────────────────────────────────────────────


def test_the_write_puts_the_planned_source_on_disk(src_modules, target, libraries, dst_library):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)

    path = write_node(plan, dst_library)

    assert path == plan.path
    assert path.read_text(encoding="utf-8") == plan.source


def test_a_refused_plan_is_never_written(src_modules, target, libraries, dst_library):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(class_name="1Bad"), target, libraries)
    with pytest.raises(ValueError, match="cannot be written"):
        write_node(plan, dst_library)


def test_a_file_that_appeared_since_the_plan_is_not_overwritten(src_modules, target, libraries, dst_library):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)
    plan.path.write_text("# mine\n")

    with pytest.raises(FileExistsError):
        write_node(plan, dst_library)
    assert plan.path.read_text() == "# mine\n"


# ── linked registration ─────────────────────────────────────────────────────


def test_a_clone_importing_another_library_links_it(src_modules, target, src_libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, src_libraries)
    assert plan.linked_additions == ["haybale_src"]


def test_a_same_library_clone_links_nothing(src_modules, target, src_libraries, dst_identity):
    single, _multi = src_modules
    dst_identity.module_name = "haybale_src"
    plan = plan_node(single.SingleNode, _fields(), target, src_libraries)
    assert plan.linked_additions == []


def test_the_builtin_template_links_nothing(target, src_libraries):
    from haywire.barn.builtin.nodes.templates.data_node import DataNodeTemplate

    plan = plan_node(DataNodeTemplate, _fields(), target, src_libraries)
    assert plan.refusal is None
    assert plan.linked_additions == []
    assert plan.free_names == []


def test_the_write_unions_additions_and_keeps_existing_entries(
    src_modules, target, src_libraries, dst_library, dst_identity
):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, src_libraries)

    write_node(plan, dst_library)

    on_disk = read_haybale_toml(Path(dst_identity.folder_path))["linked_libraries"]
    assert on_disk == ["haybale_kept", "haybale_src"]
    # Refreshed in place, before the watcher sees the .py.
    assert dst_library.identity.linked_libraries == ["haybale_kept", "haybale_src"]


def test_union_adds_only_what_is_missing(packages):
    _src, dst = packages
    assert union_linked_libraries(dst, ["haybale_kept", "haybale_new", "haybale_new"]) == ["haybale_new"]
    assert read_haybale_toml(dst)["linked_libraries"] == ["haybale_kept", "haybale_new"]
    assert union_linked_libraries(dst, ["haybale_kept"]) == []


def test_the_new_module_tracks_the_added_library(
    src_modules, target, src_libraries, dst_library, dst_identity
):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, src_libraries)
    registry = NodeRegistry()

    write_node(plan, dst_library)
    registry.event_dispatcher(_event(plan.path, dst_identity))

    assert registry.get(plan.registry_key) is not None
    assert "haybale_src." in registry._dependency_graph._module_scope_prefixes[plan.module_name]


def test_undeclared_imports_name_what_the_pyproject_lacks(src_modules, target, src_libraries, dst_identity):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, src_libraries)
    # haywire-core is declared by the fixture pyproject; haybale-src is not.
    assert undeclared_imports(plan.source, dst_identity, src_libraries) == ["haybale-src"]
    assert linked_additions(plan.source, dst_identity, src_libraries) == ["haybale_src"]


# ── the registration watch ──────────────────────────────────────────────────


def _watched_write(registry, ledger, module_name, registry_key, write, event, timeout_s=5.0):
    async def _go():
        with RegistrationWatch(registry, ledger, module_name, registry_key) as watch:
            write()
            thread = _dispatch_later(registry, event) if event is not None else None
            outcome = await watch.result(timeout_s)
        if thread is not None:
            thread.join()
        return outcome

    return asyncio.run(_go())


def test_a_good_file_is_reported_added(src_modules, target, libraries, dst_library, dst_identity):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)
    registry = NodeRegistry()

    outcome = _watched_write(
        registry,
        ErrorLedger(),
        plan.module_name,
        plan.registry_key,
        lambda: write_node(plan, dst_library),
        _event(plan.path, dst_identity),
    )

    assert outcome.status == "added"
    assert outcome.registry_key == "dst:node:BlurNode"


def test_an_overwrite_is_reported_reloaded(src_modules, target, libraries, dst_library, dst_identity):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)
    registry = NodeRegistry()
    write_node(plan, dst_library)
    registry.event_dispatcher(_event(plan.path, dst_identity))

    outcome = _watched_write(
        registry,
        ErrorLedger(),
        plan.module_name,
        None,
        lambda: plan.path.write_text(plan.source + "\n# edited\n"),
        _event(plan.path, dst_identity, FileEventType.MODIFIED),
    )

    assert outcome.status == "reloaded"
    assert outcome.registry_key == plan.registry_key


def test_a_file_whose_import_raises_is_reported_failed_with_the_ledger_entry(
    dst_library, dst_identity, monkeypatch
):
    from haywire.core.di import context as di_context

    # The registry logs through the ambient ledger; give it a fresh one.
    ledger = ErrorLedger()
    monkeypatch.setattr(di_context, "_error_ledger", ledger)
    path = Path(dst_identity.folder_path) / "nodes" / "broken.py"
    registry = NodeRegistry()

    outcome = _watched_write(
        registry,
        ledger,
        "haybale_dst.nodes.broken",
        None,
        lambda: path.write_text(BROKEN),
        _event(path, dst_identity),
    )

    assert outcome.status == "failed"
    assert outcome.errors
    assert outcome.errors[0].module_name == "haybale_dst.nodes.broken"
    assert path.exists(), "a failed file stays on disk"


def test_nothing_arriving_is_reported_as_a_timeout(dst_identity):
    outcome = _watched_write(
        NodeRegistry(), ErrorLedger(), "haybale_dst.nodes.nothing", None, lambda: None, None, timeout_s=0.1
    )
    assert outcome.status == "timeout"
    assert outcome.registry_key is None


def test_a_watch_needs_something_to_match():
    with pytest.raises(ValueError, match="needs a module_name"):
        RegistrationWatch(NodeRegistry(), ErrorLedger(), None, None)


def test_the_watch_unsubscribes_on_exit(dst_identity):
    registry, ledger = NodeRegistry(), ErrorLedger()

    async def _go():
        with RegistrationWatch(registry, ledger, "m", None):
            assert registry._batch_event_subscribers
        assert not registry._batch_event_subscribers
        assert not ledger._listeners

    asyncio.run(_go())
