"""Canon packaging: the component canons ship inside haywire-core and are readable at runtime."""

import pytest

from haywire.core.docs.canons import canons_dir, list_canon_areas, read_canon

pytestmark = pytest.mark.unit


def test_canons_dir_exists():
    assert canons_dir().is_dir()


def test_list_areas_contains_nodes():
    areas = list_canon_areas()
    assert "nodes" in areas
    assert areas == sorted(areas)


def test_read_canon_returns_markdown():
    text = read_canon("nodes")
    assert "worker" in text  # the node canon documents worker()


def test_read_canon_unknown_area_raises_with_choices():
    with pytest.raises(FileNotFoundError) as exc_info:
        read_canon("definitely-not-an-area")
    assert "nodes" in str(exc_info.value)
