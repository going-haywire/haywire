"""Unit tests for LibraryStateRegistry."""

from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryState
from haywire.core.state.registry import LibraryStateRegistry


def make_lib_identity(lib_id: str = "midi") -> LibraryIdentity:
    """Build a minimal LibraryIdentity for tests."""
    return LibraryIdentity(
        id=lib_id,
        label=lib_id.capitalize(),
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name=f"haybale_{lib_id}",
        folder_path="",
    )


class TestLibraryStateRegistry:
    def test_class_filter_accepts_subclass(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(MyState) is True

    def test_class_filter_rejects_base_class(self):
        reg = LibraryStateRegistry()
        assert reg._class_filter(LibraryState) is False

    def test_class_filter_rejects_unrelated_class(self):
        class Unrelated:
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(Unrelated) is False

    def test_register_class_creates_identity_and_stores_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        key = reg._register_class(MyState, lib_id)

        assert key == "midi:state:MyState"
        assert reg.has(key)
        assert reg.get(key) is MyState
        assert hasattr(MyState, "class_identity")
        assert MyState.class_identity.class_name == "MyState"
        assert MyState.class_identity.registry_key == "midi:state:MyState"

    def test_register_class_is_idempotent_for_same_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        first_key = reg._register_class(MyState, lib_id)
        # Re-registering the same class returns the same key without error.
        second_key = reg._register_class(MyState, lib_id)
        assert first_key == second_key

    def test_unregister_removes_class(self):
        class MyState(LibraryState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        key = reg._register_class(MyState, lib_id)
        removed = reg._unregister_class(key)

        assert removed is MyState
        assert not reg.has(key)
