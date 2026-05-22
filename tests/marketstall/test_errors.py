"""Exception types live in haywire.core.marketstall.errors."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_malformed_marketplace_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import MalformedMarketplaceError

    assert issubclass(MalformedMarketplaceError, RuntimeError)


@pytest.mark.unit
def test_duplicate_heap_name_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import DuplicateHeapNameError

    assert issubclass(DuplicateHeapNameError, RuntimeError)


@pytest.mark.unit
def test_remote_fetch_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import RemoteFetchError

    assert issubclass(RemoteFetchError, RuntimeError)


@pytest.mark.unit
def test_duplicate_package_name_error_is_gone() -> None:
    """Direct-paste packages are removed per spec §14; the error class goes with them."""
    from haywire.core.marketstall import errors as errors_module

    assert not hasattr(errors_module, "DuplicatePackageNameError")
