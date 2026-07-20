"""Error → component/file navigation helpers (studio)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.unit


def test_open_component_sets_active_component():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    assert open_component(err, ctx) is True
    assert ctx.active_component == "lib:node:Foo"


def test_open_component_noop_without_registry_key():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x")
    assert open_component(err, ctx) is False


def test_open_file_in_studio_reveals_code_editor():
    from haybale_studio.editors.error_navigation import open_file_in_studio

    ctx = MagicMock()
    open_file_in_studio("/tmp/thing.py", 12, ctx)
    assert ctx.active_file == Path("/tmp/thing.py")
    # A Reveal was published on the session.
    assert ctx.session.publish.call_count == 1
    published = ctx.session.publish.call_args[0][0]
    assert published.binding_id == "/tmp/thing.py"
