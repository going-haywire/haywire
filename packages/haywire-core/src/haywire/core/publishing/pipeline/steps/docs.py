"""Step 4 — regenerate docs."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from haywire.core.publishing.git import git, run_streaming
from haywire.core.publishing.pipeline.errors import DocsGenerationError
from haywire.core.publishing.pipeline.results import DocsResult

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline


def command(pipeline: "SharePipeline", json_path: Path | None = None) -> list[str]:
    """The argv for docs generation. ``--all``, always a subprocess.

    A subprocess because ``generate_docs()`` builds a SECOND library system
    whose ``initialize()`` calls ``set_global_injector()``, which in-studio
    repoints the live app's globals at a throwaway system (DI context is
    module-level globals, not ContextVar). ``extract_library`` also
    instantiates every node in a throwaway graph to read ports, which
    in-process would construct hardware-touching nodes inside the live app.
    See ``.insights/project_docs_gen_reentrancy.md``.

    ``--all`` rather than N per-library runs: one library-system load for
    the whole barn, and its root-relative filter naturally excludes
    site-packages installs and ``--dev`` mode's out-of-tree dev-repo
    libraries.

    ``--version`` carries ``pipeline.version`` across the subprocess
    boundary. Running after the bump is NOT by itself enough to get the new
    version into the docs: libraries typically declare
    ``version=importlib.metadata.version(...)``, which reads the installed
    dist-info, and an editable install's dist-info still holds the previous
    version until the environment is re-synced. Passing it explicitly makes
    the published version an input rather than something re-derived from
    ambient install state.
    """
    target = str(json_path) if json_path is not None else "<json-path>"
    # Bare "haywire": the console script installed by haywire-studio's
    # [project.scripts] entry point, resolved via PATH. The venv's bin/ is
    # on PATH whenever the studio itself is runnable, so this stays on the
    # same interpreter/virtualenv as the caller without hardcoding a path.
    argv = ["haywire", "docs", "--all", "--json", target]
    if pipeline.version is not None:
        argv += ["--version", pipeline.version]
    return argv


async def apply(pipeline: "SharePipeline", on_output: Callable[[str], None] | None = None) -> DocsResult:
    """Regenerate every barn library's docs. Always runs — no yes/no gate.

    Must run AFTER the version bump: ``render_quickref`` embeds
    ``v{doc.version}``, and this step renders ``pipeline.version``, which
    step 3 sets. Generating first would publish a QUICKREF stating the
    previous version. See :func:`command` for why the ordering alone does
    not achieve that and the version is passed explicitly.

    Coverage gaps are read-only feedback and never fail the step; only a
    non-zero exit (a crash) raises :class:`DocsGenerationError`.
    """
    sink = on_output or (lambda _line: None)
    tmp_dir = Path(tempfile.mkdtemp(prefix="hw-share-docs-"))
    json_path = tmp_dir / "coverage.json"
    try:
        result = await run_streaming(
            command(pipeline, json_path),
            cwd=pipeline.repo_root,
            on_output=sink,
        )
        if not result.ok:
            raise DocsGenerationError(
                f"Docs generation failed (exit {result.returncode}). The output above shows what broke.",
                output=result.stdout or result.stderr,
            )

        coverage: dict[str, list[str]] = {}
        if json_path.is_file():
            try:
                coverage = json.loads(json_path.read_text())
            except json.JSONDecodeError as exc:
                raise DocsGenerationError(
                    f"Docs generation wrote an unreadable coverage report: {exc}",
                    output=result.stdout,
                ) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    written = write_set(pipeline)
    pipeline.record(written)
    return DocsResult(coverage=coverage, written=written, output=result.stdout)


def write_set(pipeline: "SharePipeline") -> list[Path]:
    """Doc files under ``barn/`` that now differ from HEAD.

    Read from ``git status --porcelain`` rather than predicted, because the
    generator's file set is data-dependent: it writes OVERVIEW/QUICKREF/
    README plus one file per component, and DELETES orphaned per-component
    docs when a component is renamed (generate.py:87). A deletion left out
    of the commit ships a stale doc.

    Scoped to ``barn/`` — only barn content reaches consumers, and sweeping
    up unrelated dirt is what makes a wizard commit untrustworthy.
    """
    status = git(["status", "--porcelain", "--", "barn"], cwd=pipeline.repo_root)
    if not status.ok:
        return []

    out: list[Path] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path_part = line[3:].strip()
        # Renames print "old -> new"; the new path is what to stage.
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip('"')
        path = pipeline.repo_root / path_part
        if path.suffix.lower() == ".md":
            out.append(path)
    return sorted(set(out))
