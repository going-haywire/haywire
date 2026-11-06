"""How a catalog entry is put into words for the picker and the Models editor."""

from types import SimpleNamespace
from typing import Any

import pytest

from haybale_models.describe import (
    DESCRIPTION_LIMIT,
    entry_description,
    entry_licence_text,
    entry_search_text,
    search_matches,
    entry_summary,
)

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
        "commercial": False,
    }
    return SimpleNamespace(**{**base, **fields})


def test_the_summary_names_scale_architecture_and_the_first_tags():
    assert entry_summary(_entry()) == "4x · ESRGAN · anime, photo, jpeg, restoration +1"
    assert entry_summary(_entry(), scale=False) == "ESRGAN · anime, photo, jpeg, restoration +1"
    assert entry_summary(_entry(scale=None, tags=[], architecture="")) == ""


def test_the_description_is_plain_text_with_purpose_author_and_licence():
    assert entry_description(_entry()) == (
        "Real-ESRGAN aims at general restoration.\n"
        "Purpose: SR · By xinntao · Licence: BSD-3-Clause · non-commercial"
    )


def test_a_long_description_is_cut_at_a_word():
    text = entry_description(
        _entry(description="word " * 200, purpose=[], author="", license="", commercial=True)
    )
    assert text.endswith(" …")
    assert len(text) <= DESCRIPTION_LIMIT + 2


def test_search_text_covers_tags_purpose_and_description():
    text = entry_search_text(_entry())
    assert "anime" in text
    assert "sr" in text.split()
    assert "general restoration" in text


def test_licence_text_says_non_commercial_unless_flagged() -> None:
    assert entry_licence_text(_entry(license="MIT")) == "MIT · non-commercial"
    assert entry_licence_text(_entry(license="")) == "non-commercial"
    assert entry_licence_text(_entry(license="MIT", commercial=True)) == "MIT"
    assert entry_licence_text(_entry(license="", commercial=True)) == ""


def test_the_tip_says_non_commercial_too() -> None:
    assert "non-commercial" in entry_description(_entry(license="MIT"))
    assert "non-commercial" not in entry_description(_entry(license="MIT", commercial=True))


def test_every_word_must_appear_in_any_order() -> None:
    assert search_matches("esrgan anime", "anime esrgan photo")
    assert search_matches("anime esrgan", "photo esrgan anime")
    assert not search_matches("anime cartoon", "anime esrgan")


def test_a_word_may_be_part_of_a_longer_one() -> None:
    assert search_matches("real x4", "realesrgan_x4plus")


def test_an_empty_search_matches_everything() -> None:
    assert search_matches("", "anything")
    assert search_matches("   ", "anything")


def test_commercial_does_not_match_non_commercial() -> None:
    assert not search_matches("commercial", "esrgan non-commercial")
    assert search_matches("commercial", "esrgan commercial")
    assert search_matches("non-commercial", "esrgan non-commercial")
    assert search_matches("non", "esrgan non-commercial")


def test_search_text_holds_scale_licence_and_commercial_use() -> None:
    text = entry_search_text(_entry(scale=4, license="BSD-3-Clause"))
    assert search_matches("4x bsd non-commercial", text)
    assert not search_matches("commercial", entry_search_text(_entry(description="")))
    flagged = entry_search_text(_entry(commercial=True, description=""))
    assert search_matches("commercial", flagged)
    assert not search_matches("non-commercial", flagged)


def test_search_text_leaves_out_what_an_entry_lacks() -> None:
    assert "none" not in entry_search_text(
        _entry(scale=None, description="", tags=[], purpose=[], commercial=True)
    )
