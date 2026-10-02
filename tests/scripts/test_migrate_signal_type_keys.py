"""Tests for scripts/migrate_signal_type_keys.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import migrate_signal_type_keys as migrate


def _port(registry_key: str, class_name: str, module: str) -> dict:
    return {
        "kwargs": {"registry_key": registry_key, "class_name": class_name, "module": module},
        "recipe": {"registry_key": registry_key},
    }


def _graph() -> dict:
    return {
        "nodes": {
            "a": {
                "registry_key": "haybale-core:node:BeginPlayNode",
                "node_data": {
                    "ports": {
                        "exec": _port("haybale-core:type:EXEC", "EXEC", "haybale_core.types.specs"),
                        "table": _port("haybale-core:type:DICT", "DICT", "haybale_core.types.specs"),
                        "names": {
                            "kwargs": {
                                "registry_key": "haybale-core:type:PooledType",
                                "class_name": "PooledType",
                                "module": "haybale_core.types.pooled_type",
                            },
                            "recipe": {
                                "registry_key": "haybale-core:type:PooledType",
                                "element_type": {"registry_key": "haybale-core:type:CALLBACK"},
                            },
                        },
                    }
                },
            }
        }
    }


@pytest.mark.unit
def test_a_moved_type_gets_its_new_key_and_module():
    doc = _graph()

    count = migrate.rewrite_document(doc)

    port = doc["nodes"]["a"]["node_data"]["ports"]["exec"]
    assert port["recipe"]["registry_key"] == "haywire-core:type:EXEC"
    assert port["kwargs"]["registry_key"] == "haywire-core:type:EXEC"
    assert port["kwargs"]["module"] == "haywire.barn.builtin.types.exec"
    # exec: recipe key, kwargs key, module; names: the nested element key.
    assert count == 4


@pytest.mark.unit
def test_each_moved_class_gets_its_own_module():
    doc = {
        "ports": {
            "e": _port("haybale-core:type:EXEC", "EXEC", "haybale_core.types.specs"),
            "c": _port("haybale-core:type:CALLBACK", "CALLBACK", "haybale_core.types.specs"),
        }
    }

    migrate.rewrite_document(doc)

    assert doc["ports"]["e"]["kwargs"]["module"] == "haywire.barn.builtin.types.exec"
    assert doc["ports"]["c"]["kwargs"]["module"] == "haywire.barn.builtin.types.callback"


@pytest.mark.unit
def test_a_nested_element_key_is_rewritten():
    doc = _graph()

    migrate.rewrite_document(doc)

    names = doc["nodes"]["a"]["node_data"]["ports"]["names"]
    assert names["recipe"]["element_type"]["registry_key"] == "haywire-core:type:CALLBACK"
    assert names["kwargs"]["module"] == "haybale_core.types.pooled_type"


@pytest.mark.unit
def test_a_type_that_stayed_in_haybale_core_is_untouched():
    doc = _graph()

    migrate.rewrite_document(doc)

    table = doc["nodes"]["a"]["node_data"]["ports"]["table"]
    assert table == _port("haybale-core:type:DICT", "DICT", "haybale_core.types.specs")
    assert doc["nodes"]["a"]["registry_key"] == "haybale-core:node:BeginPlayNode"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("indent", "ensure_ascii", "suffix"),
    [(2, False, ""), (2, True, ""), (2, False, "\n"), (None, False, "")],
)
def test_a_file_keeps_its_formatting(tmp_path: Path, indent: int | None, ensure_ascii: bool, suffix: str):
    doc = _graph()
    doc["name"] = "Grüße"
    path = tmp_path / "g.haywire"
    path.write_text(json.dumps(doc, indent=indent, ensure_ascii=ensure_ascii) + suffix, encoding="utf-8")

    count = migrate.migrate_file(path)

    expected = _graph()
    expected["name"] = "Grüße"
    migrate.rewrite_document(expected)
    assert count == 4
    assert (
        path.read_text(encoding="utf-8")
        == json.dumps(expected, indent=indent, ensure_ascii=ensure_ascii) + suffix
    )


@pytest.mark.unit
def test_check_mode_counts_without_writing(tmp_path: Path):
    path = tmp_path / "g.haywire"
    original = json.dumps(_graph(), indent=2, ensure_ascii=False)
    path.write_text(original, encoding="utf-8")

    assert migrate.migrate_file(path, check=True) == 4
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.unit
def test_a_file_whose_formatting_cannot_be_reproduced_is_refused(tmp_path: Path):
    path = tmp_path / "g.haywire"
    path.write_text(json.dumps(_graph(), indent=4), encoding="utf-8")

    with pytest.raises(migrate.FormatNotReproducibleError):
        migrate.migrate_file(path)


@pytest.mark.unit
def test_main_reports_remaining_keys_in_check_mode(tmp_path: Path):
    (tmp_path / "old.haywire").write_text(
        json.dumps(_graph(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "clean.hwm").write_text(json.dumps({"nodes": {}}, indent=2), encoding="utf-8")

    assert migrate.main(["--check", str(tmp_path)]) == 1
    assert migrate.main([str(tmp_path)]) == 0
    assert migrate.main(["--check", str(tmp_path)]) == 0
