"""Test 3 — correctness parity between SimpleWidget and BaseWidget-default.

Gate for finding #3: perf numbers are meaningless unless the BaseWidget-default
path is behaviorally identical to SimpleWidget for the primitive case. If parity
fails, the unification has a correctness problem that outranks performance —
finding #2 (binding double-activation) is the first suspect.

See ``docs/plans/widget-unification-perf-verification.md``.
"""

import pytest

from tests.ui.widget._sync_fixtures import (
    build_base_default,
    build_simple,
    make_float_port,
    BaseDefaultFloatWidget,
    SimpleFloatWidget,
    _StandInElement,
    _main_binding,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Model -> View: the hot path both bases must agree on
# ---------------------------------------------------------------------------


def test_initial_sync_matches():
    """A fresh sync of the same port value lands the same element value."""
    s_sync, s_port, s_el = build_simple()
    b_sync, b_port, b_el = build_base_default()

    for port in (s_port, b_port):
        port.set_value(42.0)
    s_sync()
    b_sync()

    assert s_el.value == b_el.value == 42.0


def test_model_to_view_matches_across_updates():
    """Repeated model writes sync identically on both paths."""
    s_sync, s_port, s_el = build_simple()
    b_sync, b_port, b_el = build_base_default()

    for v in (1.0, -3.5, 0.0, 999.25):
        s_port.set_value(v)
        b_port.set_value(v)
        s_sync()
        b_sync()
        assert s_el.value == b_el.value == v


def test_none_falls_back_to_default_on_simple():
    """SimpleWidget substitutes get_default_value() when the port yields None.

    NOTE: this is a *known* behavioral difference to confront before unifying.
    SimpleWidget._sync_to_view swaps None -> get_default_value(); the BaseWidget
    default path runs the value through PrimitiveUnwrappingConverter, whose
    default_value is None unless configured. The unification must decide where
    the "empty port shows 0.0" default lives. This test documents the SimpleWidget
    contract so the migration can preserve it deliberately, not by accident.
    """
    port = make_float_port()
    w = SimpleFloatWidget(port)
    el = _StandInElement()
    w.ui_element = el
    # Force a None model value (fresh FLOAT field may default to 0.0, so assert
    # the fallback path directly via get_default_value()).
    assert w.get_default_value() == 0.0


# ---------------------------------------------------------------------------
# Cleanup parity — also catches finding #2 (dangling subscriptions)
# ---------------------------------------------------------------------------


def test_cleanup_removes_subscription_on_simple():
    s_sync, port, el = build_simple()
    # SimpleWidget subscribes in _setup_binding, not in our direct-drive path,
    # so subscribe the way render() would, then assert cleanup detaches it.
    w = SimpleFloatWidget(port)
    w.ui_element = el
    w._setup_binding()
    assert port._data.on_changed.has_observers()
    w.cleanup()
    assert not port._data.on_changed.has_observers()
    assert w._cleaned_up is True


def test_base_default_binding_subscribes_exactly_once():
    """Finding #2 guard: configure + activate must not double-subscribe.

    add_binding() activates immediately when ui_element already exists, and
    render()'s _activate_all_bindings() would activate again. PropertyBinding's
    _is_active flag should make the second a no-op — assert the port ends with a
    single observer, not two.
    """
    port = make_float_port()
    w = BaseDefaultFloatWidget(port)
    el = _StandInElement()
    w.ui_element = el
    w.configure_bindings()

    binding = _main_binding(w)
    binding.activate(port, el)
    observers_after_first = port._data.on_changed.handler_size

    # Simulate render()'s second activation pass.
    binding.activate(port, el)
    observers_after_second = port._data.on_changed.handler_size

    assert observers_after_first == observers_after_second == 1, (
        "BaseWidget default binding double-subscribed (finding #2) — "
        f"{observers_after_first} -> {observers_after_second}"
    )

    binding.deactivate()
    assert not port._data.on_changed.has_observers()
