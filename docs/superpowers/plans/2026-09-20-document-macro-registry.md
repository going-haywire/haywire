# DocumentRegistry + MacroRegistry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register `.hwm` macro files as components — a file-backed registry that hands back a Macro template satisfying the same `RegisteredClass` contract a node class does.

**Architecture:** `DocumentRegistry(ComponentRegistry[T])` globs one suffix, parses on load, hashes content, and maps CREATED/MODIFIED/DELETED onto the CLASS_ADDED/RELOADED/REMOVED lifecycle. `MacroRegistry(DocumentRegistry[MacroTemplate])` adds `.hwm`, containment validation (decision 13) and the cycle backstop (decision 14). This is step 2 of [03-macro.md](03-macro.md), covering decisions 4, 5, 13, 14-backstop and 17.

**Tech Stack:** Python 3.12, mypy, ruff (line-length 109), pytest.

## Global Constraints

- **Step 1 is landed and is the foundation:** `ComponentRegistry` lives at `haywire/core/registry/component.py`, `add_folder`/`remove_folder` are abstract on it, and the file-change vocabulary is in `haywire/core/registry/events.py`. Do not reopen that seam.
- **No `MacroNode`, no factory dispatch, no menu, no `to_dict` skip.** Those are steps 3 and 5. This step ends with macros *registered and queryable*, nothing placing them.
- **Containment and cycles are checked over dicts**, against `NodeRegistry`, without instantiating a node (decision 13). Instantiating would pull hardware grabs onto a registry scan.
- **A template satisfies `RegisteredClass`** (decision 4): read-only `class_identity` and `class_library` properties. Kind-generic consumers (`extract.py`, `_helpers.py`) call `registry.get(key).class_identity` and must never learn it is not a class.
- **`get()` returns the template itself**, not a class. `ComponentRegistry._classes` is typed `Dict[str, type[T]]`; a template is an *instance*. Task 1 Step 1 resolves this typing — read it before writing code.
- **Gate:** `uv run ruff check .` AND `uv run ruff format --check .`, repo-wide mypy over the CLAUDE.md paths, and `uv run pytest -m "not browser and not perf"`. Baseline to beat: **5571 passed**, ruff/format/mypy all clean at `b2ec328f`.
- Docstrings per [.claude/rules/python-docs.md](../../../.claude/rules/python-docs.md).

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/registry/document.py` | **Create.** `DocumentRegistry` — suffix glob, parse, content hash, file-event → lifecycle mapping. Kind-agnostic. |
| `packages/haywire-core/src/haywire/core/macro/template.py` | **Create.** `MacroTemplate` — parsed document + path + hash + `class_identity`/`class_library`. |
| `packages/haywire-core/src/haywire/core/macro/registry.py` | **Create.** `MacroRegistry` — `.hwm`, containment (13), cycle backstop (14), filestem rule (17). |
| `packages/haywire-core/src/haywire/core/macro/__init__.py` | **Create.** Exports `MacroTemplate`, `MacroRegistry`. |
| `packages/haywire-core/src/haywire/core/library/kinds.py` | **Modify.** `"macro"` in all three maps. |
| `packages/haywire-core/src/haywire/core/library/base.py:253-265` | **Modify.** `_REGISTRY_SCAN_PRIORITY["MacroRegistry"] = 75`. |
| `packages/haywire-studio/src/haywire_studio/init.py` | **Modify.** Scaffold a `macros/` folder + its `add_folder_to_registry` line. |
| `tests/core/test_registry/test_document_registry.py` | **Create.** Suffix routing, hash short-circuit, event mapping, parse failure. |
| `tests/core/test_macro/test_macro_registry.py` | **Create.** Template identity, containment, cycles, filestem rule. |

A new `core/macro/` package rather than folding into `core/graph/`: a macro is a component kind with a registry, and every other kind (`node/`, `type/`, `adapter/`) owns its own package.

---

## Task 1: `DocumentRegistry`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/registry/document.py`
- Test: `tests/core/test_registry/test_document_registry.py`

