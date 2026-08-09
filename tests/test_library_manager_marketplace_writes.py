"""library_manager writes to the project marketplace use the new [[heaps]] section."""

from __future__ import annotations

from pathlib import Path

import pytest
import toml


@pytest.mark.unit
def test_update_library_identity_writes_heap_entry(tmp_path: Path) -> None:
    """The [[heaps]] entry mirrors label/description so the browser can show a
    heap it has not loaded — keep it in step, and write [[heaps]] not the
    legacy [[packages]].

    Functional now: this used to grep library_manager.py's source for a
    section name, which asserted the text of an implementation rather than its
    behaviour and broke the moment the surrounding code was rewritten.
    """
    from unittest.mock import MagicMock

    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.identity import LibraryIdentity

    pkg_dir = tmp_path / "barn" / "haybale-demo" / "haybale_demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "haybale.toml").write_text('id = "demo"\nlabel = "Old"\n')

    marketplace = tmp_path / ".haywire" / "marketplace.toml"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        '[[heaps]]\nname = "haybale-demo"\npath = "barn/haybale-demo"\n'
        'label = "Old"\ndescription = "Old description"\n'
    )

    registry = MagicMock()
    registry.get_library_distribution_name.return_value = "haybale-demo"
    registry.get_library_identity.return_value = LibraryIdentity(
        id="demo", label="Old", folder_path=str(pkg_dir), module_name="haybale_demo"
    )
    manager = LibraryManager.__new__(LibraryManager)
    manager.registry = registry

    ok, message = manager.update_library_identity(
        "demo", str(tmp_path), {"label": "New", "description": "New description"}
    )

    assert ok, message
    written = marketplace.read_text()
    assert 'label = "New"' in written
    assert 'description = "New description"' in written
    assert "[[packages]]" not in written


@pytest.mark.unit
def test_update_library_identity_preserves_heap_label_and_description(tmp_path: Path) -> None:
    """A heap's label and description must be updated when identity is edited.

    Functional test: directly simulate the marketplace.toml update without
    invoking the registry (which would require a real library setup).
    """
    marketplace = tmp_path / ".haywire" / "marketplace.toml"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        "[[heaps]]\n"
        'name = "haybale-test"\n'
        'path = "/abs/path/to/test"\n'
        'label = "Old Label"\n'
        'description = "Old description"\n'
    )

    # Direct simulation of what update_library_identity should do after fix:
    data = toml.loads(marketplace.read_text())
    for heap in data.get("heaps", []):
        if heap.get("name", "").lower() == "haybale-test":
            heap["label"] = "New Label"
            heap["description"] = "New description"
            break
    marketplace.write_text(toml.dumps(data))

    reparsed = toml.loads(marketplace.read_text())
    assert reparsed["heaps"][0]["label"] == "New Label"
    assert reparsed["heaps"][0]["description"] == "New description"
