"""ProgressDemoNode — two progress bars, an overall one and one per job, driven from the worker.

Exists to show ``ProgressSettings`` working on a real card: each run processes a
number of jobs (the Progress bar fills), every job runs a number of steps (the
Job bar fills and resets per job), and a final blocking stage makes the Progress
bar sweep. The work is simulated with ``time.sleep``.
"""

import time

from haywire.barn.builtin.progress import ProgressSettings, progress_field
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import bag


class DemoProgress(ProgressSettings):
    """The demo's two bars: the whole run, and the current job."""

    main = progress_field("Progress")
    job = progress_field("Job", order=1)


@node(
    label="Progress Demo",
    description="Simulates slow work and shows its progress on the card: overall, per job, final stage.",
    search_tags=["progress", "busy", "bar", "example"],
    menu="examples/progress",
    node_type=NodeType.CONTROL,
)
class ProgressDemoNode(BaseNode):
    """Simulates slow work and shows its progress on the card.

    Trigger `exec` to run. The Progress bar fills as the jobs pass, the Job bar
    fills with the steps of the current job, and the closing "finishing" stage
    sweeps the Progress bar because its length is unknown. `done` fires when
    the run ends and `processed` gives the number of steps run.
    """

    progress = bag(DemoProgress)

    def init(self):
        from haywire.barn.builtin.types import EXEC, FLOAT, INT

        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))

        self.add(INT.as_inlet("jobs", label="Jobs", default=4))
        self.add(INT.as_inlet("steps", label="Steps per job", default=20))
        self.add(FLOAT.as_inlet("step_ms", label="Step (ms)", default=40.0))

        self.add(INT.as_outlet("processed", label="Processed"))

    def worker(self, context: ExecutionContext) -> str | None:
        jobs = max(int(self.value("jobs")), 0)
        steps = max(int(self.value("steps")), 0)
        step_s = max(float(self.value("step_ms")), 0.0) / 1000.0

        processed = 0
        for job in self.progress.track("main", range(jobs), "processing"):
            for _step in self.progress.track("job", range(steps), f"job {job + 1} of {jobs}"):
                time.sleep(step_s)
                processed += 1

        # A stage of unknown length: the bar sweeps until the block ends.
        with self.progress.busy("main", "finishing"):
            time.sleep(step_s * steps / 2)

        self.out("processed", processed)
        return "done"
