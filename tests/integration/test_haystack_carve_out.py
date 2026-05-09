"""End-to-end carve-out contract for haybale-haystack.

These stubs document the integration contract. Implementing them
concretely requires booting a real ``HaywireApp`` against a temp
workspace; that infrastructure exists in ``tests/`` but each scenario
needs case-by-case wiring beyond the scope of PR 2. Each test is
skipped pending that follow-up.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="PR2 stub — flesh out using existing app-boot integration patterns")
def test_haystack_state_loads_via_library_system(tmp_path):
    """Booting HaywireApp with haybale-haystack enabled registers HaystackState.

    Contract:
      - workspace_root = tmp_path with haystacks/ and graphs/ subdirs
      - HaywireApp constructed; library system discovers haybale-haystack
        via entry-points and runs Library.register_components()
      - LibraryStateContainer holds an instance of HaystackState whose
        on_enable has fired
    """


@pytest.mark.skip(reason="PR2 stub — flesh out using existing app-boot integration patterns")
def test_rehydrate_from_settings(tmp_path):
    """HaystackState.on_enable rehydrates from HaystackSettings.last_haystack_name.

    Contract:
      - Pre-seed <tmp_path>/haystacks/saved.toml with one entry
      - Pre-seed HaystackSettings.last_haystack_name = "saved"
      - Boot HaywireApp; HaystackState.all_entries() returns the seeded entry
    """


@pytest.mark.skip(reason="PR2 stub — flesh out using existing app-boot integration patterns")
def test_execute_true_resumes_interpreter(tmp_path):
    """Entries flagged execute=true in TOML have running interpreters after load.

    Contract:
      - Pre-seed a haystack TOML with an entry where execute=true
      - Boot HaywireApp
      - The corresponding GraphEntry.is_executing is True after on_enable
    """
