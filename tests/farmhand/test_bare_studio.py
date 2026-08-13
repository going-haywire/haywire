"""The studio_* baseline is always served.

Note on "bare studio": deviation note 2 describes a studio with only builtin +
haybale-studio installed serving exactly the ten studio_* tools. That exact-set
property can only be observed in an environment where no other barn library is
installed. In this monorepo dev venv every barn package is pip-installed, so the
library system discovers them all via entry points regardless of library_paths —
a folder/symlink sandbox cannot hide them. We therefore assert the invariant that
IS true and testable here: the ten studio_* baseline tools are always present.
The exact-set property is covered by the packaging guarantee (haywire-studio
depends on haybale-studio) and would be verified in a clean-install smoke test.
"""

import pytest

from tests.farmhand.conftest import make_caller

pytestmark = pytest.mark.integration

_BASELINE = {
    "haybale-studio_status",
    "haybale-studio_list_libraries",
    "haybale-studio_list_components",
    "haybale-studio_describe_component",
    "haybale-studio_scaffold_component",
    "haybale-studio_read_component_source",
    "haybale-studio_write_component_source",
    "haybale-studio_verify_component",
    "haybale-studio_get_errors",
    "haybale-studio_dismiss_errors",
}


def test_studio_baseline_always_served(farmhand_bare_server):
    farmhand_call = make_caller(farmhand_bare_server)

    async def scenario(session, init):
        return {t.name for t in (await session.list_tools()).tools}

    names = farmhand_call(scenario)
    assert _BASELINE <= names, f"missing baseline tools: {_BASELINE - names}"
    # Every studio_* tool present is one of the ten baseline tools.
    assert {n for n in names if n.startswith("haybale-studio_")} == _BASELINE
