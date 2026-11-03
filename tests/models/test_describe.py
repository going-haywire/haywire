"""How a catalog entry is put into words for the picker and the Models editor."""

from types import SimpleNamespace
from typing import Any

import pytest

from haybale_models.describe import DESCRIPTION_LIMIT, entry_description, entry_search_text, entry_summary

pytestmark = pytest.mark.unit


def _entry(**fields: Any) -> Any:
    base = {
        "name": "RealESRGAN_x4Plus",
        "architecture": "ESRGAN",
        "scale": 4,
        "purpose": ["SR"],
        "tags": ["anime", "photo", "jpeg", "restoration", "research"],
        "description": "[Real-ESRGAN](https://example.invalid/r) aims at **general** restoration.",
        "author": "xinntao",
        "license": "BSD-3-Clause",
    }
    return SimpleNamespace(**{**base, **fields})


def test_the_summary_names_scale_architecture_and_the_first_tags():
    assert entry_summary(_entry()) == "4x · ESRGAN · anime, photo, jpeg, restoration +1"
    assert entry_summary(_entry(), scale=False) == "ESRGAN · anime, photo, jpeg, restoration +1"
    assert entry_summary(_entry(scale=None, tags=[], architecture="")) == ""


def test_the_description_is_plain_text_with_purpose_author_and_licence():
    assert entry_description(_entry()) == (
        "Real-ESRGAN aims at general restoration.\nPurpose: SR · By xinntao · Licence: BSD-3-Clause"
    )


def test_a_long_description_is_cut_at_a_word():
    text = entry_description(_entry(description="word " * 200, purpose=[], author="", license=""))
    assert text.endswith(" …")
    assert len(text) <= DESCRIPTION_LIMIT + 2


def test_search_text_covers_tags_purpose_and_description():
    text = entry_search_text(_entry())
    assert "anime" in text
    assert "sr" in text.split()
    assert "general restoration" in text
