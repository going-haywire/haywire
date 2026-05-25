"""Install button OS-gating helper — spec §2.1 Library Browser behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_should_block_install_for_os_returns_none_when_empty_os() -> None:
    """A haybale with empty os list (= all platforms) is never OS-blocked."""
    from haybale_marketplace.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=[])
    assert should_block_install_for_os(h) is None


@pytest.mark.unit
def test_should_block_install_for_os_returns_none_when_supported() -> None:
    """A haybale that includes the current OS is not blocked."""
    from haybale_marketplace.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos", "linux", "windows"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert should_block_install_for_os(h) is None


@pytest.mark.unit
def test_should_block_install_for_os_returns_message_when_unsupported() -> None:
    """A haybale that does NOT include the current OS returns a tooltip message."""
    from haybale_marketplace.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos", "linux"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Windows"):
        msg = should_block_install_for_os(h)
        assert msg is not None
        assert "Not available on this OS" in msg
        assert "macos" in msg and "linux" in msg


@pytest.mark.unit
def test_should_block_install_for_os_includes_os_list_in_message() -> None:
    from haybale_marketplace.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        msg = should_block_install_for_os(h)
        assert msg is not None
        assert "macos" in msg
        # The current OS (linux) is NOT in the targets list — verify it doesn't leak in.
        assert msg.count("linux") == 0
