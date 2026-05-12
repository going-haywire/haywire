"""Unit tests for SessionState base class.

Covers:
  - SessionState is a subclass of LibraryState (and a sibling of AppState).
  - Lifecycle hooks (on_enable, on_disable) are duck-typed, same as AppState.
  - The `session_id` attribute is annotated on the base.
  - __init_subclass__ rejects fields whose annotation references LibrarySettings
    (both bare and Optional/Union forms).
"""

import pytest

from haywire.core.settings.schema import LibrarySettings
from haywire.core.state import AppState, LibraryState, SessionState


class TestSessionStateBase:
    def test_session_state_is_not_a_subclass_of_app_state(self):
        """AppState and SessionState are siblings, not parent/child."""
        assert not issubclass(SessionState, AppState)
        assert not issubclass(AppState, SessionState)

    def test_subclass_can_be_instantiated(self):
        class MySS(SessionState):
            pass

        instance = MySS()
        assert isinstance(instance, SessionState)
        assert isinstance(instance, LibraryState)

    def test_session_id_attribute_is_annotated(self):
        """The container stamps session_id; the annotation lets type-checkers see it."""
        assert "session_id" in SessionState.__annotations__

    def test_on_enable_is_optional(self):
        class NoHooks(SessionState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)


class TestSessionStateLibrarySettingsProhibition:
    def test_bare_library_settings_field_rejected(self):
        """A field annotated as a LibrarySettings subclass must raise at class definition."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: MySettings

    def test_optional_library_settings_field_rejected(self):
        """`Optional[X]` and `X | None` annotations also caught."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: MySettings | None = None

    def test_union_library_settings_field_rejected(self):
        """Union annotations with LibrarySettings somewhere in the union are caught."""

        class MySettings(LibrarySettings):
            pass

        with pytest.raises(TypeError, match="LibrarySettings cannot be composed"):

            class BadState(SessionState):
                config: int | MySettings

    def test_unrelated_field_not_rejected(self):
        """Fields without LibrarySettings types pass."""

        class GoodState(SessionState):
            cache: dict[str, int] = {}
            counter: int = 0

        # Class definition succeeds.
        instance = GoodState()
        assert instance.cache == {}

    def test_app_state_is_not_subject_to_the_check(self):
        """AppState may compose LibrarySettings (per library_state.md §5.1)."""

        class MySettings(LibrarySettings):
            pass

        # Must not raise.
        class GoodAppState(AppState):
            config: MySettings | None = None
