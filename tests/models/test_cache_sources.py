"""Built-in cache sources: verified default locations, env overrides, prefixes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from haybale_models.sources import FolderSource, TorchHubSource, builtin_sources
from haybale_models.sources.caches import (
    cache_sources,
    keras_dir,
    rembg_dir,
    torchhub_dir,
    ultralytics_dir,
)
from haybale_models.store.index import ModelIndex

_ENV = (
    "TORCH_HOME",
    "XDG_CACHE_HOME",
    "U2NET_HOME",
    "REMBG_HOME",
    "XDG_DATA_HOME",
    "KERAS_HOME",
    "YOLO_CONFIG_DIR",
    "XDG_CONFIG_HOME",
)


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_suggested_location_honours_env(monkeypatch, home, tmp_path) -> None:
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "t"))
    assert torchhub_dir() == tmp_path / "t" / "hub" / "checkpoints"
    monkeypatch.setenv("U2NET_HOME", str(tmp_path / "u"))
    assert rembg_dir() == tmp_path / "u"
    monkeypatch.setenv("KERAS_HOME", str(tmp_path / "k"))
    assert keras_dir() == tmp_path / "k" / "models"
    config = tmp_path / "yolo"
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(config))
    (config / "Ultralytics").mkdir(parents=True)
    (config / "Ultralytics" / "settings.json").write_text(json.dumps({"weights_dir": str(tmp_path / "w")}))
    assert ultralytics_dir() == tmp_path / "w"


def test_torch_xdg_cache_is_the_second_choice(monkeypatch, home) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "xdg"))
    assert torchhub_dir() == home / "xdg" / "torch" / "hub" / "checkpoints"


def test_defaults_without_env(home) -> None:
    assert torchhub_dir() == home / ".cache" / "torch" / "hub" / "checkpoints"
    assert rembg_dir() == home / ".u2net"
    assert keras_dir() == home / ".keras" / "models"


def test_ultralytics_fallback_is_its_config_dir_not_the_cwd(monkeypatch, home, tmp_path) -> None:
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(tmp_path / "cfg"))
    expected = tmp_path / "cfg" / "Ultralytics" / "weights"
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    from_first = ultralytics_dir()
    monkeypatch.chdir(second)
    from_second = ultralytics_dir()
    assert from_first == from_second == expected
    assert from_first.is_absolute()


def test_rembg_prefers_an_existing_rembg_home(monkeypatch, home) -> None:
    (home / ".rembg").mkdir()
    assert rembg_dir() == home / ".rembg"
    monkeypatch.setenv("REMBG_HOME", str(home / "r"))
    assert rembg_dir() == home / "r"
    monkeypatch.setenv("U2NET_HOME", str(home / "u"))
    assert rembg_dir() == home / "u"


def test_ultralytics_without_a_weights_key_uses_its_default(monkeypatch, home) -> None:
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(home / "c"))
    settings = home / "c" / "Ultralytics" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{not json")
    assert ultralytics_dir() == home / "c" / "Ultralytics" / "weights"
    settings.write_text(json.dumps({"runs_dir": "x"}))
    assert ultralytics_dir() == home / "c" / "Ultralytics" / "weights"


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", "AppData/Roaming/Ultralytics/weights"),
        ("darwin", "Library/Application Support/Ultralytics/weights"),
        ("linux", ".config/Ultralytics/weights"),
    ],
)
def test_ultralytics_default_config_dir_per_platform(monkeypatch, home, platform, expected) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    assert ultralytics_dir() == home / expected


def test_ultralytics_default_honours_xdg_config_home_on_linux(monkeypatch, home) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    assert ultralytics_dir() == home / "xdg" / "Ultralytics" / "weights"


def test_unresolvable_user_path_does_not_raise(monkeypatch, home) -> None:
    monkeypatch.setenv("TORCH_HOME", "~nosuchuser_hw")
    result = torchhub_dir()
    assert result.is_absolute()
    monkeypatch.setenv("KERAS_HOME", "~nosuchuser_hw")
    assert keras_dir().is_absolute()


def test_every_location_is_absolute(monkeypatch, home) -> None:
    monkeypatch.setenv("KERAS_HOME", "~/k")
    monkeypatch.setenv("TORCH_HOME", "~/t")
    for locate in (torchhub_dir, rembg_dir, keras_dir, ultralytics_dir):
        assert locate().is_absolute()
    assert keras_dir() == home / "k" / "models"


def test_cache_sources_names_and_kinds() -> None:
    sources = cache_sources()
    assert [s.name for s in sources] == ["torchhub", "rembg", "keras", "ultralytics"]
    assert [s.label for s in sources] == ["Torch Hub", "rembg", "Keras", "Ultralytics"]
    assert isinstance(sources[0], TorchHubSource)
    assert all(isinstance(s, FolderSource) for s in sources)


def test_builtin_sources_serve_the_cache_prefixes() -> None:
    s = builtin_sources(ModelIndex(), hf_cache=lambda: None)
    assert {"torchhub", "rembg", "keras", "ultralytics"} <= set(s.builtin_prefixes())
    assert s.primary_prefixes()[:2] == ("https", "hf")
    assert s.download_prefixes() == ("https", "http", "hf")
    assert s.primary_download_prefixes() == ("https", "hf")
