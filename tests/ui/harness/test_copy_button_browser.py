"""
Browser regression for the copy-to-clipboard button (Slice 6, Task 3).

Proves the real click -> JS -> ui.notify() path end-to-end in an actual
browser: mounts a page with ``hui.code_snippet("copy-me")``, clicks its copy
button, and asserts the "Copied to clipboard" notification appears.

Scope note: the harness always runs on localhost, which **is** a secure
context (``navigator.clipboard`` is available), so this test can only exercise
the ``navigator.clipboard.writeText()`` happy path — it does not and cannot
exercise the ``document.execCommand('copy')`` fallback used outside secure
contexts (e.g. a LAN-exposed studio over plain http). That fallback is
covered by the unit tests in tests/ui/test_copy_button.py (Task 1) and by
manual LAN verification (Task 4). See .insights/feedback_clipboard_secure_context.md.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

_COPY_BUTTON_URL = "http://localhost:8090/copy-button"

pytestmark = pytest.mark.ui


def test_copy_button_click_shows_copied_notification(page: Page, harness):
    """Clicking the code_snippet copy button notifies "Copied to clipboard".

    localhost is a secure context, so the click drives the real
    navigator.clipboard.writeText() branch of clipboard_script() (not the
    execCommand fallback) through _perform_copy()'s async handler.
    """
    goto_ready(page, _COPY_BUTTON_URL)

    page.get_by_role("button").click()

    expect(page.get_by_text("Copied to clipboard")).to_be_visible()
