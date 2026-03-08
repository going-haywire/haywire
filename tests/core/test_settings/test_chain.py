# tests/core/test_settings/test_chain.py
"""Tests for ResolutionChain — 4-tier value resolution."""

import pytest
from haywire.core.settings.chain import ResolutionChain
from haywire.core.settings.enums import SettingMode
from haywire.core.di.test_config import create_test_settings_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chain():
    """Return (registry, chain, local_store) with a single known key pre-defined."""
    registry = create_test_settings_registry(register_builtins=False)
    registry.define(name='test.chain.value', default=0)
    local_store: dict = {}
    chain = ResolutionChain(local_store, registry)
    return registry, chain, local_store


# ---------------------------------------------------------------------------
# Tier 4: schema default
# ---------------------------------------------------------------------------

class TestDefaultTier:

    def test_returns_default_when_nothing_set(self):
        _, chain, _ = _make_chain()
        assert chain.resolve('nonexistent.key', 'fallback') == 'fallback'

    def test_none_default(self):
        _, chain, _ = _make_chain()
        assert chain.resolve('nonexistent.key', None) is None

    def test_defined_but_auto_uses_schema_default(self):
        registry, chain, _ = _make_chain()
        # mode stays AUTO → chain returns schema default passed to resolve()
        assert chain.resolve('test.chain.value', 99) == 99


# ---------------------------------------------------------------------------
# Tier 3: global SET
# ---------------------------------------------------------------------------

class TestGlobalSetTier:

    def test_global_set_wins_over_default(self):
        registry, chain, _ = _make_chain()
        registry.set_global('test.chain.value', 42, SettingMode.SET)
        assert chain.resolve('test.chain.value', 0) == 42

    def test_global_set_wins_when_local_not_set(self):
        registry, chain, local = _make_chain()
        registry.set_global('test.chain.value', 10, SettingMode.SET)
        # local is empty → global SET wins
        assert chain.resolve('test.chain.value', 0) == 10


# ---------------------------------------------------------------------------
# Tier 2: local instance override
# ---------------------------------------------------------------------------

class TestLocalTier:

    def test_local_beats_global_set(self):
        registry, chain, local = _make_chain()
        registry.set_global('test.chain.value', 10, SettingMode.SET)
        local['test.chain.value'] = 999
        assert chain.resolve('test.chain.value', 0) == 999

    def test_local_beats_default(self):
        _, chain, local = _make_chain()
        local['test.chain.value'] = 7
        assert chain.resolve('test.chain.value', 0) == 7


# ---------------------------------------------------------------------------
# Tier 1: OVERRIDE
# ---------------------------------------------------------------------------

class TestOverrideTier:

    def test_override_beats_local(self):
        registry, chain, local = _make_chain()
        local['test.chain.value'] = 100
        registry.set_global('test.chain.value', 999, SettingMode.OVERRIDE)
        assert chain.resolve('test.chain.value', 0) == 999

    def test_override_beats_global_set(self):
        registry, chain, _ = _make_chain()
        registry.set_global('test.chain.value', 10, SettingMode.SET)
        registry.set_global('test.chain.value', 999, SettingMode.OVERRIDE)
        assert chain.resolve('test.chain.value', 0) == 999


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

class TestChainMutations:

    def test_has_local_false_when_empty(self):
        _, chain, _ = _make_chain()
        assert not chain.has_local('test.chain.value')

    def test_has_local_true_after_set(self):
        _, chain, local = _make_chain()
        chain.set_local('test.chain.value', 5)
        assert chain.has_local('test.chain.value')

    def test_get_local(self):
        _, chain, _ = _make_chain()
        chain.set_local('test.chain.value', 42)
        assert chain.get_local('test.chain.value') == 42

    def test_get_local_key_error(self):
        _, chain, _ = _make_chain()
        with pytest.raises(KeyError):
            chain.get_local('test.chain.value')  # not set yet

    def test_clear_local(self):
        _, chain, _ = _make_chain()
        chain.set_local('test.chain.value', 5)
        chain.clear_local('test.chain.value')
        assert not chain.has_local('test.chain.value')

    def test_clear_local_noop_when_missing(self):
        _, chain, _ = _make_chain()
        chain.clear_local('test.chain.value')   # should not raise
