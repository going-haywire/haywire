"""The Promote to Macro flow's state machine. UI rendering is not exercised here.

The property under test: nothing is written until the final step, so a user
who opens the flow, reads the path and closes it has changed nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


#: Real boundary-node keys. Containment is validated against NodeRegistry, so
#: a placeholder key passes only while no library system is loaded — which is
#: true of this file alone and false in a full run.
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


class _FakeDefinition:
    """Stands in for a SubgraphDefinition: serializes to a fixed document."""

    def __init__(self, label: str = "My Group", document: dict | None = None) -> None:
        self.label = label
        self._document = document or {
            "key": "g1",
            "nodes": {
                "b_in": {"node_id": "b_in", "registry_key": _INPUT},
                "b_out": {"node_id": "b_out", "registry_key": _OUTPUT},
            },
            "edges": {},
        }

    def to_dict(self) -> dict:
        return dict(self._document)


class _FakeSource:
    """Records the registration and the swap instead of performing them."""

    def __init__(self) -> None:
        self.registered: list[tuple[Path, str]] = []
        self.swapped: list[tuple[str, str]] = []
        self.registry_key: str | None = "haybale-example:macro:Blur"
        self.swap_refusal: str | None = None

    def register_macro_file(self, path: Path, library_id: str) -> str | None:
        self.registered.append((path, library_id))
        return self.registry_key

    def swap_card_for_placement(self, node_id: str, registry_key: str):
        self.swapped.append((node_id, registry_key))
        if self.swap_refusal is not None:
            return (None, self.swap_refusal)
        return ("placement_1", None)


def _target(folder: Path, library_id: str = "haybale-example", label: str = "Example"):
    from haywire.core.macro.promote import PromotionTarget

    return PromotionTarget(library_id=library_id, label=label, folder=folder, is_project_library=True)


def _flow(tmp_path: Path, *, source=None, definition=None, targets=None):
    from haybale_graph_editor._promote_flow import PromoteFlow

    return PromoteFlow(
        source=source or _FakeSource(),
        definition=definition or _FakeDefinition(),
        node_id="card_1",
        targets=targets if targets is not None else [_target(tmp_path)],
    )


# ---------------------------------------------------------------------------
# The name step
# ---------------------------------------------------------------------------


def test_the_name_is_suggested_from_the_group_label(tmp_path):
    flow = _flow(tmp_path, definition=_FakeDefinition(label="Blur Filter"))

    assert flow.name == "Blur_Filter"
    assert flow.name_refusal is None


def test_an_unusable_label_still_opens_with_a_valid_name(tmp_path):
    """The field must always open with something the rule accepts."""
    flow = _flow(tmp_path, definition=_FakeDefinition(label="!!!"))

    assert flow.name_refusal is None


def test_a_bad_name_is_refused_before_anything_is_planned(tmp_path):
    flow = _flow(tmp_path)
    flow.name = "9lives"

    assert flow.name_refusal is not None
    assert flow.can_plan is False


def test_the_default_target_is_the_first_offered(tmp_path):
    flow = _flow(tmp_path)

    assert flow.target is not None
    assert flow.target.library_id == "haybale-example"


def test_no_target_cannot_plan(tmp_path):
    flow = _flow(tmp_path, targets=[])

    assert flow.can_plan is False


# ---------------------------------------------------------------------------
# The plan step — read-only
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_planning_writes_nothing(tmp_path, anyio_backend):
    source = _FakeSource()
    flow = _flow(tmp_path, source=source)
    flow.name = "Blur"

    await flow.advance_from_name()

    assert flow.step == "planned"
    assert flow.plan is not None
    assert flow.plan.path == tmp_path / "Blur.hwm"
    assert not flow.plan.path.exists()
    assert source.registered == []


@pytest.mark.anyio
async def test_planning_without_a_target_reports_it(tmp_path, anyio_backend):
    flow = _flow(tmp_path, targets=[])

    await flow.advance_from_name()

    assert flow.step == "name"
    assert flow.error is not None


@pytest.mark.anyio
async def test_a_plan_over_an_existing_file_carries_the_refusal(tmp_path, anyio_backend):
    (tmp_path / "Blur.hwm").write_text("{}")
    flow = _flow(tmp_path)
    flow.name = "Blur"

    await flow.advance_from_name()

    assert flow.step == "planned"
    assert flow.plan.refusal is not None


# ---------------------------------------------------------------------------
# The promote step — the only one that writes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_promoting_writes_registers_and_swaps(tmp_path, anyio_backend):
    source = _FakeSource()
    flow = _flow(tmp_path, source=source)
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    assert flow.step == "promoted"
    assert (tmp_path / "Blur.hwm").exists()
    assert source.registered == [(tmp_path / "Blur.hwm", "haybale-example")]
    assert source.swapped == [("card_1", "haybale-example:macro:Blur")]
    assert flow.placement_node_id == "placement_1"


@pytest.mark.anyio
async def test_the_written_document_carries_no_subgraph_key(tmp_path, anyio_backend):
    """A macro document is a graph document; the Group's own key is not part of it."""
    import json

    flow = _flow(tmp_path)
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    written = json.loads((tmp_path / "Blur.hwm").read_text())
    assert "key" not in written


@pytest.mark.anyio
async def test_a_refused_plan_is_never_written(tmp_path, anyio_backend):
    source = _FakeSource()
    (tmp_path / "Blur.hwm").write_text("{}")
    flow = _flow(tmp_path, source=source)
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    assert flow.step == "planned"
    assert flow.error is not None
    assert source.registered == []
    assert source.swapped == []


@pytest.mark.anyio
async def test_a_registry_refusal_leaves_the_card_alone(tmp_path, anyio_backend):
    """The file is on disk but unregistered: swapping would strand the placement."""
    source = _FakeSource()
    source.registry_key = None
    flow = _flow(tmp_path, source=source)
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    assert flow.step == "planned"
    assert flow.error is not None
    assert source.swapped == []


@pytest.mark.anyio
async def test_a_swap_refusal_keeps_the_user_on_the_step(tmp_path, anyio_backend):
    source = _FakeSource()
    source.swap_refusal = "Node 'card_1' is not a Graph-node"
    flow = _flow(tmp_path, source=source)
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    assert flow.step == "planned"
    assert flow.error == "Node 'card_1' is not a Graph-node"


@pytest.mark.anyio
async def test_the_write_creates_the_macros_folder(tmp_path, anyio_backend):
    """A library scaffolded before macros existed has no macros/ folder yet."""
    folder = tmp_path / "macros"
    flow = _flow(tmp_path, targets=[_target(folder)])
    flow.name = "Blur"

    await flow.advance_from_name()
    await flow.advance_from_planned()

    assert (folder / "Blur.hwm").exists()
