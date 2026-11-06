"""Offline resolver: ModelRef + preference -> local files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import huggingface_hub
import pytest

from haybale_models.keys import MODELS_VOLUME
from haybale_models.matcher import Preference
from haybale_models.resolver import FetchSpec, ModelMissing, folder_address, place_of, resolve
from haybale_models.sources import builtin_sources
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from haywire.core.catalog import CatalogRegistry, ModelFile, Resource
from haywire.core.volumes import VolumeStore, location_of

from tests.models.conftest import make_hf_snapshot

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
        ModelRef(catalog=KEY),
        [{"precision": "fp16"}, {}],
        catalog=catalog,
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
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
    r = resolve(
        ModelRef(catalog=KEY),
        [{"precision": "fp16"}],
        catalog=catalog,
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
    )
    assert r.better_unfetched is None
    assert r.rank == 0


def test_missing_lists_rank0_variant(index: ModelIndex) -> None:
    catalog = make_catalog(res(b"a", "fp16"), res(b"b", "fp32"))
    with pytest.raises(ModelMissing) as exc:
        resolve(
            ModelRef(catalog=KEY),
            [{"precision": "fp32"}],
            catalog=catalog,
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
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
    r = resolve(
        ref,
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: tmp_path),
    )
    assert r.path == blob
    assert r.size == 1


def test_unpinned_file_ref_resolves_by_source(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "w.pth", b"weights")
    index.add(path, sha(b"weights"), "https://x/w.pth")
    r = resolve(
        ModelRef(urls=("https://x/w.pth",)),
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
    )
    assert r.path == path
    assert r.sha256 == sha(b"weights")
    with pytest.raises(ModelMissing) as exc:
        resolve(
            ModelRef(urls=("https://x/other",)),
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
    assert exc.value.wanted[0].identity == ("https://x/other",)


def test_pinned_file_ref_by_digest(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "w.pth", b"weights")
    ref = ModelRef(sha256=sha(b"weights"), size=7)
    assert (
        resolve(
            ref,
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        ).path
        == path
    )


def test_bundle_needs_every_file(index: ModelIndex, models_env: VolumeStore) -> None:
    a, b = b"alpha", b"beta"
    files = (ModelFile("a.bin", sha(a), None, ()), ModelFile("b.bin", sha(b), None, ()))
    catalog = make_catalog(res(None, files=files))
    put_local(index, models_env, "v/a.bin", a)
    with pytest.raises(ModelMissing):
        resolve(
            ModelRef(catalog=KEY),
            [],
            catalog=catalog,
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
    put_local(index, models_env, "v/b.bin", b)
    r = resolve(
        ModelRef(catalog=KEY),
        [],
        catalog=catalog,
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
    )
    assert set(r.files) == {"a.bin", "b.bin"}
    assert r.path == location_of(MODELS_VOLUME, models_env) / "v"
    assert r.size == len(a) + len(b)
    pool = f"a.bin:{sha(a)}\nb.bin:{sha(b)}"
    assert r.sha256 == hashlib.sha256(pool.encode()).hexdigest()


def test_empty_ref_says_no_model_chosen(index: ModelIndex) -> None:
    with pytest.raises(ModelMissing) as exc:
        resolve(
            ModelRef.empty(),
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
    assert exc.value.reason == "no model chosen"
    assert exc.value.wanted == []


def test_unknown_catalog_key(index: ModelIndex) -> None:
    with pytest.raises(ModelMissing, match="is not installed") as exc:
        resolve(
            ModelRef(catalog="x:catalog:nope"),
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
    assert "x:catalog:nope" in exc.value.reason


def test_volume_problem_is_the_reason(models_env: VolumeStore) -> None:
    index = ModelIndex()
    index.scan()  # location does not exist
    assert index.problem
    with pytest.raises(ModelMissing) as exc:
        resolve(
            ModelRef(sha256="ab" * 32),
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )
    assert exc.value.reason == index.problem


def test_unpinned_resource_resolves_by_source(index: ModelIndex, models_env: VolumeStore) -> None:
    path = put_local(index, models_env, "u.pth", b"u")
    index.add(path, sha(b"u"), "https://x/u.pth")
    catalog = make_catalog(res(None, urls=("https://x/u.pth",)))
    r = resolve(
        ModelRef(catalog=KEY),
        [],
        catalog=catalog,
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
    )
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
        ModelRef(urls=("hf://a/x/config.json",)),
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: tmp_path),
    )
    rb = resolve(
        ModelRef(urls=("hf://b/y/config.json",)),
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: tmp_path),
    )
    assert ra.sha256 == rb.sha256 == ""
    assert ra.key
    assert rb.key
    assert ra.key != rb.key


def test_digested_file_key_is_its_digest(index: ModelIndex, models_env: VolumeStore) -> None:
    put_local(index, models_env, "w.pth", b"weights")
    r = resolve(
        ModelRef(sha256=sha(b"weights"), size=7),
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: None),
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
        out[repo] = resolve(
            ModelRef(catalog=KEY),
            [],
            catalog=cat,
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: tmp_path),
        )
    assert out["a/x"].sha256 == out["b/y"].sha256 == ""
    assert out["a/x"].key != out["b/y"].key
    assert out["a/x"].key


def test_pinned_ref_rejects_a_found_file_with_another_digest(index, models_env) -> None:
    path = put_local(index, models_env, "w.pth", b"weights")
    index.add(path, sha(b"weights"), "https://x/w.pth")
    ref = ModelRef(sha256=sha(b"other"), size=5, urls=("https://x/w.pth",))
    with pytest.raises(ModelMissing):
        resolve(
            ref,
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: None),
        )


def _hf_named_blob(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blob_name: str) -> None:
    blob = tmp_path / "snap" / blob_name
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"x")
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: str(blob))


def test_pinned_hf_ref_rejects_an_lfs_blob_of_another_digest(
    index: ModelIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _hf_named_blob(monkeypatch, tmp_path, sha(b"other"))
    ref = ModelRef(sha256=sha(b"weights"), size=1, urls=("hf://o/r/m.bin",))
    with pytest.raises(ModelMissing):
        resolve(
            ref,
            [],
            catalog=make_catalog(),
            index=index,
            sources=builtin_sources(index, hf_cache=lambda: tmp_path),
        )


def test_pinned_hf_ref_accepts_a_blob_of_unknown_digest(
    index: ModelIndex, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _hf_named_blob(monkeypatch, tmp_path, "c" * 40)
    ref = ModelRef(sha256=sha(b"weights"), size=1, urls=("hf://o/r/m.bin",))
    r = resolve(
        ref,
        [],
        catalog=make_catalog(),
        index=index,
        sources=builtin_sources(index, hf_cache=lambda: tmp_path),
    )
    assert r.path == tmp_path / "snap" / ("c" * 40)


def resource_with(cache: str | None, urls: tuple[str, ...] = (), data: bytes | None = None) -> Resource:
    digest = sha(data) if data is not None else None
    return Resource("pytorch", "pth", None, digest, urls, (ModelFile("", digest, None, urls),), cache=cache)


def torch_sources(index: ModelIndex, root: Path) -> Any:
    from haybale_models.sources import SourceSet
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource

    return SourceSet(
        [
            HttpsSource(index),
            TorchHubSource(name="torchhub", label="Torch Hub", locate=lambda: root, description=""),
        ]
    )


def test_catalog_file_resolves_from_its_cache(index: ModelIndex, tmp_path: Path) -> None:
    data = b"cached weights"
    root = tmp_path / "torch"
    root.mkdir()
    (root / "w.pth").write_bytes(data)
    catalog = make_catalog(resource_with("torchhub://w.pth", ("https://x/w.pth",), data))
    resolved = resolve(
        ModelRef(catalog=KEY), [{}], catalog=catalog, index=index, sources=torch_sources(index, root)
    )
    assert resolved.path == root / "w.pth"
    assert resolved.sha256 == sha(data)


def test_pinned_ref_rejects_torchhub_name_with_other_prefix(index: ModelIndex, tmp_path: Path) -> None:
    root = tmp_path / "torch"
    root.mkdir()
    (root / "w-aaaaaaaa.pth").write_bytes(b"other weights")
    pinned = Resource(
        "pytorch",
        "pth",
        None,
        "f37072fd" + "0" * 56,
        (),
        (ModelFile("", "f37072fd" + "0" * 56, None, ()),),
        cache="torchhub://w-aaaaaaaa.pth",
    )
    with pytest.raises(ModelMissing):
        resolve(
            ModelRef(catalog=KEY),
            [{}],
            catalog=make_catalog(pinned),
            index=index,
            sources=torch_sources(index, root),
        )


def test_unserved_cache_names_its_prefix(index: ModelIndex) -> None:
    from haybale_models.resolver import cache_of, unserved_cache

    sources = builtin_sources(index, hf_cache=lambda: None)
    hf = resource_with("hf://o/r/w.pth", ("https://x/w.pth",))
    assert unserved_cache(hf, sources) == "hf"
    assert unserved_cache(resource_with("torchhub://w.pth", ("https://x/w.pth",)), sources) is None
    assert unserved_cache(resource_with(None, ("https://x/w.pth",)), sources) is None
    assert cache_of(hf, hf.files[0]) == "hf://o/r/w.pth"
    bundle = Resource(
        "pytorch",
        "pth",
        None,
        None,
        (),
        (ModelFile("a", None, None, ()), ModelFile("b", None, None, (), "keras://b")),
        cache="torchhub://ignored",
    )
    assert [cache_of(bundle, f) for f in bundle.files] == [None, "keras://b"]


def test_pinned_cache_file_of_the_wrong_size_is_missing(index: ModelIndex, tmp_path: Path) -> None:
    data = b"cached weights"
    root = tmp_path / "torch"
    root.mkdir()
    (root / "w.pth").write_bytes(data)
    pinned = Resource(
        "pytorch",
        "pth",
        len(data) + 1,
        sha(data),
        (),
        (ModelFile("", sha(data), len(data) + 1, ()),),
        cache="torchhub://w.pth",
    )
    with pytest.raises(ModelMissing):
        resolve(
            ModelRef(catalog=KEY),
            [{}],
            catalog=make_catalog(pinned),
            index=index,
            sources=torch_sources(index, root),
        )


def test_fetch_record_digest_outweighs_a_contradicting_torchhub_name(
    index: ModelIndex, tmp_path: Path
) -> None:
    from haybale_models.sources import SourceSet
    from haybale_models.sources.folder import TorchHubSource
    from haybale_models.sources.https import HttpsSource
    from haybale_models.store.records import FetchRecord, FetchRecords

    data = b"weights fetched earlier"
    pin = "f37072fd" + "0" * 56
    root = tmp_path / "torch"
    root.mkdir()
    (root / "w-aaaaaaaa.pth").write_bytes(data)
    records = FetchRecords(tmp_path / "fetched.json")
    source = TorchHubSource(
        name="torchhub", label="Torch Hub", locate=lambda: root, description="", records=records
    )
    sources = SourceSet([HttpsSource(index), source])
    address = "torchhub://w-aaaaaaaa.pth"
    records.add(FetchRecord(source.volume, "w-aaaaaaaa.pth", pin, KEY, address, len(data)))
    pinned = Resource(
        "pytorch", "pth", None, pin, (), (ModelFile("", pin, None, ()),), cache="torchhub://w-aaaaaaaa.pth"
    )
    catalog = make_catalog(pinned)
    resolved = resolve(ModelRef(catalog=KEY), [{}], catalog=catalog, index=index, sources=sources)
    assert resolved.path == root / "w-aaaaaaaa.pth"

    (root / "w-aaaaaaaa.pth").write_bytes(data + b"!")  # the record no longer matches the file
    with pytest.raises(ModelMissing):
        resolve(ModelRef(catalog=KEY), [{}], catalog=catalog, index=index, sources=sources)


# --- whole-repo (folder) resources -------------------------------------------------------

COMMIT = "a" * 40
WHOLE = f"hf://org/repo@{COMMIT}"


def whole_resource(include: tuple[str, ...] = (), urls: tuple[str, ...] = (WHOLE,)) -> Resource:
    return Resource(
        "diffusers", "dir", None, None, urls, (ModelFile("", None, None, urls),), include=include
    )


def whole_sources(index: ModelIndex, tmp_path: Path) -> Any:
    from haybale_models.sources import builtin_sources

    return builtin_sources(index, hf_cache=lambda: tmp_path)


def resolve_whole(resource: Resource, index: ModelIndex, tmp_path: Path) -> Any:
    return resolve(
        ModelRef(catalog=KEY),
        Preference(),
        catalog=make_catalog(resource),
        index=index,
        sources=whole_sources(index, tmp_path),
    )


def test_whole_repo_entry_resolves_to_the_snapshot_folder(
    index: ModelIndex, models_env: VolumeStore
) -> None:
    from haybale_models.keys import HF_VOLUME

    hf_root = location_of(HF_VOLUME, models_env)
    hf_root.mkdir(parents=True, exist_ok=True)
    snapshot = make_hf_snapshot(
        hf_root, "org/repo", COMMIT, {"w.safetensors": b"weights"}, ["w.safetensors"]
    )
    resolved = resolve_whole(whole_resource(), index, hf_root)
    assert resolved.path == snapshot
    assert resolved.sha256 == ""
    assert resolved.size == len(b"weights")
    assert resolved.key.startswith("path:")
    assert place_of(resolved.files.values(), whole_sources(index, hf_root)) == "HF cache"


def test_partial_snapshot_is_missing(index: ModelIndex, tmp_path: Path) -> None:
    make_hf_snapshot(tmp_path, "org/repo", COMMIT, {"a.bin": b"1"}, ["a.bin", "gone.bin"])
    resource = whole_resource()
    with pytest.raises(ModelMissing) as caught:
        resolve_whole(resource, index, tmp_path)
    assert [w.resource for w in caught.value.wanted] == [resource]


def test_include_decides_found(index: ModelIndex, tmp_path: Path) -> None:
    make_hf_snapshot(tmp_path, "org/repo", COMMIT, {"w.safetensors": b"1"}, ["w.safetensors"])
    assert resolve_whole(whole_resource(("*.safetensors",)), index, tmp_path).size == 1
    with pytest.raises(ModelMissing):
        resolve_whole(whole_resource(("*.onnx",)), index, tmp_path)


def test_whole_repo_keys_differ_by_include(index: ModelIndex, tmp_path: Path) -> None:
    make_hf_snapshot(
        tmp_path, "org/repo", COMMIT, {"w.safetensors": b"1", "w.onnx": b"22"}, ["w.safetensors", "w.onnx"]
    )
    a = resolve_whole(whole_resource(("*.safetensors",)), index, tmp_path)
    b = resolve_whole(whole_resource(("*.onnx",)), index, tmp_path)
    assert a.key != b.key
    assert (a.size, b.size) == (1, 2)


def test_malformed_whole_address_is_not_found(index: ModelIndex, tmp_path: Path) -> None:
    with pytest.raises(ModelMissing):
        resolve_whole(whole_resource(urls=("hf://org/repo@main",)), index, tmp_path)


def test_folder_address_is_none_for_file_resources(index: ModelIndex, tmp_path: Path) -> None:
    sources = whole_sources(index, tmp_path)
    for url in ("hf://o/r/w.bin", "https://example.com/w.bin"):
        assert folder_address(res(None, urls=(url,)), sources) is None
    assert folder_address(whole_resource(), sources) == WHOLE


def test_file_ref_with_whole_repo_address_is_missing(index: ModelIndex, tmp_path: Path) -> None:
    ref = ModelRef(urls=(WHOLE,))
    with pytest.raises(ModelMissing) as caught:
        resolve(
            ref,
            Preference(),
            catalog=make_catalog(),
            index=index,
            sources=whole_sources(index, tmp_path),
        )
    assert caught.value.wanted == []
    assert "a whole-repo address belongs in a catalog entry" in str(caught.value)


def test_tree_size_honours_folder_patterns(index: ModelIndex, tmp_path: Path) -> None:
    make_hf_snapshot(
        tmp_path, "org/repo", COMMIT, {"unet/a.bin": b"x" * 10, "b.bin": b"yy"}, ["unet/a.bin", "b.bin"]
    )
    assert resolve_whole(whole_resource(("unet/",)), index, tmp_path).size == 10
