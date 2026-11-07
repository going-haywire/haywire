"""The matrix widget, driven through a real browser."""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_PATH = "/matrix-widget"

pytestmark = pytest.mark.ui


def _cell(page: Page, matrix: str, row: int, col: int):
    return page.locator(f'[data-matrix="{matrix}"] [data-matrix-cell="{row},{col}"]')


def test_it_shows_the_identity_row_by_row(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    expect(page.locator('[data-matrix="m3"] [data-matrix-cell]')).to_have_count(9)
    expect(page.locator('[data-matrix="m4"] [data-matrix-cell]')).to_have_count(16)
    expect(_cell(page, "m3", 0, 0)).to_contain_text("1")
    expect(_cell(page, "m3", 0, 1)).to_contain_text("0")


def test_cells_keep_their_grid_places(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    first = _cell(page, "m4", 0, 0).bounding_box()
    right = _cell(page, "m4", 0, 3).bounding_box()
    below = _cell(page, "m4", 3, 0).bounding_box()
    assert first is not None
    assert right is not None
    assert below is not None
    assert right["x"] > first["x"]
    assert abs(right["y"] - first["y"]) < 2
    assert below["y"] > first["y"]
    assert abs(below["x"] - first["x"]) < 2


def test_the_largest_matrix_fits_a_narrow_card(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    grid = page.locator('[data-matrix="m4"]').bounding_box()
    last = _cell(page, "m4", 0, 3).bounding_box()
    assert grid is not None
    assert last is not None
    assert last["x"] + last["width"] <= grid["x"] + grid["width"] + 1


def test_a_number_in_the_largest_matrix_is_not_cut_off(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    center = _cell(page, "m4", 0, 0).locator(".number-drag__center")
    clipped = center.evaluate("el => el.scrollWidth > el.clientWidth")
    assert clipped is False
    room = center.evaluate("el => el.clientWidth")
    assert room >= 40


def test_editing_a_cell_writes_that_row_and_column(page: Page, harness: str) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    cell = _cell(page, "m3", 1, 2)
    cell.locator(".number-drag__center").dblclick()
    field = cell.locator("input")
    field.fill("2.5")
    field.press("Enter")
    expect(page.locator('[data-testid="echo-m3"]')).to_have_text(
        "[[1.0, 0.0, 0.0], [0.0, 1.0, 2.5], [0.0, 0.0, 1.0]]"
    )
