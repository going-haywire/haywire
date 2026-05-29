"""Audit declared vs. imported dependencies for every haywire package.

Wraps `deptry` and runs it once per package listed in
[tool.haywire.release] (pip_publish_order + git_publish_order + lockstep_unpublished). Because the
monorepo's packages import each other by *module* name (e.g. `haywire`) while
declaring each other by *distribution* name (e.g. `haywire-core`), a
package-module-name map is supplied so inter-package deps are not mis-flagged.

deptry error codes:
  DEP001  imported but not installed (a real problem)
  DEP002  declared but never imported (removable / unused)
  DEP003  imported but only transitively available (should be declared)

Exit code is always 0: this is a *report*, not a gate. The release flow runs
it for information; the operator decides what to act on. Run directly for an
ad-hoc audit:

    uv run python scripts/check_deps.py            # all packages
    uv run python scripts/check_deps.py haywire-core   # one package
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bump_version import locate_packages, read_release_config  # noqa: E402

# Distributions whose deptry "unused"/"transitive" findings are known false
# positives or deliberate, keyed by package -> set of module names to ignore.
# - attrs: transitive of cattrs; the pin in haywire-core is intentional.
# - visiongraph: declared as visiongraph[all]; deptry under-detects extras.
KNOWN_OK: dict[str, set[str]] = {
    "haywire-core": {"attrs"},
    "haybale-visiongraph": {"visiongraph"},
}


def _module_name(pyproject_path: Path) -> tuple[str, Path]:
    """Return (import_module_name, module_dir) from the wheel target config."""
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    pkgs = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    if not pkgs:
        raise SystemExit(f"no wheel packages declared in {pyproject_path}")
    rel = pkgs[0]  # e.g. "src/haywire" or "haybale_core"
    module_dir = pyproject_path.parent / rel
    module = Path(rel).name  # "haywire", "haywire_studio", "haybale_core"
    return module, module_dir


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent / "pyproject.toml"
    cfg = read_release_config(root)
    located = locate_packages(root, cfg)

    only = set(argv) if argv else None

    # Build the dist -> module map across ALL packages so inter-package
    # imports resolve regardless of which subset we scan.
    name_map = {name: _module_name(p)[0] for name, p in located.items()}
    map_arg = ",".join(f"{k}={v}" for k, v in name_map.items())

    any_findings = False
    for name in cfg.all_packages:
        if only and name not in only:
            continue
        pyproject = located[name]
        module, module_dir = _module_name(pyproject)
        result = subprocess.run(
            [
                "deptry",
                str(module_dir),
                "--package-module-name-map",
                map_arg,
                "--json-output",
                "/tmp/_haywire_deptry.json",
            ],
            cwd=pyproject.parent,
            capture_output=True,
            text=True,
        )
        try:
            findings = json.loads(Path("/tmp/_haywire_deptry.json").read_text())
        except (OSError, json.JSONDecodeError):
            print(f"  {name}: deptry failed\n{result.stderr}", file=sys.stderr)
            continue

        ignore = KNOWN_OK.get(name, set()) | {module}  # self-module is never a real finding
        unused = sorted({f["module"] for f in findings if f["error"]["code"] == "DEP002"} - ignore)
        missing = sorted({f["module"] for f in findings if f["error"]["code"] == "DEP003"} - ignore)
        notfound = sorted({f["module"] for f in findings if f["error"]["code"] == "DEP001"} - ignore)

        if unused or missing or notfound:
            any_findings = True
            print(f"### {name}")
            if notfound:
                print(f"  NOT INSTALLED (DEP001): {', '.join(notfound)}")
            if missing:
                print(f"  MISSING — imported, declare it (DEP003): {', '.join(missing)}")
            if unused:
                print(f"  UNUSED — consider removing (DEP002): {', '.join(unused)}")
        else:
            print(f"### {name}: clean")

    if not any_findings:
        print("\nClean — no dependency findings.")
    else:
        print("\nReport only — review findings; nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
