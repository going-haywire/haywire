"""Store layout."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from haybale_models.store.layout import target_path

from haywire.core.models import ModelFile, Resource

ROOT = Path("/root")


def entry() -> Any:
    return SimpleNamespace(library=SimpleNamespace(name="lib"), path=Path("cat/my-model.json"))


def resource(**kw: Any) -> Resource:
    return Resource(platform="pytorch", type="pth", size=None, sha256=None, urls=(), files=(), **kw)


def test_catalog_single_file():
    p = target_path(
        entry=entry(), resource=None, file=None, url="https://h/a/w.pth", sha256="a" * 64, root=ROOT
    )
    assert p == ROOT / "lib" / "my-model" / "w.pth"


def test_bundle_uses_variant_folder():
    f = ModelFile("sub/m.bin", None, None, ())
    p = target_path(
        entry=entry(),
        resource=resource(precision="fp16"),
        file=f,
        url="https://h/m.bin",
        sha256=None,
        root=ROOT,
    )
    assert p == ROOT / "lib" / "my-model" / "pytorch-pth-fp16" / "sub" / "m.bin"


def test_pasted_url_goes_to_downloads_host():
    p = target_path(
        entry=None, resource=None, file=None, url="https://ex.com/p/w.pth", sha256=None, root=ROOT
    )
    assert p == ROOT / "downloads" / "ex.com" / "w.pth"


def test_name_clash_gets_sha8_suffix(tmp_path: Path):
    target = tmp_path / "downloads" / "ex.com" / "w.pth"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    kw: dict[str, Any] = dict(
        entry=None, resource=None, file=None, url="https://ex.com/w.pth", root=tmp_path
    )
    new = "b" * 64
    assert target_path(sha256=new, existing_sha256=lambda _p: "a" * 64, **kw) == target.with_name(
        "w-bbbbbbbb.pth"
    )
    assert target_path(sha256=new, existing_sha256=lambda _p: new, **kw) == target
    assert target_path(sha256=new, existing_sha256=lambda _p: None, **kw) == target
    assert target_path(sha256=new, **kw) == target


def test_query_string_and_percent_encoding_stripped():
    p = target_path(
        entry=None,
        resource=None,
        file=None,
        url="https://ex.com/a%20b.pth?download=true",
        sha256=None,
        root=ROOT,
    )
    assert p.name == "a b.pth"


def test_empty_basename_falls_back():
    p = target_path(entry=None, resource=None, file=None, url="https://ex.com/", sha256=None, root=ROOT)
    assert p.name == "model.bin"


def test_dot_basenames_fall_back():
    for url in ("https://ex.com/..", "https://ex.com/%2e%2e", "https://ex.com/a/%2E%2E/"):
        p = target_path(entry=None, resource=None, file=None, url=url, sha256=None, root=ROOT)
        assert p == ROOT / "downloads" / "ex.com" / "model.bin", url


def test_bundle_path_traversal_refused():
    import pytest

    for bad in ("../x.bin", "a/../../x.bin", "/etc/x", "a\\b.bin", "a//b.bin"):
        with pytest.raises(ValueError, match="unsafe bundle"):
            target_path(
                entry=entry(),
                resource=resource(),
                file=ModelFile(bad, None, None, ()),
                url="https://h/m.bin",
                sha256=None,
                root=ROOT,
            )
