"""SourceSet: prefix lookup over the built-in sources."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from haybale_models.resolver import ModelMissing, locate_resource, resolve
from haybale_models.sources import (
    FetchRequest,
    ModelSource,
    SourceFailed,
    SourceSet,
    builtin_sources,
    prefix_of,
)
from haybale_models.sources.base import finish_part
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from haywire.core.catalog import ModelFile, Resource

from tests.models.conftest import make_hf_snapshot


class Fake(ModelSource):
    def __init__(self, name: str = "demo") -> None:
        self.name = name
        self.prefixes = (name,)
        self.label = name
        self.volume = "demo:volume"
        self.volume_noun = "demo volume"

    def find(self, address: str) -> Path | None:
        return Path("/found")

    def fetch(self, request: FetchRequest) -> Path:
        return Path("/fetched")


def test_prefix_of() -> None:
    assert prefix_of("HF://o/r/f") == "hf"
    assert prefix_of("https://x/y") == "https"
    assert prefix_of("/abs/path") is None


def test_prefixes_are_case_insensitive() -> None:
    source = Fake(name="demo")
    source.prefixes = ("Demo",)
    s = SourceSet([source])
    assert s.lookup("demo://x") is source
    assert s.lookup("DEMO://x") is source
    assert source.prefixes == ("Demo",)


def test_unavailable_names_the_first_prefix_only_when_nothing_serves() -> None:
    s = SourceSet([Fake(name="demo")])
    assert s.unavailable(["ultra://a", "demo://b"]) is None
    assert s.unavailable(["ultra://a", "x://b"]) == "ultra"


def _demo_catalog() -> tuple[Any, str]:
    resource = Resource(
        "pytorch", "pth", None, None, ("demo://w",), (ModelFile("", None, None, ("demo://w",)),), None
    )
    key = "lib-a:catalog:demo"
    entry = SimpleNamespace(
        resources=(resource,),
        class_identity=SimpleNamespace(registry_key=key),
        name="demo",
        library=SimpleNamespace(name="lib-a"),
    )
    return SimpleNamespace(entry=lambda k: entry if k == key else None), key


@pytest.fixture
def state(monkeypatch: pytest.MonkeyPatch, models_env: Any) -> Any:
    from haybale_models import consumer
    from haybale_models.keys import MODELS_VOLUME
    from haybale_models.store.index import ModelIndex

    from haywire.core.volumes import location_of

    location_of(MODELS_VOLUME).mkdir(parents=True, exist_ok=True)
    index = ModelIndex()
    fake = SimpleNamespace(index=index, sources=builtin_sources(index, hf_cache=lambda: None))
    monkeypatch.setattr(consumer, "models_state", lambda: fake)
    return fake


def test_a_failing_source_find_is_not_found_not_a_crash(
    state: Any, caplog: pytest.LogCaptureFixture
) -> None:
    class Failing(Fake):
        def find(self, address: str) -> Path | None:
            raise RuntimeError("boom")

    caplog.set_level(logging.WARNING, logger="haybale_models.resolver")
    catalog, key = _demo_catalog()
    with pytest.raises(ModelMissing):
        resolve(
            ModelRef(catalog=key),
            [],
            catalog=catalog,
            index=state.index,
            sources=SourceSet([Failing()]),
        )
    assert any(
        r.name == "haybale_models.resolver"
        and r.levelno == logging.WARNING
        and r.getMessage() == "source 'demo' failed to look up demo://w; treated as not found"
        for r in caplog.records
    )


def test_status_names_the_cache() -> None:
    from haybale_models.status import resource_status

    assert resource_status("Torch Hub cache", []) == "Torch Hub cache"
    assert resource_status("local", []) == "local"
    assert resource_status(None, [], unavailable="demo") == "source unavailable: demo:// not provided"


def test_holding_names_the_source_of_a_cache_file(tmp_path: Path, models_env: Any) -> None:
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource
    from haybale_models.store.index import ModelIndex

    torch = TorchHubSource(name="torchhub", label="Torch Hub", locate=lambda: tmp_path / "t", description="")
    sources = SourceSet([HttpsSource(ModelIndex()), torch])
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "w.pth").write_bytes(b"1")
    assert sources.holding(tmp_path / "t" / "w.pth") is None  # volume not defined yet: holds nothing
    torch.ensure()
    assert sources.holding(tmp_path / "t" / "w.pth") is torch
    assert sources.holding(tmp_path / "models" / "x.bin") is sources.lookup("https://x")
    assert sources.holding(tmp_path / "elsewhere.bin") is None


def test_holding_picks_the_deepest_matching_root(tmp_path: Path, models_env: Any) -> None:
    from haybale_models.keys import MODELS_VOLUME
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource
    from haybale_models.store.index import ModelIndex

    torch = TorchHubSource(
        name="torchhub", label="Torch Hub", locate=lambda: tmp_path / "all" / "t", description=""
    )
    (tmp_path / "all" / "t").mkdir(parents=True)
    torch.ensure()
    models_env.update(MODELS_VOLUME, location=tmp_path / "all")  # the Models volume nests above the cache
    sources = SourceSet([HttpsSource(ModelIndex()), torch])
    (tmp_path / "all" / "t" / "w.pth").write_bytes(b"1")
    assert sources.holding(tmp_path / "all" / "t" / "w.pth") is torch
    assert sources.holding(tmp_path / "all" / "x.bin") is sources.lookup("https://x")


@pytest.mark.unit
def test_download_prefixes_list_every_prefix_of_download_sources() -> None:
    from haybale_models.sources import builtin_sources
    from haybale_models.store.index import ModelIndex

    s = builtin_sources(ModelIndex(), hf_cache=lambda: None)
    assert s.download_prefixes() == ("https", "http", "hf")
    assert s.primary_download_prefixes() == ("https", "hf")


def test_hf_source_names_whole_repo_folders() -> None:
    from haybale_models.sources.https import HttpsSource

    commit = "a" * 40
    hf_source = builtin_sources(ModelIndex(), hf_cache=lambda: None).lookup("hf://o/r")
    assert hf_source is not None
    assert hf_source.names_folder(f"hf://o/r@{commit}")
    assert not hf_source.names_folder("hf://o/r/w.bin")
    assert not HttpsSource(ModelIndex()).names_folder("https://x/y")
    assert Fake().find_folder("demo://x", ()) is None
    assert hf_source.find_folder(f"hf://o/r@{commit}", ()) is None  # no cache volume


def test_hf_parse_refuses_a_whole_repo_branch() -> None:
    hf_source = builtin_sources(ModelIndex(), hf_cache=lambda: None).lookup("hf://o/r")
    assert hf_source is not None
    with pytest.raises(ValueError, match="needs a commit"):
        hf_source.parse("hf://o/r@main")


def _sources(tmp_path: Path) -> Any:
    return builtin_sources(ModelIndex(), hf_cache=lambda: tmp_path / "hf")


def test_https_page_url_is_the_address(tmp_path: Path) -> None:
    address = "https://mega.nz/file/x#k"
    assert _sources(tmp_path).lookup(address).page_url(address) == address


def test_hf_page_url(tmp_path: Path) -> None:
    address = "hf://org/repo/sub/f.bin@abc"
    assert (
        _sources(tmp_path).lookup(address).page_url(address)
        == "https://huggingface.co/org/repo/blob/abc/sub/f.bin"
    )


def test_hf_page_url_defaults_to_main(tmp_path: Path) -> None:
    address = "hf://org/repo/f.bin"
    assert _sources(tmp_path).lookup(address).page_url(address) == (
        "https://huggingface.co/org/repo/blob/main/f.bin"
    )


def test_whole_repo_and_malformed_hf_addresses_have_no_page_url(tmp_path: Path) -> None:
    source = _sources(tmp_path).lookup("hf://x")
    assert source.page_url("hf://org/repo@" + "a" * 40) is None
    assert source.page_url("hf://nonsense") is None


def test_a_cache_source_has_no_page_url(tmp_path: Path) -> None:
    address = "torchhub://w-abcdef12.pth"
    assert _sources(tmp_path).lookup(address).page_url(address) is None


def test_only_the_web_source_has_indexed_addresses(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    assert sources.lookup("https://h/f").indexed_addresses is True
    assert sources.lookup("hf://o/r/f").indexed_addresses is False
    assert sources.lookup("torchhub://w.pth").indexed_addresses is False


def test_finish_part_moves_a_matching_file(tmp_path: Path) -> None:
    part, target = tmp_path / "w.pth.part", tmp_path / "w.pth"
    part.write_bytes(b"abc")
    finish_part(part, target, digest="d" * 64, size=3, sha256="d" * 64)
    assert target.read_bytes() == b"abc"
    assert not part.exists()


def test_finish_part_reports_got_and_expected_size(tmp_path: Path) -> None:
    part, target = tmp_path / "w.pth.part", tmp_path / "w.pth"
    part.write_bytes(b"abc")
    with pytest.raises(SourceFailed, match="size mismatch: got 3 bytes, expected 9"):
        finish_part(part, target, digest="d" * 64, size=9, sha256=None)
    assert not part.exists()
    assert not target.exists()


def test_finish_part_reports_got_and_expected_digest(tmp_path: Path) -> None:
    part, target = tmp_path / "w.pth.part", tmp_path / "w.pth"
    part.write_bytes(b"abc")
    got, expected = "d" * 64, "e" * 64
    with pytest.raises(SourceFailed, match=f"digest mismatch: got {got}, expected {expected}"):
        finish_part(part, target, digest=got, size=None, sha256=expected)
    assert not part.exists()
    assert not target.exists()


def test_a_pinned_hf_file_in_the_shared_store_is_accepted(tmp_path: Path, models_env: Any) -> None:
    """The final file is named by its Xet hash; the repo's link keeps the sha256."""
    data = b"shared-weights"
    sha = hashlib.sha256(data).hexdigest()
    commit = "a" * 40
    root = tmp_path / "hub"
    root.mkdir()
    make_hf_snapshot(root, "org/repo", commit, {"a.bin": data}, None, linked=True, shared=True)
    index = ModelIndex()
    sources = builtin_sources(index, hf_cache=lambda: root)
    file = ModelFile("", sha, len(data), (f"hf://org/repo/a.bin@{commit}",))
    resource = Resource(
        platform="onnx", type="onnx", size=len(data), sha256=sha, urls=file.urls, files=(file,)
    )
    assert locate_resource(resource, index, sources) is not None
    other = ModelFile("", "f" * 64, len(data), file.urls)
    wrong = Resource(
        platform="onnx", type="onnx", size=len(data), sha256="f" * 64, urls=file.urls, files=(other,)
    )
    assert locate_resource(wrong, index, sources) is None
