"""Variant matcher."""

from pathlib import Path
from typing import Any

from haybale_models.matcher import candidates, entry_matches, matches

from haywire.core.library.identity import LibraryIdentity
from haywire.core.models import ModelFile, Resource


def res(**tags: Any) -> Resource:
    return Resource(
        platform=tags.pop("platform", ""),
        type=tags.pop("type", ""),
        size=None,
        sha256=None,
        urls=("https://x/y",),
        files=(ModelFile("", None, None, ("https://x/y",)),),
        **tags,
    )


def test_missing_tag_is_wildcard():
    assert matches(res(platform="pytorch"), {"precision": "fp16"})


def test_present_tag_must_equal():
    assert not matches(res(precision="fp32"), {"precision": "fp16"})


def test_rank_follows_preference_order():
    fp16, fp32 = res(precision="fp16"), res(precision="fp32")
    assert candidates([fp32, fp16], [{"precision": "fp16"}, {}]) == [(0, fp16), (1, fp32)]


def test_resource_listed_once_at_best_rank():
    fp16 = res(precision="fp16")
    agnostic = res()
    out = candidates([fp16, agnostic], [{"precision": "fp16"}, {}])
    assert out == [(0, fp16), (0, agnostic)]


def test_empty_preference_matches_all():
    a, b = res(precision="fp16"), res(precision="fp32")
    assert candidates([a, b], []) == [(0, a), (0, b)]


class _Entry:
    path = Path("x.json")
    library = LibraryIdentity.__new__(LibraryIdentity)

    def fields(self) -> dict[str, Any]:
        return {"architecture": "ESRGAN", "scale": 4, "purpose": ["upscale", "denoise"], "tags": []}


def test_entry_filter_list_overlap_and_scalar():
    e: Any = _Entry()
    assert entry_matches(e, {"purpose": ["denoise", "x"]})
    assert not entry_matches(e, {"purpose": ["x"]})
    assert entry_matches(e, {"scale": [2, 4], "architecture": ["ESRGAN"]})
    assert not entry_matches(e, {"scale": [2]})
    assert not entry_matches(e, {"unknown": [1]})
    assert entry_matches(e, {})
