"""The New Node wizard's four panels render, in a simulated page.

The state machine is covered by ``test_new_node_flow.py``; this only checks
that each step's panel builds without raising and shows its key text.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.authoring import RegistrationOutcome

from tests.graph_editor import test_new_node_flow as flow_tests

# The authoring fixtures and the flow builder, shared with the state-machine tests.
packages = flow_tests.packages
dst_identity = flow_tests.dst_identity
dst_library = flow_tests.dst_library
src_modules = flow_tests.src_modules
target = flow_tests.target
env = flow_tests.env

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


async def _open(user: User, env, **kwargs):
    from haybale_graph_editor._new_node_flow import show_new_node_flow

    captured = {}

    @ui.page("/")
    def page() -> None:
        captured["flow"] = show_new_node_flow(flow_tests._flow(env, **kwargs))

    await user.open("/")
    return captured["flow"]


@pytest.mark.anyio
async def test_the_source_step_lists_templates(user: User, env) -> None:
    await _open(user, env)
    await user.should_see("Template-ish")


@pytest.mark.anyio
async def test_the_details_step_shows_the_file_name(user: User, env) -> None:
    await _open(user, env, source_cls=env["single"])
    await user.should_see("nodes/single_copy.py")
    await user.should_see("Starting from Single")


@pytest.mark.anyio
async def test_the_details_step_without_targets_points_at_haywire_init(user: User, env) -> None:
    await _open(user, env, source_cls=env["single"], targets=[])
    await user.should_see("No library in this project can receive a node.")


@pytest.mark.anyio
async def test_the_plan_and_result_steps_render(user: User, env) -> None:
    flow = await _open(user, env, source_cls=env["single"])
    await flow.advance_from_details()
    with user:
        flow.on_render()
    await user.should_see("This will be written:")
    await user.should_see("dst:node:SingleCopy")

    flow.outcome = RegistrationOutcome(status="added", registry_key="dst:node:SingleCopy")
    flow.step = "result"
    with user:
        flow.on_render()
    await user.should_see("Single Copy is registered.")
    await user.should_see("Place")

    flow.outcome = RegistrationOutcome(status="timeout")
    with user:
        flow.on_render()
    await user.should_see("Open file")
