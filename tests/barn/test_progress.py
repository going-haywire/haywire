"""ProgressSettings: bars written by ``busy()`` blocks and ``track()`` loops, idle again when one ends."""

from __future__ import annotations

from typing import Any, cast

import pytest

from haywire.barn.builtin import progress as progress_module
from haywire.barn.builtin.progress import ProgressSettings, progress_field
from haywire.barn.builtin.types import INT, PROGRESS
from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import setting
from haywire.core.types.enums import PortType

pytestmark = pytest.mark.unit


class _Bars(ProgressSettings):
    main = progress_field("Progress")
    sub = progress_field("Step")
    count = setting[INT](0)


def _settings() -> _Bars:
    return _Bars(registry=create_test_settings_registry())


class TestValue:
    def test_default_is_idle(self):
        value = PROGRESS()
        assert (value.active, value.fraction, value.label) == (False, None, "")

    def test_fraction_is_clamped(self):
        assert PROGRESS(active=True, fraction=1.7).fraction == 1.0
        assert PROGRESS(active=True, fraction=-0.2).fraction == 0.0

    def test_round_trips_through_dict(self):
        value = PROGRESS(active=True, fraction=0.25, label="tiles")
        assert PROGRESS.from_dict(value.to_dict()) == value

    def test_malformed_dict_becomes_idle(self):
        assert PROGRESS.from_dict({"fraction": "half"}) == PROGRESS()
        assert PROGRESS.from_dict(cast(Any, None)) == PROGRESS()


class TestBusy:
    def test_open_block_shows_busy_without_fraction(self):
        settings = _settings()
        with settings.busy("main", "inferring"):
            assert settings.main == PROGRESS(active=True, label="inferring")
            assert settings.sub == PROGRESS()

    def test_end_of_block_resets_to_idle_and_leaves_nothing_to_save(self):
        settings = _settings()
        with settings.busy("main", "inferring"):
            assert settings._is_locally_set("main")
        assert settings.main == PROGRESS()
        assert not settings._is_locally_set("main")
        assert settings._to_dict()["values"] == {}

    def test_exception_resets_to_idle_and_propagates(self):
        settings = _settings()
        with pytest.raises(ValueError, match="boom"):
            with settings.busy("main", "boom"):
                raise ValueError("boom")
        assert settings.main == PROGRESS()

    def test_step_reports_a_fraction(self):
        settings = _settings()
        with settings.busy("main", "tiles") as span:
            span.step(0.4)
            assert settings.main == PROGRESS(active=True, fraction=0.4, label="tiles")

    def test_step_drops_writes_closer_than_the_interval(self, monkeypatch):
        clock = [100.0]
        monkeypatch.setattr(progress_module.time, "monotonic", lambda: clock[0])
        settings = _settings()
        with settings.busy("main", "tiles") as span:
            span.step(0.1)
            span.step(0.2)
            assert settings.main.fraction == 0.1
            clock[0] += 2 * progress_module.STEP_INTERVAL_S
            span.step(0.3)
            assert settings.main.fraction == 0.3

    def test_new_label_always_writes(self, monkeypatch):
        monkeypatch.setattr(progress_module.time, "monotonic", lambda: 100.0)
        settings = _settings()
        with settings.busy("main", "download") as span:
            span.step(0.1)
            span.step(0.5, label="unpacking")
            assert settings.main == PROGRESS(active=True, fraction=0.5, label="unpacking")

    def test_blocks_on_different_bars_nest(self):
        settings = _settings()
        with settings.busy("main", "processing"):
            with settings.busy("sub", "loading"):
                assert settings.sub.active
            assert settings.main == PROGRESS(active=True, label="processing")
            assert settings.sub == PROGRESS()

    def test_inner_block_on_the_same_bar_resets_it(self):
        settings = _settings()
        with settings.busy("main", "outer"):
            with settings.busy("main", "inner"):
                pass
            assert settings.main == PROGRESS()

    @pytest.mark.parametrize("field", ["missing", "count"])
    def test_unknown_or_non_progress_field_is_refused(self, field):
        with pytest.raises(ValueError, match=field):
            _settings().busy(field)


class TestTrack:
    def test_yields_items_and_fills_by_share_passed(self, monkeypatch):
        clock = [0.0]

        def tick() -> float:
            clock[0] += 1.0
            return clock[0]

        monkeypatch.setattr(progress_module.time, "monotonic", tick)
        settings = _settings()
        seen = []
        for item in settings.track("main", ["a", "b", "c", "d"], "files"):
            seen.append((item, settings.main.fraction))
        assert seen == [("a", 0.0), ("b", 0.25), ("c", 0.5), ("d", 0.75)]
        assert settings.main == PROGRESS()

    def test_iterable_without_len_sweeps(self):
        settings = _settings()
        for _ in settings.track("main", iter([1, 2]), "stream"):
            assert settings.main == PROGRESS(active=True, label="stream")

    def test_total_gives_a_fraction_to_an_iterable_without_len(self):
        settings = _settings()
        for _ in settings.track("main", iter([1, 2]), "stream", total=4):
            assert settings.main.fraction == 0.0
            break

    def test_break_resets_to_idle(self):
        settings = _settings()
        for _ in settings.track("main", [1, 2, 3]):
            break
        assert settings.main == PROGRESS()

    def test_exception_resets_to_idle(self):
        settings = _settings()

        def run() -> None:
            for _ in settings.track("main", [1, 2, 3]):
                raise RuntimeError("stop")

        with pytest.raises(RuntimeError, match="stop"):
            run()
        assert settings.main == PROGRESS()

    def test_unknown_field_is_refused_at_the_call(self):
        with pytest.raises(ValueError, match="missing"):
            _settings().track("missing", [1])


class TestDeclaration:
    @pytest.mark.parametrize("name", ["busy", "track"])
    def test_reserved_field_name_is_refused(self, name):
        with pytest.raises(TypeError, match=name):
            type("_Clash", (ProgressSettings,), {name: progress_field()})

    def test_bars_show_on_the_card_by_default(self):
        settings = _settings()
        assert settings._get_promoted_direction("main") is PortType.CONFIG
        assert settings._get_promoted_direction("sub") is PortType.CONFIG


class _StubWrapper:
    graph = None
    state = None

    def mark_as_structuraly_dirty(self):
        pass


def test_node_gets_a_config_port_per_bar(library_system):
    from haywire.core.node import BaseNode, NodeType, node

    @node(label="Progress Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _Probe(BaseNode):
        class progress(ProgressSettings):
            main = progress_field("Progress")
            sub = progress_field("Step")

        def init(self):
            pass

    node_obj = cast(Any, _Probe)(node_id="p", wrapper=_StubWrapper())
    node_obj.init()
    node_obj._regenerate_promoted_ports()

    main, sub = node_obj.ports["progress.main"], node_obj.ports["progress.sub"]
    assert main.port_type is PortType.CONFIG
    assert sub.port_type is PortType.CONFIG
    with node_obj.progress.busy("main", "processing"):
        with node_obj.progress.busy("sub", "loading"):
            assert main.get_value().label == "processing"
            assert sub.get_value().label == "loading"
    assert main.get_value() == PROGRESS()
    assert sub.get_value() == PROGRESS()
