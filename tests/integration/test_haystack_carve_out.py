"""End-to-end carve-out contract for haybale-haystack.

The discovery contract (library system registers HaystackState and runs its
``on_enable``) is covered below against the session-scoped ``library_system``
fixture.

The two rehydration contracts are NOT covered. They need a library system
booted against a pre-seeded ``tmp_path`` workspace, but ``library_system`` is
session-scoped and already booted by the time any test runs, and
``HaystackState.on_enable`` resolves its dependencies from ambient DI globals
at enable time. Testing them needs a fresh per-test boot — see the xfail
markers, which keep the gap visible instead of silently skipping.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_haystack_state_loads_via_library_system(library_system):
    """Booting the library system registers HaystackState with on_enable fired.

    Every other HaystackState test constructs the class directly and mocks its
    container, so this is the only coverage of the discovery path.
    """
    from haywire.core.state import LibraryStateContainer
    from haybale_haystack.state.haystack_state import HaystackState

    container = library_system.injector.get(LibraryStateContainer)
    instance = container.get(HaystackState)

    assert instance is not None, "HaystackState was not registered by the library system"
    # on_enable ran: it resolves the shared GraphAppState and leaves the entry
    # list queryable rather than raising on a half-built object.
    assert instance.all_entries() == []


@pytest.mark.xfail(
    reason="Needs a library system booted against a seeded tmp_path workspace; "
    "the library_system fixture is session-scoped and already booted.",
    raises=NotImplementedError,
    strict=True,
)
def test_rehydrate_from_settings(tmp_path):
    """HaystackState.on_enable rehydrates from HaystackSettings.last_haystack_name.

    Contract:
      - Pre-seed <tmp_path>/haystacks/saved.toml with one entry
      - Pre-seed HaystackSettings.last_haystack_name = "saved"
      - Boot HaywireApp; HaystackState.all_entries() returns the seeded entry
    """
    raise NotImplementedError("per-test library-system boot fixture not available")


@pytest.mark.xfail(
    reason="Needs a library system booted against a seeded tmp_path workspace; "
    "the library_system fixture is session-scoped and already booted.",
    raises=NotImplementedError,
    strict=True,
)
def test_execute_true_resumes_interpreter(tmp_path):
    """Entries flagged execute=true in TOML have running interpreters after load.

    Contract:
      - Pre-seed a haystack TOML with an entry where execute=true
      - Boot HaywireApp
      - The corresponding GraphEntry.is_executing is True after on_enable
    """
    raise NotImplementedError("per-test library-system boot fixture not available")
