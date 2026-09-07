"""NodeSkin.is_collapsed — the Node collapse resolver every skin's render()
consults once, up front, to pick its fold-vs-unfold branch.

Replaces the deleted NodeVisibility/resolve_node_visibility (see ADR 0032's
"Superseded" section, 2026-09): once NodeDetail stopped needing a resolved
value to hand skins, a value OBJECT for one boolean had no purpose left —
every real caller already branches on the fold state before it would ever
touch a second field on it. What survives is this one method: an overridable
hook (see ErrorNodeSkin, which used to override show_of() the same way) that
degrades to unfolded rather than raising on a broken props bag.
"""

import pathlib
from typing import cast

import pytest

pytestmark = pytest.mark.unit


class _FakeProps:
    def __init__(self, collapsed):
        self.collapsed = collapsed


class _FakeNode:
    def __init__(self, props):
        self.props = props


class _FakeWrapper:
    def __init__(self, props):
        self.node = _FakeNode(props)


def _wrapper(collapsed):
    return cast("object", _FakeWrapper(_FakeProps(collapsed)))


@pytest.fixture
def skin():
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    # is_collapsed reads nothing off self — a bare instance is fine, and
    # avoids pulling in a real widget factory just to read one prop.
    return StackedNodeSkin.__new__(StackedNodeSkin)


class TestIsCollapsed:
    def test_reads_the_prop(self, skin):
        assert skin.is_collapsed(_wrapper(True)) is True
        assert skin.is_collapsed(_wrapper(False)) is False

    def test_unreadable_props_degrades_to_unfolded_rather_than_raising(self, skin):
        """A stale or exploding props bag must not take a node card down.
        Render path: degrade toward MORE drawing, never less."""

        class Exploding:
            @property
            def collapsed(self):
                raise RuntimeError("boom")

        wrapper = _FakeWrapper(Exploding())
        assert skin.is_collapsed(cast("object", wrapper)) is False

    def test_missing_node_degrades_rather_than_raising(self, skin):
        class NoNode:
            @property
            def node(self):
                raise AttributeError("detached")

        assert skin.is_collapsed(cast("object", NoNode())) is False


class TestErrorSkinNeverFolds:
    """ErrorNodeSkin does NOT override is_collapsed (it inherits the base
    resolver verbatim) — its "never folds" guarantee lives entirely in its
    own render(), which never calls is_collapsed or branches on collapse at
    all. This pins that absence: a future edit that makes render() consult
    is_collapsed would need to also override it, or a broken node's card
    could fold and hide the fact that anything is wrong."""

    def test_render_never_calls_is_collapsed(self):
        import inspect

        from haybale_studio.skins.error_skin import ErrorNodeSkin

        source = inspect.getsource(ErrorNodeSkin.render)
        assert "is_collapsed" not in source
        assert "props.collapsed" not in source


class TestSkinsHonourNodeCollapse:
    """ADR 0032 decision 7: skins honour Node collapse, the framework does not
    enforce it. Nothing can cover a third-party skin, so this covers ours —
    the same source-inspection approach ``test_node_skin_settings.py`` uses,
    and for the same reason: "does this skin consult the axis" is not
    observable from a rendered card.

    A skin that ignores it renders every port unfolded — slower, never broken.
    """

    _ROOT = pathlib.Path(__file__).resolve().parents[3]

    # Every in-repo directory that holds node skins. A new one added without
    # being listed here is invisible to this check, which is what
    # `test_every_known_skin_dir_exists` is for.
    _SKIN_DIRS = (
        _ROOT / "barn/haybale-studio/haybale_studio/skins",
        _ROOT / "packages/haywire-core/src/haywire/barn/builtin/skins",
    )

    # Skins that ignore collapse ON PURPOSE. Each entry is a decision, not a
    # backlog item — adding one means arguing why that card should stay
    # full-size when the user folds every node in the graph.
    #
    # The error skin is NOT here. It ignores collapse, but explicitly — see
    # TestErrorSkinNeverFolds above — and it still calls get_visible_ports(),
    # a symbol this sweep also accepts as "consults the port-list contract".
    _EXEMPT = {
        # Already a bare dot on a wire — a folded card would be BIGGER, and it
        # has no labels or widgets for a rank to remove.
        "reroute_skin.py",
    }

    def test_every_known_skin_dir_exists(self):
        """Guard the premise — a stale path makes the sweep below vacuous."""
        for directory in self._SKIN_DIRS:
            assert directory.is_dir(), f"skin directory not found: {directory}"
        assert (self._SKIN_DIRS[0] / "stacked_skin.py").is_file()

    def test_every_non_exempt_skin_consults_the_port_list_contract(self):
        unaware = []
        for directory in self._SKIN_DIRS:
            for path in sorted(directory.glob("*_skin.py")):
                if path.name in self._EXEMPT:
                    continue
                source = path.read_text()
                if not any(
                    token in source for token in ("is_collapsed", "get_visible_ports", "get_folded_ports")
                ):
                    unaware.append(str(path.relative_to(self._ROOT)))

        assert not unaware, (
            f"{unaware} render node cards without consulting is_collapsed() or "
            f"either port-list method. They will draw every port unfolded, so "
            f"graph-level collapse silently does nothing for nodes using them. "
            f"Wire them, or add them to _EXEMPT with a reason."
        )

    def test_exempt_skins_still_exist(self):
        """A rename would otherwise turn an exemption into a silent hole."""
        present = {p.name for d in self._SKIN_DIRS for p in d.glob("*_skin.py")}
        missing = self._EXEMPT - present
        assert not missing, f"{sorted(missing)} no longer exist — update _EXEMPT"


@pytest.fixture
def graph(library_system):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    return BaseGraph(filestem="is_collapsed test", validation_scheduler=SyncScheduler())


@pytest.mark.integration
class TestAgainstRealNodes:
    def _add_node(self, graph_obj):
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))

    def test_resolves_a_real_wrapper_at_the_default(self, graph):
        from haybale_studio.skins.stacked_skin import StackedNodeSkin

        wrapper = self._add_node(graph)
        skin_instance = StackedNodeSkin.__new__(StackedNodeSkin)

        assert skin_instance.is_collapsed(wrapper) is False

    def test_node_writes_reach_it(self, graph):
        """Collapse is node-only now (no graph tier to mirror through), so
        the write that must reach the skin is the node's own."""
        from haybale_studio.skins.stacked_skin import StackedNodeSkin

        wrapper = self._add_node(graph)
        skin_instance = StackedNodeSkin.__new__(StackedNodeSkin)

        wrapper.node.props.collapsed = True
        assert skin_instance.is_collapsed(wrapper) is True