**Interfaces:**
- Consumes: `ComponentRegistry` (`haywire.core.registry.component`), `FileChangeEvent`/`FileEventType`/`HotReloadRegistry` (`haywire.core.registry.events`), `LifeCycleEvent`/`LifeCycleEventType` (`haywire.core.registry.lifecycle_event`).
- Produces: `DocumentRegistry(ComponentRegistry[T])` with:
  - `SUFFIX: ClassVar[str]` — subclass hook, e.g. `".hwm"`.
  - `_parse(self, path: Path, text: str) -> T` — abstract; raises to signal a bad document.
  - `_document_key(self, path: Path, library_identity: LibraryIdentity) -> str` — abstract; the registry key.
  - `add_folder` / `remove_folder` — concrete, glob `SUFFIX`.
  - `event_dispatcher(self, event: FileChangeEvent)` — concrete.
  - `_hashes: Dict[str, str]` — registry_key → sha256 of the parsed text.
  - `register_file(self, path: str, library_identity: LibraryIdentity) -> str | None` — synchronous registration (step 8's promote needs it; it is the one place `add_folder` and the watcher share).

- [ ] **Step 1: Resolve the `type[T]` vs instance typing**

`ComponentRegistry._classes` is `Dict[str, type[T]]` with `T` bound to `RegisteredClass`. A `MacroTemplate` is an **instance** satisfying that Protocol, not a class.

Do **not** widen `ComponentRegistry`. Declare `T` on `DocumentRegistry` bound to `RegisteredClass` and store templates in `_classes` with a narrow, commented cast at each write:

```python
    def _store(self, registry_key: str, template: T) -> None:
        """Put a template in the element map.

        ``ComponentRegistry`` types its map as ``type[T]`` because a class
        registry stores classes. A document registry stores instances that
        satisfy the same Protocol; consumers only ever read ``class_identity``
        and ``class_library`` off the result, which both provide.
        """
        self._classes[registry_key] = cast("type[T]", template)
```

Add the same one-line note to the class docstring. If mypy rejects the cast, that is the signal to revisit — report it rather than reaching for `# type: ignore`.

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_registry/test_document_registry.py`:

```python
"""``DocumentRegistry`` maps file events onto the component lifecycle."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


class _Doc:
    """A parsed document satisfying RegisteredClass."""

    def __init__(self, registry_key, text):
        from haywire.core.registry.identity import BaseIdentity

        self._identity = BaseIdentity(
            registry_id=registry_key.split(":")[-1],
            registry_key=registry_key,
            label=registry_key.split(":")[-1],
        )
        self._library = _identity()
        self.text = text

    @property
    def class_identity(self):
        return self._identity

    @property
    def class_library(self):
        return self._library


def _registry(fail_on: str = ""):
    """A DocumentRegistry over '.txt' that parses into _Doc."""
    from haywire.core.registry.document import DocumentRegistry

    class _Fake(DocumentRegistry):
        SUFFIX = ".txt"

        def _parse(self, path: Path, text: str):
            if fail_on and fail_on in text:
                raise ValueError("bad document")
            return _Doc(self._document_key(path, _identity()), text)

        def _document_key(self, path: Path, library_identity):
            return f"{library_identity.name}:doc:{path.stem}"

    return _Fake()


def _event(path, kind, identity=None):
    from haywire.core.registry.events import FileChangeEvent, FileEventType

    return FileChangeEvent(
        file_path=str(path),
        event_type=kind,
        library_identity=identity or _identity(),
        timestamp=0.0,
    )


def test_a_created_file_registers_and_emits_added(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    reg = _registry()
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))

    reg.event_dispatcher(_event(doc, FileEventType.CREATED, _identity(str(tmp_path))))

    assert reg.has("testlib:doc:alpha")
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_ADDED]


def test_a_file_of_another_suffix_is_ignored(tmp_path):
    from haywire.core.registry.events import FileEventType

    other = tmp_path / "notes.md"
    other.write_text("hello")
    reg = _registry()

    reg.event_dispatcher(_event(other, FileEventType.CREATED, _identity(str(tmp_path))))

    assert reg.list_names() == []


def test_unchanged_content_on_modify_emits_nothing(tmp_path):
    from haywire.core.registry.events import FileEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert batches == [] or batches[-1] == []


def test_changed_content_on_modify_emits_reloaded(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.write_text("goodbye")
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_RELOADED]


def test_a_deleted_file_unregisters_and_emits_removed(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.unlink()
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.DELETED, identity))

    assert not reg.has("testlib:doc:alpha")
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_REMOVED]


def test_a_parse_failure_keeps_the_key_and_emits_reload_failed(tmp_path):
    """A broken save must not silently drop the component."""
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("good")
    identity = _identity(str(tmp_path))
    reg = _registry(fail_on="BROKEN")
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.write_text("BROKEN")
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert reg.has("testlib:doc:alpha"), "the previous good document stays registered"
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_RELOAD_FAILED]
    assert batches[-1][0].error is not None


def test_add_folder_registers_every_matching_file(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "c.md").write_text("c")
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert set(reg.list_names()) == {"testlib:doc:a", "testlib:doc:b"}


def test_remove_folder_unregisters_them_again(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.add_folder(str(tmp_path), identity)

    reg.remove_folder(str(tmp_path), identity)

    assert reg.list_names() == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/core/test_registry/test_document_registry.py -q`
Expected: collection error — `No module named 'haywire.core.registry.document'`.

- [ ] **Step 4: Implement `DocumentRegistry`**

Create `packages/haywire-core/src/haywire/core/registry/document.py`. It must:

1. Declare `SUFFIX: ClassVar[str] = ""` and abstract `_parse` / `_document_key`.
2. `add_folder`: record `_folder_to_library[folder_path]`, glob `*{SUFFIX}` (non-recursive, matching `KIND_FOLDERS` flatness), call `register_file` per hit, then `_notify_batch_event_subscribers()` once.
3. `remove_folder`: `del self._folder_to_library[folder_path]`, unregister every key whose path is under the folder, then notify once.
4. `event_dispatcher`: return immediately unless `event.file_path.endswith(self.SUFFIX)` — the same early-return shape `BaseRegistry` uses for `.py`, and for the same reason (the watcher routes every file under a claimed folder). Then branch on `event_type`:
   - CREATED → parse, store, queue `CLASS_ADDED`
   - MODIFIED → read, hash; equal to stored hash → **return without notifying**; else parse, replace, queue `CLASS_RELOADED`
   - DELETED → unregister, queue `CLASS_REMOVED`
   Wrap parse in try/except: on failure queue `CLASS_RELOAD_FAILED` carrying a `HaywireException` via `HaywireException.from_exception(...).enrich(registry_key=..., library_identity=...)`, **keep the existing entry registered**, and do not update the hash. Notify batch subscribers once at the end of every branch that queued something.
5. Track `_key_to_path: Dict[str, Path]` so `remove_folder` and DELETED can find keys by path.
6. Hash with `hashlib.sha256(text.encode()).hexdigest()`.

Mirror `BaseRegistry.event_dispatcher`'s logging shape (`logger.info` on entry, `self.logger.error` on failure) so a document reload reads the same in the log as a class reload.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core/test_registry/test_document_registry.py -q`
Expected: 8 passed.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/registry/ tests/core/test_registry/
uv run ruff format --check packages/haywire-core/src/haywire/core/registry/ tests/core/test_registry/
uv run mypy packages/haywire-core/src/haywire/core/registry/
git add packages/haywire-core/src/haywire/core/registry/document.py tests/core/test_registry/test_document_registry.py
git commit -m "feat(registry) DocumentRegistry — components backed by files

Globs one suffix, parses on load, and maps file events onto the component
lifecycle. Unchanged content on MODIFIED emits nothing; a parse failure
keeps the previous document registered and reports CLASS_RELOAD_FAILED.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: `MacroTemplate`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/macro/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/macro/template.py`
- Test: covered by Task 3's suite (a template alone has no behaviour worth its own file).

**Interfaces:**
- Consumes: `NodeIdentity` (`haywire.core.node.identity`), `LibraryIdentity`.
- Produces:

```python
@dataclass
class MacroTemplate:
    document: dict[str, Any]     # BaseGraph.to_dict() output, minus 'key'
    path: Path
    content_hash: str
    _identity: NodeIdentity
    _library: LibraryIdentity

    @property
    def class_identity(self) -> NodeIdentity: ...
    @property
    def class_library(self) -> LibraryIdentity: ...

    @property
    def nodes(self) -> dict[str, Any]: ...      # document['nodes']
    @property
    def edges(self) -> dict[str, Any]: ...
    @property
    def subgraphs(self) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write it**

`class_identity` carries, per decision 4:
- `registry_id` = filestem, `registry_key` = `<lib>:macro:<Filestem>`
- `label` = filestem
- `description` = `document["meta"]["description"]`, defaulting to `""`
- `menu` = `f"{library_identity.name}/macros"` (decision 6 — fixed path)
- `hidden = False`

`NodeIdentity` is a dataclass with `search_tags`/`menu`/`help_md`/`help_url` and the `_is_*` flags; leave every flag at its default. Do **not** set `_is_graph_node` — that describes the placement node class, which this step does not build.

Keep `class_identity`/`class_library` as read-only `@property`, matching the `RegisteredClass` Protocol's variance note.

- [ ] **Step 2: Lint and commit** (tests land with Task 3)

```bash
uv run ruff check packages/haywire-core/src/haywire/core/macro/
uv run mypy packages/haywire-core/src/haywire/core/macro/
git add packages/haywire-core/src/haywire/core/macro/
git commit -m "feat(macro) MacroTemplate — a parsed .hwm under the class contract

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: `MacroRegistry` — containment, cycles, filestem

**Files:**
- Create: `packages/haywire-core/src/haywire/core/macro/registry.py`
- Modify: `packages/haywire-core/src/haywire/core/macro/__init__.py`
- Test: `tests/core/test_macro/__init__.py`, `tests/core/test_macro/test_macro_registry.py`

**Interfaces:**
- Consumes: `DocumentRegistry` (Task 1), `MacroTemplate` (Task 2), `NodeRegistry` (`haywire.core.node.registry`).
- Produces: `MacroRegistry(DocumentRegistry[MacroTemplate])` with `SUFFIX = ".hwm"`, `_parse`, `_document_key`, and:
  - `_validate_containment(self, document: dict) -> tuple[bool, str | None]`
  - `_macro_keys_reachable_from(self, registry_key: str) -> set[str]` — transitive closure over templates, for the cycle backstop.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_macro/__init__.py` (empty) and `tests/core/test_macro/test_macro_registry.py`:

```python
"""``MacroRegistry``: a .hwm becomes a component, or is refused with a reason."""

import json

import pytest

pytestmark = pytest.mark.unit

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_ADD = "haybale-testing:node:TestAddFloatNode"


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(
        label="testlib", name="testlib", folder_path=folder_path, module_name="testlib"
    )


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


def _write(tmp_path, stem, document):
    path = tmp_path / f"{stem}.hwm"
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
    assert template.class_identity.menu == "testlib/macros"


def test_the_template_satisfies_the_registered_class_contract(tmp_path, library_system):
    """Kind-generic consumers read these two off get() and must not learn the difference."""
    _write(tmp_path, "Blur", _document(_INPUT, _OUTPUT))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    template = reg.get("testlib:macro:Blur")
    assert template.class_identity is not None
    assert template.class_library.name == "testlib"


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
    assert "exactly one" in str(event.error)


def test_a_macro_containing_an_event_node_is_refused(tmp_path, library_system):
    _write(tmp_path, "Evented", _document(_INPUT, _OUTPUT, "haybale-testing:node:TestBeginPlayNode"))
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Evented")


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
    document = _document(_INPUT, _OUTPUT, "testlib:macro:Loop")
    _write(tmp_path, "Loop", document)
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Loop")


def test_a_mutual_cycle_is_refused(tmp_path, library_system):
    """A placing B, B placing A: whichever closes the loop is refused."""
    _write(tmp_path, "A", _document(_INPUT, _OUTPUT, "testlib:macro:B"))
    _write(tmp_path, "B", _document(_INPUT, _OUTPUT, "testlib:macro:A"))
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not (reg.has("testlib:macro:A") and reg.has("testlib:macro:B"))


def test_unparseable_json_is_refused_with_a_reason(tmp_path, library_system):
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    (tmp_path / "Bad.hwm").write_text("{not json")
    reg = _registry()
    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert not reg.has("testlib:macro:Bad")
    event = reg.get_lastevent("testlib:macro:Bad")
    assert event is not None
    assert event.event_type is LifeCycleEventType.CLASS_RELOAD_FAILED
```

Before writing the implementation, run this to confirm the two fixture/registry-key assumptions the tests make:

```bash
uv run python -c "
from haywire.core.node.registry import NodeRegistry
print([k for k in NodeRegistry().list_names() if 'BeginPlay' in k or 'Event' in k][:5])
"
grep -rn 'def library_system' tests/conftest.py | head -3
```

If no EVENT-typed test node exists under that key, substitute the one that does and update `_ADD`/the EVENT key accordingly — do not invent a registry key. If `library_system` is not a fixture, find the one that builds a populated `NodeRegistry` and use it.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_macro/test_macro_registry.py -q`
Expected: collection error — `No module named 'haywire.core.macro.registry'`.

- [ ] **Step 3: Implement `MacroRegistry`**

`_document_key`: `f"{library_identity.name}:macro:{path.stem}"`.

`_parse`:
1. `json.loads(text)` — a `JSONDecodeError` propagates and `DocumentRegistry` turns it into `CLASS_RELOAD_FAILED`.
2. Filestem rule (17): `re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", path.stem)`. A non-conforming stem is **skipped with a ledger warning**, not a failure — so `add_folder` must filter these *before* calling `register_file`. Implement the regex check in `add_folder`'s glob loop and log via `HaywireException(...).log(self.logger)`.
3. Containment (13) via `_validate_containment`; raise `ValueError(reason)` on failure.
4. Cycle backstop (14) via `_macro_keys_reachable_from`; raise `ValueError` naming the cycle.
5. Build and return the `MacroTemplate`.

`_validate_containment(document)` mirrors `StructuralValidator.validate_subgraph_contents`
([structural_validator.py:337-395](../../../packages/haywire-core/src/haywire/core/validation/structural_validator.py#L337-L395)) but reads **dicts**:

```python
    def _validate_containment(self, document: dict) -> tuple[bool, str | None]:
        """Exactly one Subgraph Input and Output; no EVENT or OUTPUT node.

        Reads each node's ``registry_key`` against ``NodeRegistry`` rather than
        instantiating: a registry scan must not construct nodes, which would
        acquire whatever hardware their ``init`` opens.
        """
        from haywire.core.di.config import get_node_registry
        from haywire.core.node.behavior import NodeType

        registry = get_node_registry()
        inputs, outputs, offenders = [], [], []
        for node_id, entry in document.get("nodes", {}).items():
            cls = registry.get(entry.get("registry_key", ""))
            if cls is None:
                continue  # A missing node class is the placement's problem, not the file's.
            identity = cls.class_identity
            node_type = cls.class_behavior.node_type
            if NodeType.BOUNDARY in node_type:
                if identity._is_subgraph_input:
                    inputs.append(node_id)
                if identity._is_subgraph_output:
                    outputs.append(node_id)
                continue
            if NodeType.EVENT in node_type or NodeType.OUTPUT in node_type:
                offenders.append(f"{node_id} ({identity.label})")
        ...
```

Keep the two failure messages textually close to the validator's, so a user meets one wording whether the Subgraph is a Group or a macro.

`_macro_keys_reachable_from(key)`: walk `document["nodes"]` for `registry_key`s whose kind segment is `macro`, recursing through `self.get(...)` templates already registered, with a `seen` set. A key reachable from itself is a cycle.

Resolve the registry via DI (`get_node_registry()`), not by constructing one — per [.insights/project_settings_registry_construction_side_effects.md](../../../.insights/project_settings_registry_construction_side_effects.md), building registries has side effects.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_macro/ -q`
Expected: 10 passed.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/macro/ tests/core/test_macro/
uv run ruff format --check packages/haywire-core/src/haywire/core/macro/ tests/core/test_macro/
uv run mypy packages/haywire-core/src/haywire/core/macro/
git add packages/haywire-core/src/haywire/core/macro/ tests/core/test_macro/
git commit -m "feat(macro) MacroRegistry — .hwm files as components

Containment and cycles are validated over the document's dicts against
NodeRegistry, so a scan never instantiates a node. A non-conforming
filestem is skipped with a warning; a cycle or a missing boundary node
is refused with the reason.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Wire the kind into the library system

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/kinds.py`
- Modify: `packages/haywire-core/src/haywire/core/library/base.py:253-265`
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Test: `tests/core/test_macro/test_macro_kind_wiring.py`

**Interfaces:**
- Consumes: `MacroRegistry` (Task 3).
- Produces: `"macro"` resolvable through `kind_registry_map()`, `KIND_FOLDERS`, `canon_area`.

- [ ] **Step 1: Write the failing test**

```python
"""The macro kind is wired into the maps every kind-generic consumer reads."""

import pytest

pytestmark = pytest.mark.unit


def test_the_kind_maps_to_the_macro_registry():
    from haywire.core.library.kinds import kind_registry_map
    from haywire.core.macro.registry import MacroRegistry

    assert kind_registry_map()["macro"] is MacroRegistry


def test_the_kind_maps_to_the_macros_folder():
    from haywire.core.library.kinds import KIND_FOLDERS

    assert KIND_FOLDERS["macro"] == "macros"


def test_the_kind_has_a_canon_area():
    from haywire.core.library.kinds import canon_area

    assert canon_area("macro") == "macros"


def test_macros_scan_after_nodes():
    """Containment reads node classes, so NodeRegistry (70) must be populated first."""
    from haywire.core.library.base import BaseLibrary

    priority = BaseLibrary._REGISTRY_SCAN_PRIORITY
    assert priority["MacroRegistry"] == 75
    assert priority["NodeRegistry"] < priority["MacroRegistry"]
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/core/test_macro/test_macro_kind_wiring.py -q`
Expected: FAIL — `KeyError: 'macro'`.

- [ ] **Step 3: Make the three edits**

In `kinds.py`, add the import inside `kind_registry_map()` (it is function-local by convention there, to keep import cost off module load):

```python
    from haywire.core.macro.registry import MacroRegistry
```
and `"macro": MacroRegistry,` to the returned dict; `"macro": "macros",` to `KIND_FOLDERS`; `"macro": "macros",` to `_KIND_TO_AREA`.

In `library/base.py`, add `"MacroRegistry": 75,` between `NodeRegistry` (70) and `SkinRegistry` (80).

In `init.py`, add `macros/` to the scaffolded folders and its `add_folder_to_registry` line, following exactly what the neighbouring kinds do. Read the file first — mirror the existing pattern rather than inventing one.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_macro/ -q`
Expected: 14 passed.

- [ ] **Step 5: Verify the scaffold actually works end to end**

```bash
uv run haywire init /tmp/macro_scaffold_check
ls /tmp/macro_scaffold_check/*/macros 2>/dev/null && echo "macros/ scaffolded"
rm -rf /tmp/macro_scaffold_check
```
Expected: the folder exists. If `haywire init` prompts interactively, pass whatever flag makes it non-interactive (check `--help`); do not skip this step — a scaffold line that does not run is the kind of thing only a real invocation catches.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/kinds.py packages/haywire-core/src/haywire/core/library/base.py packages/haywire-studio/src/haywire_studio/init.py tests/core/test_macro/test_macro_kind_wiring.py
git commit -m "feat(macro) wire the macro kind into the library system

Kind maps, a macros/ folder in the scaffold, and a scan priority of 75 —
after NodeRegistry, because containment reads node classes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Full gate

- [ ] **Step 1: Confirm `barn/haybale-testing` is committed**

Run: `git status --porcelain barn/haybale-testing`
Expected: empty. If not, commit first — `tests/studio/test_docs/test_generate.py` git-checkouts that directory in teardown and will discard uncommitted work there.

- [ ] **Step 2: Repo-wide ruff, both commands**

```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: "All checks passed!" and no reformat candidates.

- [ ] **Step 3: Repo-wide mypy**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: "Success: no issues found". The baseline is clean as of `24f6ba0f`, so any error is this step's.

- [ ] **Step 4: Full non-browser suite**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/gate2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/gate2.log
grep -E "passed|failed" /tmp/gate2.log | tail -1
```
Expected: `exit=0`, no failures, **5593 passed** (5571 + 8 document + 10 macro + 4 wiring). Timeout ≥ 600000 ms.

- [ ] **Step 5: Confirm the step's boundary held**

```bash
grep -rn "MacroNode\|subgraph_key\|template_key" --include="*.py" packages/haywire-core/src/haywire/core/macro/
```
Expected: no output. Those belong to step 5; if they appear here, the placement node leaked into the registry step.

---

## Notes for the implementer

- **The `type[T]` cast in Task 1 Step 1 is the one genuinely novel thing here.** Everything else follows a shape that already exists. If it fights you, stop and report rather than widening `ComponentRegistry` — that class is shared with `BaseRegistry` and step 1's tests pin its contract.
- **`get_lastevent` is how the tests observe failures** — it survives the queue drain, which is exactly what step 1's `test_last_event_survives_the_queue_drain` pinned.
- **Containment deliberately skips unknown node classes.** A macro referencing a node from an uninstalled library is not a malformed macro; the *placement* takes the error-node path at step 3. Refusing the file here would make an absent library look like a corrupt document.
- **Do not add `.hwm` handling to the file watcher.** It is suffix-agnostic already ([file_watcher.py:106-131](../../../packages/haywire-core/src/haywire/core/library/file_watcher.py#L106-L131)); the suffix filter is each registry's own, which is why `DocumentRegistry.event_dispatcher` opens with one.
