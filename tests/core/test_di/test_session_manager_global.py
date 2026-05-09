"""Test that the ambient SessionManager global behaves like its peers."""

from unittest.mock import MagicMock

import pytest


def test_get_raises_before_set():
    # Reset global so the test is independent of test order
    import haywire.core.di.context as ctx_mod

    ctx_mod._session_manager = None

    from haywire.core.di.context import get_session_manager

    with pytest.raises(RuntimeError, match="SessionManager not set"):
        get_session_manager()


def test_set_then_get_returns_same_instance():
    from haywire.core.di.context import set_session_manager, get_session_manager

    sm = MagicMock()
    set_session_manager(sm)
    assert get_session_manager() is sm


def test_set_overwrites_previous():
    from haywire.core.di.context import set_session_manager, get_session_manager

    sm1 = MagicMock()
    sm2 = MagicMock()
    set_session_manager(sm1)
    set_session_manager(sm2)
    assert get_session_manager() is sm2
