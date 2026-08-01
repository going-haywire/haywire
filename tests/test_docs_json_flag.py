"""`haywire docs --json <path>` writes the coverage report to a file."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _run_main(argv: list[str]) -> None:
    """Invoke haywire's main() with a fake argv."""
    from haywire_studio.app import main

    with patch.object(sys, "argv", ["haywire", *argv]):
        main()


def test_json_flag_writes_the_coverage_map(tmp_path: Path) -> None:
    out = tmp_path / "coverage.json"

    with patch(
        "haywire_studio.docs_gen.generate.generate_all_docs",
        return_value={"beta": [], "alpha": ["node Foo: missing docstring"]},
    ):
        _run_main(["docs", "--all", "--json", str(out)])

    data = json.loads(out.read_text())
    assert data == {"beta": [], "alpha": ["node Foo: missing docstring"]}


def test_json_flag_creates_missing_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deeper" / "coverage.json"

    with patch("haywire_studio.docs_gen.generate.generate_all_docs", return_value={}):
        _run_main(["docs", "--all", "--json", str(out)])

    assert out.is_file()
    assert json.loads(out.read_text()) == {}


def test_coverage_gaps_still_exit_zero(tmp_path: Path) -> None:
    """A coverage gap is feedback, not a failure — the pipeline must not abort on it."""
    out = tmp_path / "coverage.json"

    with patch(
        "haywire_studio.docs_gen.generate.generate_all_docs",
        return_value={"alpha": ["gap"]},
    ):
        _run_main(["docs", "--all", "--json", str(out)])  # no SystemExit

    assert json.loads(out.read_text()) == {"alpha": ["gap"]}


def test_json_without_all_writes_a_single_entry_map(tmp_path: Path) -> None:
    """`--json` on the single-library form keys the map by the library path."""
    out = tmp_path / "coverage.json"
    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)

    with patch("haywire_studio.docs_gen.generate.generate_docs", return_value=["gap"]):
        _run_main(["docs", str(lib), "--json", str(out)])

    data = json.loads(out.read_text())
    assert list(data.values()) == [["gap"]]


def test_docs_help_documents_the_flag() -> None:
    result = subprocess.run(
        ["uv", "run", "haywire", "docs", "--help"],
        capture_output=True,
        text=True,
    )
    assert "--json" in result.stdout
