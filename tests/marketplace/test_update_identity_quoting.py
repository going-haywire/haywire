"""The identity writer lands on ``haybale.toml``, and only on the fields it owns.

Nothing writes the `@library(...)` decorator — metadata saves go through this
file-write path instead of a source edit.
"""


def test_update_library_identity_writes_haybale_toml(tmp_path):
    """End-to-end: the manager's write path lands on haybale.toml, and the
    author's comments and the fields the dialog does not own survive it.
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
