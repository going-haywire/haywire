from haywire.barn.builtin import widget_keys


def test_every_constant_resolves_to_a_registered_widget(library_system):
    """Constants must match the @widget-derived registry keys (typo guard)."""
    from haywire.ui.widget.globals import WIDGET_REGISTRY

    consts = {
        name: val for name, val in vars(widget_keys).items() if name.isupper() and isinstance(val, str)
    }
    assert consts, "widget_keys module exports no constants?"
    for name, key in consts.items():
        assert key in WIDGET_REGISTRY, f"widget_keys.{name}={key!r} not in WIDGET_REGISTRY"
