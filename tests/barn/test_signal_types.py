"""A signal port must never be asked to serialize an untouched value.

EXEC and CALLBACK both wrap a field holding ``None`` until something writes it,
and ``PrimitiveType`` cannot construct one from ``None`` — so a port asked to
store it raises from inside ``PrimitiveField.to_dict``. Both types therefore
override ``as_outlet``'s ``ALWAYS`` default, EXEC with ``NEVER`` and CALLBACK
with ``NODE_SET``: a CALLBACK carries the subscription key its listener
registers under, so a key the node wrote is kept.
"""

import pytest

from haywire.core.types.enums import StoreStrategy

# The strategy each signal type declares, and what it means for the port.
SIGNAL_STRATEGIES = [
    ("EXEC", StoreStrategy.NEVER),
    ("CALLBACK", StoreStrategy.NODE_SET),
]


@pytest.mark.parametrize(("type_name", "expected"), SIGNAL_STRATEGIES)
def test_a_signal_type_declares_its_store_strategy(type_name, expected):
    from haywire.barn.builtin import types as specs

    signal = getattr(specs, type_name)
    assert signal.class_identity.store_strategy is expected


@pytest.mark.parametrize("factory", ["as_inlet", "as_outlet"])
@pytest.mark.parametrize(("type_name", "expected"), SIGNAL_STRATEGIES)
def test_a_signal_port_keeps_that_strategy_in_either_direction(type_name, expected, factory):
    """``as_outlet`` defaults to ALWAYS, which the type's own strategy overrides."""
    from haywire.barn.builtin import types as specs

    signal = getattr(specs, type_name)
    spec = getattr(signal, factory)("signal")
    assert StoreStrategy(spec["kwargs"]["store_strategy"]) is expected


@pytest.mark.parametrize(("type_name", "_expected"), SIGNAL_STRATEGIES)
def test_an_untouched_signal_port_stores_nothing(type_name, _expected):
    """The crash case: nothing wrote the port, so there is no value to write out."""
    from haywire.barn.builtin import types as specs

    signal = getattr(specs, type_name)
    strategy = signal.class_identity.store_strategy
    assert not strategy.should_store(has_widget=False, node_set=False)


# Each signal type owns a module named after it.
SIGNAL_MODULES = {"EXEC": "exec", "CALLBACK": "callback"}


@pytest.mark.parametrize(("type_name", "_expected"), SIGNAL_STRATEGIES)
def test_a_signal_type_is_a_builtin_type(type_name, _expected):
    from haywire.barn.builtin import types

    signal = getattr(types, type_name)
    assert signal.class_identity.registry_key == f"haywire-core:type:{type_name}"
    assert signal.__module__ == f"haywire.barn.builtin.types.{SIGNAL_MODULES[type_name]}"


@pytest.mark.parametrize(("type_name", "_expected"), SIGNAL_STRATEGIES)
def test_haybale_core_does_not_export_a_signal_type(type_name, _expected):
    import haybale_core.types

    assert not hasattr(haybale_core.types, type_name)
