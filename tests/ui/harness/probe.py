"""Narrowing wrappers around Optional-returning Playwright probes.

``Locator.bounding_box()`` returns None when the element is detached or has no
layout box, and ``Page.get_attribute()`` returns None when the attribute is
absent. Harness tests treat both as broken preconditions, not as branches under
test — but reading through the None surfaces later as an opaque ``TypeError``
("'NoneType' object is not subscriptable") pointing at the wrong line.

These helpers fail at the probe with the selector in the message.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page


def box(locator: Locator, what: str = "element") -> dict[str, Any]:
    """``locator.bounding_box()``, asserted present."""
    found = locator.bounding_box()
    assert found is not None, f"{what} has no bounding box (detached or not laid out)"
    return dict(found)


def attr(page: Page, selector: str, name: str) -> str:
    """``page.get_attribute()``, asserted present."""
    value = page.get_attribute(selector, name)
    assert value is not None, f"{selector} is missing attribute {name!r}"
    return value
