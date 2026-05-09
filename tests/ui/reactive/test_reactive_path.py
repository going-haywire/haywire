"""ReactivePath identifies one reactive field on a class. Phase 1: data only."""

from haywire.core.session.reactive import ReactivePath


def test_reactive_path_identity():
    class Owner:
        pass

    p1 = ReactivePath(owner=Owner, attr="x")
    p2 = ReactivePath(owner=Owner, attr="x")
    assert p1 == p2
    assert hash(p1) == hash(p2)


def test_reactive_path_repr():
    class SomeContext:
        pass

    p = ReactivePath(owner=SomeContext, attr="active_node")
    assert "SomeContext" in repr(p)
    assert "active_node" in repr(p)
