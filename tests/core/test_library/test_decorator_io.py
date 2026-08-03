"""Tests for haywire.core.library.decorator_io — decorator source rewriters."""

from pathlib import Path

import pytest

from haywire.core.library.decorator_io import (
    _get_decorator_list_field,
    _set_decorator_list_field,
    merge_decorator_list_field,
    norm_dep,
)

_INIT_TEMPLATE = """@library(
    id="x",
    dependencies=[{deps}],
    file_watcher=True,
)
class Library(BaseLibrary):
    pass
"""


def _write_init(tmp_path: Path, deps: list[str]) -> Path:
    init_file = tmp_path / "__init__.py"
    rendered = ", ".join(repr(d) for d in deps)
    init_file.write_text(_INIT_TEMPLATE.format(deps=rendered))
    return init_file


@pytest.mark.unit
def test_norm_dep_collapses_separators_and_case():
    assert norm_dep("Haybale-Core") == "haybale_core"
    assert norm_dep("haybale.core") == "haybale_core"
    assert norm_dep("haybale_core") == "haybale_core"


@pytest.mark.unit
def test_get_decorator_list_field_converts_underscores_to_hyphens():
    content = _INIT_TEMPLATE.format(deps="'haybale_core'")
    assert _get_decorator_list_field(content, "dependencies") == ["haybale-core"]


@pytest.mark.unit
def test_get_decorator_list_field_absent_field_returns_empty():
    content = '@library(\n    id="x",\n)\nclass Library(BaseLibrary):\n    pass\n'
    assert _get_decorator_list_field(content, "dependencies") == []


@pytest.mark.unit
def test_merge_union_adds_missing_and_preserves_existing_spelling(tmp_path: Path):
    """Union mode preserves the pre-existing (hyphen-converted) spelling of
    already-declared entries and appends new ones as spelled in `values` —
    matching apply_drift_fix's historical output exactly."""
    init_file = _write_init(tmp_path, ["haybale_core"])

    merge_decorator_list_field(init_file, "dependencies", ["haybale_studio"], mode="union")

    content = init_file.read_text()
    assert "dependencies=['haybale-core', 'haybale_studio']," in content


@pytest.mark.unit
def test_merge_union_dedupes_by_normalized_form(tmp_path: Path):
    init_file = _write_init(tmp_path, ["haybale_core"])

    # "haybale-core" normalizes the same as the already-declared "haybale_core"
    # (read back as "haybale-core") — must not be added twice.
    merge_decorator_list_field(init_file, "dependencies", ["haybale-core"], mode="union")

    content = init_file.read_text()
    assert content.count("haybale-core") == 1
    assert content.count("haybale_core") == 0


@pytest.mark.unit
def test_merge_union_no_op_when_nothing_missing(tmp_path: Path):
    init_file = _write_init(tmp_path, ["haybale_core", "haybale_studio"])

    merge_decorator_list_field(init_file, "dependencies", [], mode="union")

    content = init_file.read_text()
    assert "dependencies=['haybale-core', 'haybale-studio']," in content


@pytest.mark.unit
def test_merge_replace_overwrites_wholesale(tmp_path: Path):
    """Replace mode uses `values` as the complete new value — no union, no
    normalization dance. A declaration not present in `values` is dropped."""
    init_file = _write_init(tmp_path, ["haybale_core", "haybale_unused"])

    merge_decorator_list_field(init_file, "dependencies", ["haybale_studio"], mode="replace")

    content = init_file.read_text()
    assert "dependencies=['haybale_studio']," in content
    assert "haybale_core" not in content
    assert "haybale_unused" not in content


@pytest.mark.unit
def test_merge_replace_sorts_values(tmp_path: Path):
    init_file = _write_init(tmp_path, [])

    merge_decorator_list_field(init_file, "dependencies", ["haybale_studio", "haybale_core"], mode="replace")

    content = init_file.read_text()
    assert "dependencies=['haybale_core', 'haybale_studio']," in content


@pytest.mark.unit
def test_merge_raises_on_missing_file(tmp_path: Path):
    """Both modes surface I/O failure to the caller — the shared function
    must not swallow it, since apply_drift_replace relies on it propagating
    through its ManifestError translation boundary."""
    missing = tmp_path / "does_not_exist" / "__init__.py"
    with pytest.raises(FileNotFoundError):
        merge_decorator_list_field(missing, "dependencies", ["x"], mode="replace")


@pytest.mark.unit
def test_set_decorator_list_field_still_works_directly():
    """`_set_decorator_list_field` remains a standalone public primitive —
    rename.py and the marketplace Edit dialog call it directly on in-memory
    content, not through merge_decorator_list_field."""
    content = _INIT_TEMPLATE.format(deps="'a'")
    rewritten = _set_decorator_list_field(content, "dependencies", ["b", "c"])
    assert "dependencies=['b', 'c']," in rewritten
