"""setup_farmhand writes the studio sidecar when Farmhand is enabled."""

from typing import Any, cast

import pytest

from haywire_studio.farmhand.identity import IDENTITY_FILENAME, read_identity
from haywire_studio.security.document import SecurityDocument

pytestmark = pytest.mark.unit


class _FakeHost:
    def __init__(self, *args, **kwargs):
        pass

    def mount(self, port, document, *, tls: bool = False):  # no real network mount in a unit test
        self.mounted_port = port


@pytest.fixture
def app_state(tmp_path, monkeypatch):
    # setup_farmhand imports FarmhandHost locally from farmhand.host — patch the
    # source module so the local import picks up the fake.
    import haywire_studio.farmhand.host as host_module

    monkeypatch.setattr(host_module, "FarmhandHost", _FakeHost)

    # Import lazily and build a minimal HaywireApp rooted at tmp_path.
    from haywire_studio import app as app_module

    state = app_module.HaywireApp(workspace_root=str(tmp_path))
    # library_service is referenced by setup_farmhand's FarmhandHost(...) call;
    # _FakeHost ignores it, so a bare attribute is enough.
    state.library_service = cast(Any, object())
    return state, tmp_path, app_module


def test_sidecar_written_when_enabled(app_state):
    state, tmp_path, app_module = app_state
    document = SecurityDocument()
    document.farmhand.enabled = True

    state.setup_farmhand(8082, document)

    ident = read_identity(tmp_path)
    assert ident is not None
    assert ident["port"] == 8082
    assert (tmp_path / ".haywire" / IDENTITY_FILENAME).exists()


def test_no_sidecar_when_disabled(app_state):
    state, tmp_path, app_module = app_state
    document = SecurityDocument()
    document.farmhand.enabled = False

    state.setup_farmhand(8082, document)

    assert read_identity(tmp_path) is None
