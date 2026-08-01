"""``haywire docs`` — generate deterministic docs for a haybale library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("docs", help="Generate deterministic docs for a haybale library")
    parser.add_argument(
        "library",
        nargs="?",
        default=None,
        help=(
            "Path to the library package root, or (with --all) the repo root to scan"
            " — default: current directory"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate docs for every in-repo library (barn/* + builtin) in one load",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        metavar="PATH",
        help="Write the coverage report to PATH as JSON ({library_id: [lines]}). "
        "A file sink rather than stdout, because a library-system boot prints "
        "freely to stdout and not all of it is ours.",
    )
    parser.set_defaults(handler=_run)


def _write_coverage_json(destination: str | None, coverage: dict[str, list[str]]) -> None:
    """Write *coverage* to *destination*, creating parent dirs. No-op when unset."""
    if destination is None:
        return
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(coverage, indent=2), encoding="utf-8")


def _run(args: argparse.Namespace) -> int:
    # Imported lazily: generating docs boots a whole second library system and
    # instantiates every node. Nothing should pay that cost by importing the CLI.
    if args.all:
        from haywire_studio.packaging.docs.generate import generate_all_docs

        results = generate_all_docs(args.library)
        total_gaps = sum(len(gaps) for gaps in results.values())
        print(f"Generated docs for {len(results)} libraries.")
        for lib_id in sorted(results):
            gaps = results[lib_id]
            marker = f"{len(gaps)} coverage gap(s)" if gaps else "clean"
            print(f"  • {lib_id}: {marker}")
            for line in gaps:
                print(f"      - {line}")
        print(f"Total coverage gaps: {total_gaps}.")
        _write_coverage_json(args.json, results)
        return 0

    from haywire_studio.packaging.docs.generate import generate_docs

    coverage = generate_docs(args.library)
    if coverage:
        print("Documentation coverage gaps:")
        for line in coverage:
            print(f"  - {line}")
    else:
        print("Docs generated. No coverage gaps.")
    # The single-library form has no library id to key by, so the path the
    # user named is the key. Keeps --json's shape identical for both forms.
    _write_coverage_json(args.json, {str(args.library or Path.cwd()): coverage})
    return 0
