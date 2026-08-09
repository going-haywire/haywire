"""The identity writer must handle double-quoted decorators — which is all of them.

Regression test: the original implementation used single-quote-only regexes
(`(    label=')[^']*(')`), so every write silently no-opped against
`ruff format` output.

The decorator writers survive for `haywire rename` and the share pipeline's
drift fix; the marketplace save path moved to haybale.toml, so the end-to-end
test at the bottom asserts that file instead.
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


def test_update_library_identity_writes_haybale_toml(tmp_path):
    """End-to-end: the manager's write path lands on haybale.toml.

    Replaces the decorator-writing end-to-end test. The metadata moved out of
    `@library(...)` precisely so a save is a file write rather than a source
    edit, so this asserts the file — and that the author's comments and the
    fields the dialog does not own survive it.
    """
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.identity import LibraryIdentity

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "haybale.toml").write_text(
        "# hand-written note\n"
        'name = "haybale-demo"\n'
        'id = "demo"\n'
        'label = "Old Label"\n'
        'version = "0.1.0"\n'
        'linked_libraries = ["haybale_core"]\n'
    )

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    registry.get_library_identity.return_value = LibraryIdentity(
        id="demo", label="Old Label", folder_path=str(pkg_dir), module_name="haybale_demo"
    )
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity(
        "demo",
        str(tmp_path),
        {
            "label": "Fresh Label",
            "description": "Fresh description",
            "homepage_url": "https://fresh.example",
            "tags": ["alpha"],
            "on_reload": "none",
        },
    )

    assert ok, message
    written = (pkg_dir / "haybale.toml").read_text()
    assert 'label = "Fresh Label"' in written
    assert 'description = "Fresh description"' in written
    assert 'tags = ["alpha"]' in written
    # Untouched by this dialog, and therefore untouched on disk.
    assert 'version = "0.1.0"' in written
    assert 'linked_libraries = ["haybale_core"]' in written
    assert "# hand-written note" in written


def test_update_library_identity_rejects_fields_it_does_not_own(tmp_path):
    """version/origin belong to the share wizard, name/id are immutable. Passing
    one is a caller bug, so it fails loudly rather than being dropped."""
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.identity import LibraryIdentity

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "haybale.toml").write_text('id = "demo"\nversion = "0.1.0"\n')

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    registry.get_library_identity.return_value = LibraryIdentity(
        id="demo", folder_path=str(pkg_dir), module_name="haybale_demo"
    )
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity("demo", str(tmp_path), {"version": "9.9.9"})

    assert not ok
    assert "version" in message
    assert 'version = "0.1.0"' in (pkg_dir / "haybale.toml").read_text()
