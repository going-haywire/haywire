"""Unit tests for LibraryStateRegistry."""

from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import AppState, LibraryState
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
        class MyState(AppState):
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(MyState) is True

    def test_class_filter_rejects_marker_bases(self):
        reg = LibraryStateRegistry()
        assert reg._class_filter(LibraryState) is False
        assert reg._class_filter(AppState) is False

    def test_class_filter_rejects_unrelated_class(self):
        class Unrelated:
            pass

        reg = LibraryStateRegistry()
        assert reg._class_filter(Unrelated) is False

    def test_register_class_creates_identity_and_stores_class(self):
        class MyState(AppState):
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
        class MyState(AppState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        first_key = reg._register_class(MyState, lib_id)
        # Re-registering the same class returns the same key without error.
        second_key = reg._register_class(MyState, lib_id)
        assert first_key == second_key

    def test_unregister_removes_class(self):
        class MyState(AppState):
            pass

        reg = LibraryStateRegistry()
        lib_id = make_lib_identity()
        key = reg._register_class(MyState, lib_id)
        removed = reg._unregister_class(key)

        assert removed is MyState
        assert not reg.has(key)


class TestGetClassesForLibrary:
    def test_empty_registry_returns_empty_dict(self):
        reg = LibraryStateRegistry()
        result = reg.get_classes_for_library(make_lib_identity("midi"))
        assert result == {}

    def test_returns_classes_for_matching_library(self):
        class StateA(AppState):
            pass

        class StateB(AppState):
            pass

        reg = LibraryStateRegistry()
        midi = make_lib_identity("midi")
        key_a = reg._register_class(StateA, midi)
        key_b = reg._register_class(StateB, midi)

        result = reg.get_classes_for_library(midi)
        assert result == {key_a: StateA, key_b: StateB}

    def test_filters_out_other_libraries(self):
        class MidiState(AppState):
            pass

        class AudioState(AppState):
            pass

        reg = LibraryStateRegistry()
        midi = make_lib_identity("midi")
        audio = make_lib_identity("audio")
        midi_key = reg._register_class(MidiState, midi)
        reg._register_class(AudioState, audio)

        result = reg.get_classes_for_library(midi)
        assert result == {midi_key: MidiState}

    def test_unregistered_class_is_excluded(self):
        class MyState(AppState):
            pass

        reg = LibraryStateRegistry()
        midi = make_lib_identity()
        key = reg._register_class(MyState, midi)
        reg._unregister_class(key)

        result = reg.get_classes_for_library(midi)
        assert result == {}

    def test_filters_by_library_id_not_object_identity(self):
        """Hot-reload may produce a fresh LibraryIdentity instance with the
        same id. The filter must compare by id string, not Python identity."""

        class MyState(AppState):
            pass

        reg = LibraryStateRegistry()
        first = make_lib_identity("midi")
        reg._register_class(MyState, first)

        # New LibraryIdentity instance — same id, different Python object.
        second = make_lib_identity("midi")
        assert second is not first

        result = reg.get_classes_for_library(second)
        assert MyState in result.values()
