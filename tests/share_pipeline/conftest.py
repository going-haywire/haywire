"""Shared fixtures for the share-pipeline tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """`anyio`'s backend parametrization. The repo runs asyncio only."""
    return "asyncio"
