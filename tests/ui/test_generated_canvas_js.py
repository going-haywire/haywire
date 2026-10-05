"""The canvas's generated JavaScript matches its Python source (scripts/generate_vue_events.py)."""

from pathlib import Path

import pytest

from haywire.ui.components.graph import generators

pytestmark = pytest.mark.unit

_GENERATED = Path(generators.__file__).parent / "generated"


@pytest.mark.parametrize("name", sorted(generators.GENERATED_FILES))
def test_a_generated_file_is_up_to_date(name: str) -> None:
    expected = generators.GENERATED_FILES[name]()
    assert (_GENERATED / name).read_text() == expected, (
        f"generated/{name} is stale: run `uv run python scripts/generate_vue_events.py`"
    )


def test_the_canvas_loads_every_generated_file() -> None:
    from haywire.ui.components.graph import canvas

    vue = (Path(canvas.__file__).parent / "canvas.vue").read_text()
    for name in generators.GENERATED_FILES:
        assert f"import '{Path(name).stem}';" in vue, f"canvas.vue does not import {name}"
