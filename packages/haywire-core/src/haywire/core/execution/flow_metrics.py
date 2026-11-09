"""Flow meter maths: turns counter snapshots of the running Flows into load, drop rate and severity.

A ``FlowSnapshot`` is a cheap read of one Flow's counters. ``FlowMeterSampler`` compares each snapshot
with the previous one to get the figures a meter shows, and orders the Flows by severity within their
execution groups.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """How badly a Flow is keeping up. Higher is worse."""

    OK = 0
    WARN = 1
    ALERT = 2


@dataclass(frozen=True)
class FlowSnapshot:
    """The counters of one Flow at one moment. ``frames``, ``busy_ns`` and ``dropped`` only grow."""

    flow_id: str
    entry_node_id: str
    group_id: str
    drop_mode: bool
    queue_depth: int
    queue_max: int
    frames: int
    busy_ns: int
    dropped: int
    executing: bool
    taken_at: float
    """Seconds on a monotonic clock."""


@dataclass(frozen=True)
class Thresholds:
    """Where a figure turns a Flow amber (``WARN``) or red (``ALERT``)."""

    load_warn: float = 0.7
    load_alert: float = 0.9
    fill_warn: float = 0.5
    fill_alert: float = 0.8
    drop_rate_warn: float = 0.1
    drop_memory_s: float = 5.0
    """How long a drop keeps a BLOCK-mode Flow red."""


@dataclass(frozen=True)
class FlowReading:
    """What a meter shows for one Flow."""

    flow_id: str
    entry_node_id: str
    group_id: str
    drop_mode: bool
    load: float
    """Share of the sampling window the Flow's frames ran, from 0 to 1."""
    group_load: float
    """Share of the window the Flow's execution group ran any frame, from 0 to 1."""
    fill: float
    """Queue depth over its maximum."""
    frame_rate: float
    """Frames completed per second."""
    drop_rate: float
    """Share of the window's Triggers that were dropped, from 0 to 1."""
    recently_dropped: bool
    dropped_total: int
    queue_depth: int
    queue_max: int
    severity: Severity


@dataclass(frozen=True)
class GroupReading:
    """The Flows of one execution group, worst first."""

    group_id: str
    load: float
    severity: Severity
    flows: tuple[FlowReading, ...]


@dataclass(frozen=True)
class MeterReading:
    """All Flows of a graph, grouped, with the worst group first."""

    groups: tuple[GroupReading, ...]

    @property
    def flows(self) -> tuple[FlowReading, ...]:
        """Every Flow, in display order."""
        return tuple(flow for group in self.groups for flow in group.flows)

    @property
    def worst(self) -> FlowReading | None:
        """The Flow to show when only one bar fits, or ``None`` when no Flow runs."""
        return self.groups[0].flows[0] if self.groups else None


class FlowMeterSampler:
    """Turns successive snapshots of a graph's Flows into a ``MeterReading``.

    Each ``update`` compares the snapshots with the previous call's. The first call after a Flow
    appears, or after its counters restart, reports it as idle.

    A Flow is amber or red by the larger of its own load and its group's load. A BLOCK-mode Flow is
    also judged by its queue fill and is red for ``drop_memory_s`` seconds after a drop. A DROP-mode
    Flow drops by design, so only a drop rate above the threshold turns it amber, and its queue fill
    is not judged.

    Example::

        sampler = FlowMeterSampler()
        sampler.update(interpreter.flow_metrics())   # primes the sampler
        reading = sampler.update(interpreter.flow_metrics())
        if reading.worst is not None:
            print(reading.worst.severity, reading.worst.load)
    """

    def __init__(self, thresholds: Thresholds | None = None) -> None:
        self.thresholds = thresholds or Thresholds()
        self._previous: dict[str, FlowSnapshot] = {}
        self._last_drop_at: dict[str, float] = {}

    def update(self, snapshots: Sequence[FlowSnapshot]) -> MeterReading:
        """Return the reading for ``snapshots``, the current state of every running Flow."""
        figures = [self._figures(s, self._previous.get(s.flow_id)) for s in snapshots]
        self._previous = {s.flow_id: s for s in snapshots}
        self._last_drop_at = {k: v for k, v in self._last_drop_at.items() if k in self._previous}

        by_group: dict[str, list[tuple[FlowSnapshot, dict]]] = {}
        for snapshot, fig in zip(snapshots, figures, strict=True):
            by_group.setdefault(snapshot.group_id, []).append((snapshot, fig))

        groups = []
        for group_id, members in by_group.items():
            group_load = min(1.0, sum(fig["load"] for _, fig in members))
            flows = [self._reading(s, fig, group_load) for s, fig in members]
            flows.sort(key=lambda f: (-f.severity, -f.load, f.flow_id))
            groups.append(GroupReading(group_id, group_load, max(f.severity for f in flows), tuple(flows)))
        groups.sort(key=lambda g: (-g.severity, -g.load, g.group_id))
        return MeterReading(tuple(groups))

    def _figures(self, now: FlowSnapshot, before: FlowSnapshot | None) -> dict:
        fill = now.queue_depth / now.queue_max if now.queue_max else 0.0
        if before is None or now.frames < before.frames or now.taken_at <= before.taken_at:
            return {"load": 0.0, "fill": fill, "frame_rate": 0.0, "drop_rate": 0.0, "dropped_now": False}
        window = now.taken_at - before.taken_at
        frames = now.frames - before.frames
        dropped = max(0, now.dropped - before.dropped)
        load = min(1.0, (now.busy_ns - before.busy_ns) / 1e9 / window)
        if now.executing and frames == 0:
            load = 1.0  # one frame spans the whole window and has not added its time yet
        arrivals = frames + dropped + max(0, now.queue_depth - before.queue_depth)
        if dropped:
            self._last_drop_at[now.flow_id] = now.taken_at
        return {
            "load": load,
            "fill": fill,
            "frame_rate": frames / window,
            "drop_rate": dropped / arrivals if arrivals else 0.0,
            "dropped_now": dropped > 0,
        }

    def _reading(self, s: FlowSnapshot, fig: dict, group_load: float) -> FlowReading:
        t = self.thresholds
        last_drop = self._last_drop_at.get(s.flow_id)
        recently = last_drop is not None and s.taken_at - last_drop < t.drop_memory_s
        severity = _grade(max(fig["load"], group_load), t.load_warn, t.load_alert)
        if s.drop_mode:
            if fig["drop_rate"] >= t.drop_rate_warn:
                severity = max(severity, Severity.WARN)
        else:
            severity = max(severity, _grade(fig["fill"], t.fill_warn, t.fill_alert))
            if recently:
                severity = Severity.ALERT
        return FlowReading(
            flow_id=s.flow_id,
            entry_node_id=s.entry_node_id,
            group_id=s.group_id,
            drop_mode=s.drop_mode,
            load=fig["load"],
            group_load=group_load,
            fill=fig["fill"],
            frame_rate=fig["frame_rate"],
            drop_rate=fig["drop_rate"],
            recently_dropped=recently,
            dropped_total=s.dropped,
            queue_depth=s.queue_depth,
            queue_max=s.queue_max,
            severity=severity,
        )


def _grade(value: float, warn: float, alert: float) -> Severity:
    if value >= alert:
        return Severity.ALERT
    if value >= warn:
        return Severity.WARN
    return Severity.OK
