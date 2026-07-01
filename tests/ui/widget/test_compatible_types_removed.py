import haywire.core.graph.editor  # noqa: F401

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget


def test_widget_decorator_no_longer_requires_compatible_types():
    @widget(description="no types declared")
    class W(BaseWidget):
        def build(self):
            return None

    assert W is not None


def test_widget_decorator_rejects_compatible_types():
    import pytest

    with pytest.raises(TypeError):

        @widget(description="legacy", compatible_types=set())
        class W(BaseWidget):
            def build(self):
                return None

        _ = W


def test_widget_identity_has_no_compatible_types_field():
    from haywire.ui.widget.identity import WidgetIdentity
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(WidgetIdentity)}
    assert "compatible_types" not in field_names
