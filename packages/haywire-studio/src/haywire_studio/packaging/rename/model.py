"""Pure data describing a planned rename. No filesystem, no side effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Occurrence:
    """One textual site referencing the old name."""

    path: Path
    line: int
    text: str


@dataclass
class FileChange:
    """A single file the rename will rewrite."""

    path: Path
    kind: str  # "graph" | "python" | "toml"
    count: int
    occurrences: list[Occurrence] = field(default_factory=list)


@dataclass(frozen=True)
class Blocker:
    """A condition that stops the rename. Carries the command that fixes it."""

    message: str
    remedy: str = ""


@dataclass(frozen=True)
class Warning_:
    """Advisory: the rename proceeds, but the user should read this."""

    message: str
    remedy: str = ""


@dataclass
class RenamePlan:
    """Everything the rename will do, computed without writing anything."""

    old_dist: str
    new_dist: str
    old_module: str
    new_module: str
    workspace_root: Path
    old_lib_dir: Path
    new_lib_dir: Path
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)
    graph_changes: list[FileChange] = field(default_factory=list)
    python_changes: list[FileChange] = field(default_factory=list)
    toml_changes: list[FileChange] = field(default_factory=list)
    dependent_changes: list[FileChange] = field(default_factory=list)
    unrecognized: list[Occurrence] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def total_changes(self) -> int:
        return sum(
            c.count
            for c in (
                *self.graph_changes,
                *self.python_changes,
                *self.toml_changes,
                *self.dependent_changes,
            )
        )
