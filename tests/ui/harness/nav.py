"""Navigation helper for harness Playwright tests."""

from playwright.sync_api import Page


def goto_ready(page: Page, url: str) -> None:
    """Navigate and wait until the NiceGUI client is actually interactive.

    A rendered DOM (``wait_for_selector``) does not mean the page is safe to
    interact with: ``updateValue`` sync messages queued during server-side
    render are flushed to the browser only after the websocket connects, and
    an edit typed before that flush lands gets stomped back to the server
    value (which re-emits the old value, silently reverting the edit
    server-side). Every harness page queues a ``data-hw-synced`` body stamp
    as its LAST message (see ``routes._stamp_synced``), so once it appears,
    all pending sync messages have been applied and input is safe.
    """
    page.goto(url)
    page.wait_for_function("() => document.body.dataset.hwSynced === '1'")
