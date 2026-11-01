"""Offline resolver: ModelRef + preference -> local files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import huggingface_hub
import pytest

from haybale_models.keys import MODELS_VOLUME
from haybale_models.resolver import FetchSpec, ModelMissing, resolve
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from haywire.core.catalog import CatalogRegistry, ModelFile, Resource
from haywire.core.volumes import VolumeStore, location_of

KEY = "lib:catalog:demo"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def res(
    data: bytes | None,
    precision: str | None = None,
    urls: tuple[str, ...] = (),
    files: tuple[ModelFile, ...] | None = None,
) -> Resource:
    digest = sha(data) if data is not None else None
    if files is None:
        files = (ModelFile("", digest, None, urls),)
    return Resource("pytorch", "pth", None, digest, urls, files, None, precision)


def make_catalog(*resources: Resource) -> CatalogRegistry:
    entry = SimpleNamespace(
        resources=resources, class_identity=SimpleNamespace(registry_key=KEY), name="demo"
    )
    return cast(CatalogRegistry, SimpleNamespace(entry=lambda k: cast(Any, entry) if k == KEY else None))


@pytest.fixture
def index(models_env: VolumeStore) -> ModelIndex:
    location_of(MODELS_VOLUME, models_env).mkdir(parents=True, exist_ok=True)
    return ModelIndex()


def put_local(index: ModelIndex, models_env: VolumeStore, name: str, data: bytes) -> Path:
    path = location_of(MODELS_VOLUME, models_env) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    index.scan()
    index.hash_pending()
    return path


def test_best_local_wins_and_reports_better(index: ModelIndex, models_env: VolumeStore) -> None:
    fp16, fp32 = b"half", b"full-precision"
    catalog = make_catalog(res(fp16, "fp16"), res(fp32, "fp32"))
    put_local(index, models_env, "b.pth", fp32)
    r = resolve(
        ModelRef(catalog=KEY), [{"precision": "fp16"}, {}], catalog=catalog, index=index, hf_cache=None
    )
    assert r.resource is not None
    assert r.resource.precision == "fp32"
    assert r.better_unfetched is not None
    assert r.better_unfetched.precision == "fp16"
    assert r.rank == 1
    assert r.sha256 == sha(fp32)
    assert r.size == len(fp32)
    assert r.path.read_bytes() == fp32


def test_best_local_reports_no_better_when_rank0(index: ModelIndex, models_env: VolumeStore) -> None:
    catalog = make_catalog(res(b"a", "fp16"), res(b"b", "fp32"))
    put_local(index, models_env, "a.pth", b"a")
    r = resolve(ModelRef(catalog=KEY), [{"precision": "fp16"}], catalog=catalog, index=index, hf_cache=None)
    assert r.better_unfetched is None
    assert r.rank == 0


def test_missing_lists_rank0_variant(index: ModelIndex) -> None:
    catalog = make_catalog(res(b"a", "fp16"), res(b"b", "fp32"))
    with pytest.raises(ModelMissing) as exc:
        resolve(ModelRef(catalog=KEY), [{"precision": "fp32"}], catalog=catalog, index=index, hf_cache=None)
    assert exc.value.reason == "model missing — fetch it from Models"
    (spec,) = exc.value.wanted
    assert isinstance(spec, FetchSpec)
    assert spec.resource is not None
    assert spec.resource.precision == "fp32"
    assert spec.identity == (KEY, "pytorch-pth-fp32")


def test_hf_ref_resolves_from_cache_offline(
    index: ModelIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"x")
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: str(blob))

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", boom)
    ref = ModelRef(urls=("hf://o/r/m.bin",))
    r = resolve(ref, [], catalog=make_catalog(), index=index, hf_cache=tmp_path)
    assert r.path == blob
    assert r.size == 1


def test_unpinned_file_ref_resolves_by_source(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "w.pth", b"weights")
    index.add(path, sha(b"weights"), "https://x/w.pth")
    r = resolve(ModelRef(urls=("https://x/w.pth",)), [], catalog=make_catalog(), index=index, hf_cache=None)
    assert r.path == path
    assert r.sha256 == sha(b"weights")
    with pytest.raises(ModelMissing) as exc:
        resolve(ModelRef(urls=("https://x/other",)), [], catalog=make_catalog(), index=index, hf_cache=None)
    assert exc.value.wanted[0].identity == ("https://x/other",)


def test_pinned_file_ref_by_digest(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "w.pth", b"weights")
    ref = ModelRef(sha256=sha(b"weights"), size=7)
    assert resolve(ref, [], catalog=make_catalog(), index=index, hf_cache=None).path == path


def test_bundle_needs_every_file(index: ModelIndex, models_env: VolumeStore) -> None:
    a, b = b"alpha", b"beta"
    files = (ModelFile("a.bin", sha(a), None, ()), ModelFile("b.bin", sha(b), None, ()))
    catalog = make_catalog(res(None, files=files))
    put_local(index, models_env, "v/a.bin", a)
    with pytest.raises(ModelMissing):
        resolve(ModelRef(catalog=KEY), [], catalog=catalog, index=index, hf_cache=None)
    put_local(index, models_env, "v/b.bin", b)
    r = resolve(ModelRef(catalog=KEY), [], catalog=catalog, index=index, hf_cache=None)
    assert set(r.files) == {"a.bin", "b.bin"}
    assert r.path == location_of(MODELS_VOLUME, models_env) / "v"
    assert r.size == len(a) + len(b)
    pool = f"a.bin:{sha(a)}\nb.bin:{sha(b)}"
    assert r.sha256 == hashlib.sha256(pool.encode()).hexdigest()


def test_empty_ref_says_no_model_chosen(index: ModelIndex) -> None:
    with pytest.raises(ModelMissing) as exc:
        resolve(ModelRef.empty(), [], catalog=make_catalog(), index=index, hf_cache=None)
    assert exc.value.reason == "no model chosen"
    assert exc.value.wanted == []


def test_unknown_catalog_key(index: ModelIndex) -> None:
    with pytest.raises(ModelMissing, match="is not installed") as exc:
        resolve(ModelRef(catalog="x:catalog:nope"), [], catalog=make_catalog(), index=index, hf_cache=None)
    assert "x:catalog:nope" in exc.value.reason


def test_volume_problem_is_the_reason(models_env: VolumeStore) -> None:
    index = ModelIndex()
    index.scan()  # location does not exist
    assert index.problem
    with pytest.raises(ModelMissing) as exc:
        resolve(ModelRef(sha256="ab" * 32), [], catalog=make_catalog(), index=index, hf_cache=None)
    assert exc.value.reason == index.problem


def test_unpinned_resource_resolves_by_source(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "u.pth", b"u")
    index.add(path, sha(b"u"), "https://x/u.pth")
    catalog = make_catalog(res(None, urls=("https://x/u.pth",)))
    r = resolve(ModelRef(catalog=KEY), [], catalog=catalog, index=index, hf_cache=None)
    assert r.path == path
    assert r.sha256 == sha(b"u")


def _hf_blobs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, names: dict[str, str]) -> None:
    """Stub the HF cache: ``repo/file`` -> a 40-hex (git sha1) blob, as for non-LFS files."""

    def fake(repo: str, filename: str, **k: object) -> str:
        blob = tmp_path / repo.replace("/", "_") / ("a" * 40 if repo.startswith("a") else "b" * 40)
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(names[f"{repo}/{filename}"].encode())
        return str(blob)

    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", fake)


def test_undigested_files_get_distinct_nonempty_keys(
    index: ModelIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _hf_blobs(monkeypatch, tmp_path, {"a/x/config.json": "1", "b/y/config.json": "2"})
    ra = resolve(
        ModelRef(urls=("hf://a/x/config.json",)), [], catalog=make_catalog(), index=index, hf_cache=tmp_path
    )
    rb = resolve(
        ModelRef(urls=("hf://b/y/config.json",)), [], catalog=make_catalog(), index=index, hf_cache=tmp_path
    )
    assert ra.sha256 == rb.sha256 == ""
    assert ra.key
    assert rb.key
    assert ra.key != rb.key


def test_digested_file_key_is_its_digest(index: ModelIndex, models_env: VolumeStore) -> None:
    put_local(index, models_env, "w.pth", b"weights")
    r = resolve(
        ModelRef(sha256=sha(b"weights"), size=7), [], catalog=make_catalog(), index=index, hf_cache=None
    )
    assert r.key == r.sha256 == sha(b"weights")


def test_bundle_keys_differ_across_repos(
    index: ModelIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def bundle(repo: str) -> ModelRef:
        return ModelRef(urls=(f"hf://{repo}/config.json",))

    files = {
        repo: (ModelFile("config.json", None, None, (f"hf://{repo}/config.json",)),)
        for repo in ("a/x", "b/y")
    }
    _hf_blobs(monkeypatch, tmp_path, {"a/x/config.json": "1", "b/y/config.json": "2"})
    out = {}
    for repo, fs in files.items():
        cat = make_catalog(Resource("pytorch", "pth", None, None, (), fs, None, None))
        out[repo] = resolve(ModelRef(catalog=KEY), [], catalog=cat, index=index, hf_cache=tmp_path)
    assert out["a/x"].sha256 == out["b/y"].sha256 == ""
    assert out["a/x"].key != out["b/y"].key
    assert out["a/x"].key
