"""The identity writer must handle double-quoted decorators — which is all of them.

Regression test: the original implementation used single-quote-only regexes
(`(    label=')[^']*(')`), so every write silently no-opped against
`ruff format` output.
"""

import pytest

from haywire.core.library.decorator_io import _set_decorator_str_field

DOUBLE_QUOTED = """from haywire.core.library.decorator import library


@library(
    label="Old Label",
    id="demo",
    description="Old description",
    url="https://old.example",
    author="Old Author",
    author_url="https://old-author.example",
    file_watcher=True,
)
class Library:
    pass
"""


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("label", "New Label"),
        ("description", "New description"),
        ("url", "https://new.example"),
        ("author", "New Author"),
        ("author_url", "https://new-author.example"),
    ],
)
def test_set_decorator_str_field_rewrites_double_quoted(field, new_value):
    result = _set_decorator_str_field(DOUBLE_QUOTED, field, new_value)
    assert f'{field}="{new_value}"' in result


def test_rewrite_leaves_other_fields_untouched():
    result = _set_decorator_str_field(DOUBLE_QUOTED, "label", "New Label")
    assert 'id="demo"' in result
    assert 'author="Old Author"' in result
    assert "file_watcher=True" in result


def test_rewrite_is_idempotent():
    once = _set_decorator_str_field(DOUBLE_QUOTED, "label", "X")
    twice = _set_decorator_str_field(once, "label", "X")
    assert once == twice


def test_update_library_identity_writes_double_quoted_decorator(tmp_path):
    """End-to-end: the manager's write path must land on a double-quoted file."""
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(DOUBLE_QUOTED)
    (pkg_dir.parent / "pyproject.toml").write_text('[project]\nname = "haybale-demo"\nversion = "0.1.0"\n')

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity(
        "demo",
        str(tmp_path),
        {
            "label": "Fresh Label",
            "dependencies": [],
            "on_reload": "none",
        },
    )

    assert ok, message
    written = (pkg_dir / "__init__.py").read_text()
    assert 'label="Fresh Label"' in written
    assert 'on_reload="none"' in written
    assert "Old Label" not in written


def test_update_library_identity_leaves_pyproject_owned_fields_alone(tmp_path):
    """description/author/url/tags come from pyproject.toml, so the writer skips them.

    Writing them here would produce a second copy the next import ignores —
    which is the drift this migration exists to end.
    """
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(DOUBLE_QUOTED)
    (pkg_dir.parent / "pyproject.toml").write_text('[project]\nname = "haybale-demo"\nversion = "0.1.0"\n')

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity(
        "demo",
        str(tmp_path),
        {"label": "Fresh Label", "dependencies": [], "on_reload": "none"},
    )

    assert ok, message
    written = (pkg_dir / "__init__.py").read_text()
    assert 'description="Old description"' in written
    assert 'author="Old Author"' in written
    assert 'url="https://old.example"' in written
