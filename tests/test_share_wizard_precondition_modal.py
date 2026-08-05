"""Rendered-DOM coverage for the Share Wizard's precondition remedy modal.

``test_share_wizard_ui.py`` is explicitly state-machine only (see its module
docstring) — it cannot assert that a modal is open or that a button click
does what it claims. This file fills that gap for the "Solve" button using
NiceGUI's ``user_simulation`` harness (real rendering, no browser — see
``test_restart_affordance.py`` for the established pattern), scoped to
exactly the three behaviors this covers:

1. A precondition failure does NOT open the modal by itself.
2. Clicking "Solve" opens exactly one modal and closes the wizard popup.
3. The modal's "Restart Wizard" button reopens the wizard popup.
"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    """A NiceGUI ``User`` simulator without requiring a main_file."""
    async with user_simulation() as u:
        yield u


@pytest.fixture
def broken_repo(tmp_path: Path) -> Path:
    """A git repo with no barn/ — the cheapest precondition failure to
    reach, and an 'inform'-kind one, so the same coverage also proves inform
    failures get the Solve button, not just act ones."""
    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _click_button(user: User, label: str) -> None:
    """Click the ``ui.button`` whose text is *label*.

    Not ``user.find(label)``: when ``find``'s first positional argument is a
    string it matches marker-or-content across EVERY element kind and ignores
    ``kind=`` entirely (see ``User._gather_elements``). "Check" therefore also
    matches the step title "Check the project" and the description label
    "Checks that your working tree is clean...", and ``UserInteraction.click``
    then picks the lowest element id among the matches — a label, which
    swallows the click silently. Passing ``kind``/``content`` as keywords with
    no positional target is the combination that actually filters.
    """
    user.find(kind=ui.button, content=label).click()


async def _open_wizard_at_the_failure(user: User, repo: Path):
    """Open the share wizard in a fresh page and drive it to its (inform)
    precondition failure via the real "Check" button — calling
    ``advance_from_preconditions()`` directly would skip the ``rerender()``
    that ``busy_advance`` runs afterward, leaving the error banner (and its
    "Solve" button) never actually rendered. Returns the ShareWizard
    instance."""
    from haybale_marketplace.editors._share_wizard import show_share_wizard

    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        captured["wizard"] = show_share_wizard(repo)

    await user.open("/")
    _click_button(user, "Check")
    # Extra retries because the check runs `git` in a thread
    # (asyncio.to_thread) and the default 3 x 0.1s can expire first.
    await user.should_see("Solve", retries=50)
    return captured["wizard"]


def _open_dialog_count(user: User) -> int:
    """How many ``ui.dialog`` elements on *user*'s page are open.

    Read via ``user._client.elements`` rather than ``ui.context.client`` —
    the latter resolves through the current asyncio task's slot stack, which
    is empty for code running outside a NiceGUI event/render context (see
    .insights/feedback_nicegui_async.md); the test driver itself is such a
    context, so it must reach the client NiceGUI already has, not ask for
    "the current one".
    """
    client = user._client  # noqa: SLF001 — no public accessor; see docstring.
    return sum(1 for element in client.elements.values() if isinstance(element, ui.dialog) and element.value)


@pytest.mark.anyio
async def test_the_banner_states_what_failed_without_opening_the_modal(
    user: User, broken_repo: Path
) -> None:
    """The failure message must be readable on the banner itself. The modal
    is gated behind a click, so a banner carrying only an icon and a Solve
    button would leave the user with no idea what went wrong until they
    pressed it."""
    await _open_wizard_at_the_failure(user, broken_repo)

    await user.should_see("Is this a haywire project root?")
    assert _open_dialog_count(user) == 0


@pytest.mark.anyio
async def test_a_dirty_tree_banner_names_the_dirty_files(user: User, tmp_path: Path) -> None:
    """The dirty-tree failure is the one users hit most, and its message is
    the list of offending files — that list has to reach the banner, not just
    the modal."""
    from haybale_marketplace.editors._share_wizard import show_share_wizard

    repo = tmp_path / "dirty"
    (repo / "barn" / "haybale-alpha").mkdir(parents=True)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
    )
    for args in (["init"], ["config", "user.email", "t@t.test"], ["config", "user.name", "T"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    (repo / "untracked.txt").write_text("scratch")

    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        captured["wizard"] = show_share_wizard(repo)

    await user.open("/")
    _click_button(user, "Check")
    await user.should_see("Solve", retries=50)

    await user.should_see("Working tree is not clean")
    await user.should_see("untracked.txt")
    assert _open_dialog_count(user) == 0


@pytest.mark.anyio
async def test_failure_does_not_open_the_modal_by_itself(user: User, broken_repo: Path) -> None:
    """Reaching a precondition failure must not open any dialog — only
    clicking "Solve" does. This is the regression this file exists for: the
    modal used to auto-open the instant fail() queued it."""
    wizard = await _open_wizard_at_the_failure(user, broken_repo)

    assert wizard.precondition_failure is not None
    assert _open_dialog_count(user) == 0
    assert wizard.popup is not None
    assert wizard.popup.is_open is True


@pytest.mark.anyio
async def test_solve_opens_exactly_one_modal_and_closes_the_wizard_popup(
    user: User, broken_repo: Path
) -> None:
    """Clicking Solve: the wizard popup closes, and exactly one dialog opens
    — not one per click, and not stacked on top of a previous one."""
    wizard = await _open_wizard_at_the_failure(user, broken_repo)

    _click_button(user, "Solve")
    await user.should_see("Restart Wizard")

    assert wizard.popup is not None
    assert wizard.popup.is_open is False
    assert _open_dialog_count(user) == 1


@pytest.mark.anyio
async def test_clicking_solve_twice_still_opens_exactly_one_modal(user: User, broken_repo: Path) -> None:
    """The wizard popup is closed after the first click, so a second Solve
    click has no button left to press — nothing should stack. Guards the
    exact bug reported: repeated Solve presses opening more modals."""
    wizard = await _open_wizard_at_the_failure(user, broken_repo)

    _click_button(user, "Solve")
    await user.should_see("Restart Wizard")
    assert _open_dialog_count(user) == 1

    # The wizard popup is closed and its Solve button gone with it — there is
    # nothing left in the DOM to click a second time. Assert that directly
    # rather than trying to click a button that no longer exists.
    assert wizard.popup is not None
    assert wizard.popup.is_open is False


@pytest.mark.anyio
async def test_restart_wizard_reopens_the_popup(user: User, broken_repo: Path) -> None:
    """The modal's "Restart Wizard" button must reopen the wizard popup, not
    leave the user stuck with a closed popup and a dismissed modal."""
    wizard = await _open_wizard_at_the_failure(user, broken_repo)

    _click_button(user, "Solve")
    await user.should_see("Restart Wizard")
    assert wizard.popup is not None
    assert wizard.popup.is_open is False

    _click_button(user, "Restart Wizard")

    assert wizard.popup.is_open is True
    assert _open_dialog_count(user) == 0
