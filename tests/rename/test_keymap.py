"""``haywire rename --map``: exact key-map rewriting of saved graphs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

MAP = """
[[rename]]
old = "haybale-core:node:BeginPlayNode"
new = "haybale-core:node:BeginPlayEventNode"

[[rename]]
old = "haybale-image:type:IMAGE_RGB"
new = "haybale-image:type:RGB_IMAGE"

[[rename]]
old = "haybale-core:type:ArrayType"
new = "haybale-core:type:ARRAY"
old_module = "haybale_core.types.array_type"
new_module = "haybale_core.types.array"

[[rename]]
old = "haybale-core:type:PooledType"
new = "haybale-core:type:POOLED"

[[rename]]
old = "haywire-core:widget:SelectWidget"
new = "haywire-core:widget:MenuWidget"

[[rename]]
old = "haybale-image:adapter:ImageToRgbAdapter"
new = "haybale-image:adapter:ImageToRgbImageAdapter"
"""


def _renames(tmp_path: Path, text: str = MAP) -> list[Any]:
    from haywire_studio.packaging.rename.keymap import load_key_map

    path = tmp_path / "map.toml"
    path.write_text(text)
    renames, blockers = load_key_map(path)
    assert blockers == []
    return renames


def _port(registry_key: str, class_name: str, module: str, recipe: dict) -> dict:
    """A port as the studio saves it: descriptive kwargs plus a type recipe."""
    return {
        "kwargs": {
            "registry_id": class_name,
            "registry_key": registry_key,
            "label": f"{class_name} in",
            "class_name": class_name,
            "module": module,
            "widget_key": "haywire-core:widget:SelectWidget",
        },
        "recipe": recipe,
    }


def _graph() -> dict:
    """A graph holding every saved form of a key, the substring traps, and a nested subgraph."""
    array_of_rgb = {
        "registry_key": "haybale-core:type:ArrayType",
        "element_type": {"registry_key": "haybale-image:type:IMAGE_RGB"},
    }
    pooled_array = {
        "registry_key": "haybale-core:type:PooledType",
        "element_type": {
            "registry_key": "haybale-core:type:ArrayType",
            "element_type": {"registry_key": "haywire-core:type:INT"},
        },
    }
    optional_rgb = {
        "registry_key": "haywire-core:type:OPTIONAL",
        "element_type": {"registry_key": "haybale-image:type:IMAGE_RGB"},
    }
    return {
        "graph_id": "g",
        "nodes": {
            "BeginPlayNode_ea80758b": {
                "node_id": "BeginPlayNode_ea80758b",
                "registry_key": "haybale-core:node:BeginPlayNode",
                "node_data": {
                    "identity": {
                        "registry_id": "BeginPlayNode",
                        "registry_key": "haybale-core:node:BeginPlayNode",
                        "label": "Begin Player",
                        "class_name": "BeginPlayNode",
                        "module": "haybale_core.nodes.begin_play",
                    },
                    "ports": {
                        "arr": _port(
                            "haybale-core:type:ArrayType",
                            "ArrayType",
                            "haybale_core.types.array_type",
                            array_of_rgb,
                        ),
                        "pool": _port(
                            "haybale-core:type:PooledType",
                            "PooledType",
                            "haybale_core.types.pooled_type",
                            pooled_array,
                        ),
                        "opt": _port("haywire-core:type:OPTIONAL", "OPTIONAL", "haywire.barn", optional_rgb),
                    },
                },
            },
            "trap_rgba": {
                "registry_key": "haybale-image:type:IMAGE_RGBA",
                "node_data": {
                    "identity": {"registry_key": "haybale-image:type:IMAGE_RGBA", "class_name": "IMAGE_RGBA"}
                },
            },
            "trap_test_prefix": {
                "registry_key": "haybale-testing:node:TestBeginPlayNode",
                "node_data": {
                    "identity": {
                        "registry_key": "haybale-testing:node:TestBeginPlayNode",
                        "class_name": "TestBeginPlayNode",
                    }
                },
            },
            "trap_other_dist": {"registry_key": "haybale-other:node:BeginPlayNode"},
            "group": {
                "registry_key": "haywire-core:node:GraphNode",
                "node_data": {
                    "subgraph": {
                        "nodes": {
                            "inner": {
                                "registry_key": "haybale-core:node:BeginPlayNode",
                                "node_data": {
                                    "subgraph": {
                                        "nodes": {
                                            "deepest": {"registry_key": "haybale-image:type:IMAGE_RGB"}
                                        }
                                    }
                                },
                            }
                        }
                    }
                },
            },
        },
        "edges": {
            "e": {
                "chain_adapter_keys": [
                    "haybale-image:adapter:ImageToRgbAdapter",
                    "haybale-image:adapter:Other",
                ]
            }
        },
        "properties": {"skin": "haybale-core:node:BeginPlayNode", "note": "uses ArrayType[IMAGE_RGB]"},
    }


def _patched(tmp_path: Path) -> tuple[dict, int, list[str], Any]:
    from haywire_studio.packaging.rename.graphs import KeyMapRewriter, patch_graph_keys

    data = _graph()
    rewriter = KeyMapRewriter(_renames(tmp_path))
    count, leftovers = patch_graph_keys(data, rewriter)
    return data, count, leftovers, rewriter


@pytest.mark.unit
def test_rewrites_node_identity_and_its_descriptive_copies(tmp_path):
    data, _, _, _ = _patched(tmp_path)

    node = data["nodes"]["BeginPlayNode_ea80758b"]
    identity = node["node_data"]["identity"]
    assert node["registry_key"] == "haybale-core:node:BeginPlayEventNode"
    assert identity["registry_key"] == "haybale-core:node:BeginPlayEventNode"
    assert identity["class_name"] == "BeginPlayEventNode"
    assert identity["registry_id"] == "BeginPlayEventNode"
    # No module in the entry: the saved module stays. Label and node id are never rewritten.
    assert identity["module"] == "haybale_core.nodes.begin_play"
    assert identity["label"] == "Begin Player"
    assert node["node_id"] == "BeginPlayNode_ea80758b"
    assert "BeginPlayNode_ea80758b" in data["nodes"]


@pytest.mark.unit
def test_parameterized_types_are_covered_through_their_recipes(tmp_path):
    """``ArrayType[IMAGE_RGB]``, ``PooledType[ArrayType[INT]]`` and ``OPTIONAL[IMAGE_RGB]``
    save the family key with a nested ``element_type``; one entry per family covers them.
    """
    data, _, _, _ = _patched(tmp_path)
    ports = data["nodes"]["BeginPlayNode_ea80758b"]["node_data"]["ports"]

    assert ports["arr"]["recipe"] == {
        "registry_key": "haybale-core:type:ARRAY",
        "element_type": {"registry_key": "haybale-image:type:RGB_IMAGE"},
    }
    assert ports["pool"]["recipe"] == {
        "registry_key": "haybale-core:type:POOLED",
        "element_type": {
            "registry_key": "haybale-core:type:ARRAY",
            "element_type": {"registry_key": "haywire-core:type:INT"},
        },
    }
    assert ports["opt"]["recipe"] == {
        "registry_key": "haywire-core:type:OPTIONAL",
        "element_type": {"registry_key": "haybale-image:type:RGB_IMAGE"},
    }


@pytest.mark.unit
def test_port_copies_follow_and_module_moves_only_when_mapped(tmp_path):
    data, _, _, _ = _patched(tmp_path)
    ports = data["nodes"]["BeginPlayNode_ea80758b"]["node_data"]["ports"]

    arr = ports["arr"]["kwargs"]
    assert (arr["registry_key"], arr["class_name"], arr["registry_id"], arr["module"]) == (
        "haybale-core:type:ARRAY",
        "ARRAY",
        "ARRAY",
        "haybale_core.types.array",
    )
    pool = ports["pool"]["kwargs"]
    assert (pool["class_name"], pool["module"]) == ("POOLED", "haybale_core.types.pooled_type")
    assert arr["widget_key"] == "haywire-core:widget:MenuWidget"
    assert arr["label"] == "ArrayType in"


@pytest.mark.unit
def test_substring_and_lookalike_keys_are_left_alone(tmp_path):
    data, _, _, _ = _patched(tmp_path)
    nodes = data["nodes"]

    assert nodes["trap_rgba"]["registry_key"] == "haybale-image:type:IMAGE_RGBA"
    assert nodes["trap_rgba"]["node_data"]["identity"]["class_name"] == "IMAGE_RGBA"
    assert nodes["trap_test_prefix"]["registry_key"] == "haybale-testing:node:TestBeginPlayNode"
    assert nodes["trap_test_prefix"]["node_data"]["identity"]["class_name"] == "TestBeginPlayNode"
    assert nodes["trap_other_dist"]["registry_key"] == "haybale-other:node:BeginPlayNode"


@pytest.mark.unit
def test_nested_subgraphs_and_adapter_chains_are_rewritten(tmp_path):
    data, _, _, _ = _patched(tmp_path)

    inner = data["nodes"]["group"]["node_data"]["subgraph"]["nodes"]["inner"]
    deepest = inner["node_data"]["subgraph"]["nodes"]["deepest"]
    assert inner["registry_key"] == "haybale-core:node:BeginPlayEventNode"
    assert deepest["registry_key"] == "haybale-image:type:RGB_IMAGE"
    assert data["edges"]["e"]["chain_adapter_keys"] == [
        "haybale-image:adapter:ImageToRgbImageAdapter",
        "haybale-image:adapter:Other",
    ]


@pytest.mark.unit
def test_the_declarations_table_is_rekeyed_in_order(tmp_path):
    from haywire_studio.packaging.rename.graphs import KeyMapRewriter, patch_graph_keys

    data = {
        "declarations": {
            "haybale-core:node:BeginPlayNode": {
                "p": {"recipe": {"registry_key": "haybale-core:type:ArrayType"}}
            },
            "haybale-other:node:Kept": {},
        }
    }
    count, leftovers = patch_graph_keys(data, KeyMapRewriter(_renames(tmp_path)))

    assert list(data["declarations"]) == ["haybale-core:node:BeginPlayEventNode", "haybale-other:node:Kept"]
    assert data["declarations"]["haybale-core:node:BeginPlayEventNode"]["p"]["recipe"] == {
        "registry_key": "haybale-core:type:ARRAY"
    }
    assert (count, leftovers) == (2, [])


@pytest.mark.unit
def test_counts_per_key_and_copies(tmp_path):
    _, count, _, rewriter = _patched(tmp_path)

    assert dict(rewriter.key_counts) == {
        "haybale-core:node:BeginPlayNode": 3,
        "haybale-core:type:ArrayType": 3,
        "haybale-core:type:PooledType": 2,
        "haybale-image:type:IMAGE_RGB": 3,
        "haywire-core:widget:SelectWidget": 3,
        "haybale-image:adapter:ImageToRgbAdapter": 1,
    }
    assert count == sum(rewriter.key_counts.values())
    # identity and pool: class_name + registry_id; arr: those plus module.
    assert rewriter.copies == 7


@pytest.mark.unit
def test_drift_reports_whole_old_keys_outside_key_fields_only(tmp_path):
    """A key parked in a field the mode doesn't own is reported; a lookalike key or a
    bare class name in prose is not.
    """
    _, _, leftovers, _ = _patched(tmp_path)

    assert leftovers == ["properties.skin"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "no [[rename]] entries"),
        ("not toml [", "not valid TOML"),
        ('[[rename]]\nold = "a:node:X"\nnew = "a:node:Y"\ntypo = 1\n', "unknown field"),
        ('[[rename]]\nold = "BeginPlayNode"\nnew = "a:node:Y"\n', "not a registry key"),
        ('[[rename]]\nold = "a:node:X"\nnew = "a:node:X"\n', "old and new are both"),
        ('[[rename]]\nold = "a:node:X"\nnew = "a:type:X"\n', "changes the kind"),
        ('[[rename]]\nold = "a:node:X"\nnew = "a:node:Y"\nold_module = "m"\n', "set both"),
        (
            '[[rename]]\nold = "a:node:X"\nnew = "a:node:Y"\n'
            '[[rename]]\nold = "a:node:X"\nnew = "a:node:Z"\n',
            "more than once",
        ),
        (
            '[[rename]]\nold = "a:node:X"\nnew = "a:node:Y"\n'
            '[[rename]]\nold = "a:node:Y"\nnew = "a:node:Z"\n',
            "Chain",
        ),
    ],
)
def test_invalid_maps_are_blocked(tmp_path, text, message):
    from haywire_studio.packaging.rename.keymap import load_key_map

    path = tmp_path / "map.toml"
    path.write_text(text)
    renames, blockers = load_key_map(path)

    assert renames == []
    assert any(message in blocker.message for blocker in blockers)


@pytest.mark.unit
def test_missing_map_file_is_blocked(tmp_path):
    from haywire_studio.packaging.rename.keymap import load_key_map

    _, blockers = load_key_map(tmp_path / "absent.toml")
    assert blockers
    assert "Cannot read" in blockers[0].message


def _workspace(tmp_path: Path, *, ascii_only: bool = True) -> Path:
    """A clean git workspace with the trap graph in a nested folder and the map outside it."""
    ws = tmp_path / "ws"
    (ws / "flows").mkdir(parents=True)
    data = _graph()
    data["properties"]["title"] = "1 result · 22ms"
    (ws / "flows" / "g.haywire").write_text(
        json.dumps(data, indent=2, ensure_ascii=ascii_only), encoding="utf-8"
    )
    (ws / "flows" / "untouched.haywire").write_text(
        json.dumps({"graph_id": "u", "nodes": {"n": {"registry_key": "haybale-image:type:IMAGE_RGBA"}}})
    )
    (tmp_path / "map.toml").write_text(MAP)
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@t.t"],
        ["config", "user.name", "t"],
        ["add", "-A"],
        ["commit", "-qm", "seed"],
    ):
        subprocess.run(["git", *args], cwd=ws, check=True)
    return ws


@pytest.mark.unit
def test_dry_run_reports_counts_and_writes_nothing(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_key_map_cli

    ws = _workspace(tmp_path)
    before = (ws / "flows" / "g.haywire").read_text()
    code = run_key_map_cli(map_path=tmp_path / "map.toml", workspace_root=ws, dry_run=True)

    out = capsys.readouterr().out
    assert code == 0
    assert (ws / "flows" / "g.haywire").read_text() == before
    assert "6 of 6 map entr(ies) found in graphs" in out
    assert "3 key(s) in 1 graph(s)" in out
    assert "15 change(s) in 1 file" in out
    assert "Not rewritten: Python sources" in out
    assert "without --dry-run" in out


@pytest.mark.unit
def test_dirty_tree_blocks(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_key_map_cli

    ws = _workspace(tmp_path)
    (ws / "stray.txt").write_text("x")
    code = run_key_map_cli(map_path=tmp_path / "map.toml", workspace_root=ws)

    assert code == 1
    assert "not clean" in capsys.readouterr().out


@pytest.mark.unit
def test_apply_never_prompts(tmp_path):
    from haywire_studio.packaging.rename import run_key_map_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", side_effect=AssertionError("must not prompt")):
        code = run_key_map_cli(map_path=tmp_path / "map.toml", workspace_root=ws)

    assert code == 0
    graph = (ws / "flows" / "g.haywire").read_text()
    assert '"registry_key": "haybale-core:node:BeginPlayNode"' not in graph


@pytest.mark.unit
@pytest.mark.parametrize("ascii_only", [True, False])
def test_apply_then_inverse_map_is_byte_identical(tmp_path, ascii_only):
    """Every value the map doesn't own survives, the file's own escaping included."""
    import tomllib

    from haywire_studio.packaging.rename import run_key_map_cli

    ws = _workspace(tmp_path, ascii_only=ascii_only)
    graph = ws / "flows" / "g.haywire"
    seed = graph.read_bytes()

    assert run_key_map_cli(map_path=tmp_path / "map.toml", workspace_root=ws) == 0
    assert '"registry_key": "haybale-core:node:BeginPlayNode"' not in graph.read_text()
    assert (ws / "flows" / "untouched.haywire").read_text().startswith('{"graph_id"')
    subprocess.run(["git", "commit", "-qam", "applied"], cwd=ws, check=True)

    inverse = []
    for entry in tomllib.loads(MAP)["rename"]:
        inverse += ["[[rename]]", f'old = "{entry["new"]}"', f'new = "{entry["old"]}"']
        if "old_module" in entry:
            inverse += [f'old_module = "{entry["new_module"]}"', f'new_module = "{entry["old_module"]}"']
    (tmp_path / "inverse.toml").write_text("\n".join(inverse) + "\n")
    assert run_key_map_cli(map_path=tmp_path / "inverse.toml", workspace_root=ws) == 0

    assert graph.read_bytes() == seed


@pytest.mark.unit
def test_verify_resolves_after_apply_once_the_new_keys_exist(tmp_path):
    from haywire_studio.packaging.rename import run_key_map_cli
    from haywire_studio.packaging.verify import collect_keys, run_verify_cli

    ws = _workspace(tmp_path)
    renames = _renames(tmp_path)
    olds = {rename.old for rename in renames}
    present = set(collect_keys(json.loads((ws / "flows" / "g.haywire").read_text())))
    present |= {"haybale-image:type:IMAGE_RGBA"}
    # The installed registry after the renames: every new key, no old one.
    known = (present - olds) | {rename.new for rename in renames}

    assert run_verify_cli(workspace_root=ws, resolver=lambda key: key in known) == 1
    assert run_key_map_cli(map_path=tmp_path / "map.toml", workspace_root=ws) == 0
    assert run_verify_cli(workspace_root=ws, resolver=lambda key: key in known) == 0


def _parse(*argv: str) -> argparse.Namespace:
    from haywire_studio.cli import rename

    parser = argparse.ArgumentParser()
    rename.register(parser.add_subparsers())
    return parser.parse_args(["rename", *argv])


@pytest.mark.unit
def test_cli_map_routes_to_key_map_mode(tmp_path):
    args = _parse("--map", str(tmp_path / "map.toml"), "--dry-run", "--verbose")
    with patch("haywire_studio.packaging.rename.run_key_map_cli", return_value=0) as run:
        assert args.handler(args) == 0

    kwargs = run.call_args.kwargs
    assert kwargs["map_path"] == tmp_path / "map.toml"
    assert kwargs["dry_run"]
    assert kwargs["verbose"]


@pytest.mark.unit
@pytest.mark.parametrize("flag", ["--apply", "--yes"])
def test_cli_no_longer_takes_apply_or_yes(flag):
    with pytest.raises(SystemExit):
        _parse("--map", "m.toml", flag)


@pytest.mark.unit
@pytest.mark.parametrize("argv", [("hay-a", "hay-b", "--map", "m.toml"), ("hay-a",), ()])
def test_cli_rejects_mixed_or_incomplete_arguments(argv, capsys):
    args = _parse(*argv)
    assert args.handler(args) == 2
    assert "--map FILE" in capsys.readouterr().out
