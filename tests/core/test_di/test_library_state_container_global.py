"""Test the ambient LibraryStateContainer getter."""

from unittest.mock import MagicMock

import pytest


def test_get_raises_before_set():
    import haywire.core.di.context as ctx_mod

    ctx_mod._library_state_container = None
    from haywire.core.di.context import get_library_state_container

    with pytest.raises(RuntimeError, match="LibraryStateContainer not set"):
        get_library_state_container()


def test_set_then_get():
    from haywire.core.di.context import set_library_state_container, get_library_state_container

    container = MagicMock()
    set_library_state_container(container)
    assert get_library_state_container() is container
