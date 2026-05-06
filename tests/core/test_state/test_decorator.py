"""Tests for the @state decorator."""

import pytest

from haywire.core.state import AppState, SessionState, state


@pytest.mark.unit
class TestStateDecorator:
    def test_decorates_app_state_subclass(self):
        @state(label="My App State")
        class _MyApp(AppState):
            pass

        assert _MyApp.class_identity.label == "My App State"
        assert _MyApp.class_identity.class_name == "_MyApp"
        assert _MyApp.class_identity.module == __name__

    def test_decorates_session_state_subclass(self):
        @state(label="My Session State")
        class _MySession(SessionState):
            pass

        assert _MySession.class_identity.label == "My Session State"

    def test_label_defaults_to_registry_id(self):
        @state()
        class _NoLabel(AppState):
            pass

        assert _NoLabel.class_identity.label == "_NoLabel"

    def test_registry_id_overrides_class_name(self):
        @state(registry_id="CustomId")
        class _SomeName(AppState):
            pass

        assert _SomeName.class_identity.registry_id == "CustomId"
        # Registry key uses the override.
        assert _SomeName.class_identity.registry_key.endswith(":state:CustomId")

    def test_description_attached(self):
        @state(description="A thing")
        class _Described(AppState):
            pass

        assert _Described.class_identity.description == "A thing"

    def test_attaches_class_library(self):
        @state()
        class _HasLibrary(AppState):
            pass

        assert hasattr(_HasLibrary, "class_library")
        # System library is the auto-generated fallback when no real library
        # is found in sys.modules.
        assert _HasLibrary.class_library is not None

    def test_registry_key_format(self):
        """Registry key follows the standard ``{lib_id}:state:{registry_id}`` format."""

        @state()
        class _FormatCheck(AppState):
            pass

        key = _FormatCheck.class_identity.registry_key
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[1] == "state"
        assert parts[2] == "_FormatCheck"

    def test_rejects_non_state_class(self):
        class _NotAState:
            pass

        with pytest.raises(TypeError, match="@state can only be applied"):
            state()(_NotAState)

    def test_rejects_bare_library_state_subclass(self):
        from haywire.core.state import LibraryState

        # A subclass of LibraryState that's neither AppState nor SessionState
        # should be rejected — only the concrete bases are valid scopes.
        class _BareMarker(LibraryState):
            pass

        with pytest.raises(TypeError, match="@state can only be applied"):
            state()(_BareMarker)
