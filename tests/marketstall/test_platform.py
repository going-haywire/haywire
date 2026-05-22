"""current_os() — spec §2.1 mapping table."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_current_os_maps_darwin_to_macos() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Darwin"):
        assert current_os() == "macos"


@pytest.mark.unit
def test_current_os_maps_windows_to_windows() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Windows"):
        assert current_os() == "windows"


@pytest.mark.unit
def test_current_os_maps_linux_to_linux() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert current_os() == "linux"


@pytest.mark.unit
def test_current_os_maps_unknown_to_other() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="FreeBSD"):
        assert current_os() == "other"


@pytest.mark.unit
def test_haybale_supports_current_when_os_empty() -> None:
    """Empty os list = all platforms per §2.1."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=[])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is True


@pytest.mark.unit
def test_haybale_supports_current_when_listed() -> None:
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos", "linux"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is True


@pytest.mark.unit
def test_haybale_does_not_support_current_when_not_listed() -> None:
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is False


@pytest.mark.unit
def test_haybale_on_other_os_blocked_from_all_declared() -> None:
    """`other` is the runtime sentinel; a declared list never includes 'other' so 'other' never matches."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos", "linux", "windows"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="OpenBSD"):
        assert haybale_supports_current_os(h) is False


@pytest.mark.unit
def test_haybale_on_other_os_supported_when_empty() -> None:
    """Pure-Python library with no os declared still installs on unknown OSes."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=[])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Haiku"):
        assert haybale_supports_current_os(h) is True
