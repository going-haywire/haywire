"""`haywire docs --json <path>` writes the coverage report to a file."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.packaging.docs import generate as docs_generate

pytestmark = pytest.mark.unit


def _run_main(argv: list[str]) -> int:
    """Invoke haywire's main() with a fake argv; returns the process exit code.

    Every subcommand exits through ``SystemExit(<handler's return>)``, so a
    successful run raises ``SystemExit(0)`` rather than returning.
    """
    from haywire_studio.app import main

    with patch.object(sys, "argv", ["haywire", *argv]):
        with pytest.raises(SystemExit) as excinfo:
            main()
    return int(excinfo.value.code or 0)


def test_json_flag_writes_the_coverage_map(tmp_path: Path) -> None:
    out = tmp_path / "coverage.json"

    with patch.object(
        docs_generate,
        "generate_all_docs",
        return_value={"beta": [], "alpha": ["node Foo: missing docstring"]},
    ):
        _run_main(["docs", "--all", "--json", str(out)])

    data = json.loads(out.read_text())
    assert data == {"beta": [], "alpha": ["node Foo: missing docstring"]}


def test_json_flag_creates_missing_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deeper" / "coverage.json"

    with patch.object(docs_generate, "generate_all_docs", return_value={}):
        _run_main(["docs", "--all", "--json", str(out)])

    assert out.is_file()
    assert json.loads(out.read_text()) == {}


def test_coverage_gaps_still_exit_zero(tmp_path: Path) -> None:
    """A coverage gap is feedback, not a failure — the pipeline must not abort on it."""
    out = tmp_path / "coverage.json"

    with patch.object(docs_generate, "generate_all_docs", return_value={"alpha": ["gap"]}):
        assert _run_main(["docs", "--all", "--json", str(out)]) == 0

    assert json.loads(out.read_text()) == {"alpha": ["gap"]}


def test_json_without_all_writes_a_single_entry_map(tmp_path: Path) -> None:
    """`--json` on the single-library form keys the map by the library path."""
    out = tmp_path / "coverage.json"
    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)

    with patch.object(docs_generate, "generate_docs", return_value=["gap"]):
        _run_main(["docs", str(lib), "--json", str(out)])

    data = json.loads(out.read_text())
    assert list(data.values()) == [["gap"]]


def test_all_form_reports_each_library_and_a_total(capsys: pytest.CaptureFixture[str]) -> None:
    """Characterizes the `--all` stdout report ahead of its extraction into cli/docs.py.

    Libraries are listed in sorted order, each marked clean or with its gap
    count, every gap line printed beneath it, and a total printed last.
    """
    with patch.object(
        docs_generate,
        "generate_all_docs",
        return_value={"beta": [], "alpha": ["node Foo: missing docstring"]},
    ):
        _run_main(["docs", "--all"])

    out = capsys.readouterr().out
    assert "Generated docs for 2 libraries." in out
    assert out.index("• alpha") < out.index("• beta"), "libraries must be sorted"
    assert "• alpha: 1 coverage gap(s)" in out
    assert "- node Foo: missing docstring" in out
    assert "• beta: clean" in out
    assert "Total coverage gaps: 1." in out


def test_single_form_reports_gaps_then_falls_silent_when_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The single-library form prints a gap list, or a clean confirmation."""
    with patch.object(docs_generate, "generate_docs", return_value=["gap one"]):
        _run_main(["docs", "somewhere"])
    out = capsys.readouterr().out
    assert "Documentation coverage gaps:" in out
    assert "- gap one" in out

    with patch.object(docs_generate, "generate_docs", return_value=[]):
        _run_main(["docs", "somewhere"])
    assert "Docs generated. No coverage gaps." in capsys.readouterr().out


def test_docs_help_documents_the_flag() -> None:
    result = subprocess.run(
        ["uv", "run", "haywire", "docs", "--help"],
        capture_output=True,
        text=True,
    )
    assert "--json" in result.stdout
