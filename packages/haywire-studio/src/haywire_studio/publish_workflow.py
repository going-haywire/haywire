"""The CI files ``haywire init`` writes so a tag push can publish to PyPI.

Two files: ``.github/workflows/publish.yml`` and the planner it calls,
``.github/publish_plan.py``. The workflow is always present. Its first job runs
the planner, which reads ``[tool.haywire.marketstall] distribute`` from the root
``pyproject.toml`` and ends the run green without publishing unless it is
``"pypi"``. A git-distributed project therefore carries the workflow at no cost
and switches to PyPI by changing one line.

The build and publish jobs run once per ``barn/*`` library. Each library is its
own PyPI project and needs its own pending publisher; all of them share the same
owner, repository, workflow name and environment.
"""

from __future__ import annotations

PLAN_SCRIPT_PATH = ".github/publish_plan.py"
WORKFLOW_PATH = ".github/workflows/publish.yml"

PLAN_SCRIPT = '''\
"""Decide what publish.yml does. Standard library only; reads the checked-out project.

Writes ``enabled`` and ``matrix`` to $GITHUB_OUTPUT. Exits 1, with a message, when
publishing was requested but the run cannot be trusted to publish the right thing.
"""

import json
import os
import pathlib
import sys
import tomllib


def emit(enabled, matrix):
    line = f"enabled={'true' if enabled else 'false'}\\nmatrix={json.dumps(matrix)}\\n"
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as handle:
            handle.write(line)
    print(line, end="")


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


root = pathlib.Path(".")
config = tomllib.loads((root / "pyproject.toml").read_text())
distribute = config.get("tool", {}).get("haywire", {}).get("marketstall", {}).get("distribute", "git")

if distribute != "pypi":
    print(f"distribute = {distribute!r}: nothing to publish to PyPI.")
    emit(False, [])
    sys.exit(0)

if os.environ.get("GITHUB_REF_TYPE") != "tag":
    fail("Publishing runs on a version tag only. Retry with: gh workflow run publish.yml --ref vX.Y.Z")

libraries = []
for directory in sorted((root / "barn").glob("*")):
    manifest = directory / "pyproject.toml"
    if directory.is_symlink() or not manifest.is_file():
        continue
    project = tomllib.loads(manifest.read_text())["project"]
    libraries.append({"dist": project["name"], "version": project["version"]})

if not libraries:
    fail("No library under barn/ to publish.")

tag = os.environ.get("GITHUB_REF_NAME", "")
wrong = [item for item in libraries if tag != f"v{item['version']}"]
if wrong:
    names = ", ".join(f"{item['dist']} {item['version']}" for item in wrong)
    fail(f"Tag {tag} does not match the committed version of: {names}. Nothing was uploaded.")

emit(True, libraries)
'''

WORKFLOW = """\
name: Publish

# Publishes every barn/* library to PyPI on a version tag, when the root
# pyproject.toml declares  [tool.haywire.marketstall] distribute = "pypi".
# With any other value the run ends green without publishing.
# To retry a failed run: gh workflow run publish.yml --ref vX.Y.Z

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:

env:
  PYTHON_VERSION: '3.12'

jobs:
  guard:
    name: Plan
    runs-on: ubuntu-latest
    outputs:
      enabled: ${{ steps.plan.outputs.enabled }}
      matrix: ${{ steps.plan.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - name: Decide what to publish
        id: plan
        run: python3 .github/publish_plan.py

  build:
    name: Build ${{ matrix.lib.dist }}
    needs: guard
    if: needs.guard.outputs.enabled == 'true'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        lib: ${{ fromJSON(needs.guard.outputs.matrix) }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv python install ${{ env.PYTHON_VERSION }}
      - run: uv sync --frozen
      - name: Run tests
        if: hashFiles('tests/**') != ''
        run: uv run --frozen pytest -q
      - name: Build wheel and sdist
        run: |
          rm -rf dist/
          uv build --package ${{ matrix.lib.dist }}
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.lib.dist }}
          path: dist/
          if-no-files-found: error

  publish:
    name: Publish ${{ matrix.lib.dist }}
    needs: [guard, build]
    if: needs.guard.outputs.enabled == 'true'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        lib: ${{ fromJSON(needs.guard.outputs.matrix) }}
    environment:
      name: pypi
      url: https://pypi.org/project/${{ matrix.lib.dist }}/
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist-${{ matrix.lib.dist }}
          path: dist/
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          skip-existing: true
"""


def render_publish_workflow() -> str:
    """Return the text of ``.github/workflows/publish.yml``."""
    return WORKFLOW


def render_publish_plan() -> str:
    """Return the text of ``.github/publish_plan.py``, the planner the workflow's first job runs."""
    return PLAN_SCRIPT
