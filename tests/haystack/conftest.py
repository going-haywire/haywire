import pytest


@pytest.fixture(autouse=True)
def _own_ambient_di(own_ambient_di):
    """Run every test in this directory against the session library system."""
