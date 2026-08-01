"""Shared fixtures for the share-pipeline tests."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"
