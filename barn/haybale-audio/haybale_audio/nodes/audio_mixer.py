"""Audio Mixer — sums several audio sources into one block per tick of a clock."""

import logging
import threading
import time

from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting
from haywire.core.types import PortOrigin

from haybale_audio.dsp.buffer import PullBuffer
from haybale_audio.dsp.mix import mix
from haybale_audio.emitter import set_status
from haybale_audio.value import AudioBlock

logger = logging.getLogger(__name__)

_PREFIX = "in_"
#: Blocks an input holds between two ticks; about 1 s of 256-frame blocks at 48 kHz.
_INPUT_BLOCKS = 192
#: A wait between two ticks longer than this is logged.
LONG_WAIT = 0.05
#: Seconds between status updates; one per tick would flood the UI.
STATUS_INTERVAL = 0.5


class MixerSettings(NodeSettings):
    """How each input is buffered. Applies on the next start."""

    prefill = setting[INT](
        8,
        min=1,
        max=64,
        label="Prefill",
        category="Mixer",
        description="Blocks an input queues before it is mixed. More blocks ride out longer stalls.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Audio Mixer",
    description="Sums several audio sources into one block per clock tick",
    menu="audio/mix",
    search_tags=["audio", "mixer", "mix", "sum", "gain", "mute", "combine", "bus"],
    node_type=NodeType.CONTROL,
)
class AudioMixerNode(BaseNode):
    """Mixes live sources that run on their own flows. Each source has its own input: connect its audio
    output to the open input at the bottom and it gets a `Gain` and a `Mute`; a new open input appears
    below.

    An input collects every block its source delivers, at the source's own pace, until the next tick.
    Wire an Audio Clock's Audio Event `Block Ready` to `Tick`. `Tick` is the moment to mix one block:
    each tick takes what every input collected and mixes one block per input. The block that triggered
    the tick sets the sample rate and block size of the output; it is not mixed in. The sources are the
    numbered inputs. Inputs at another sample rate or block size are converted, and a source clock that
    differs slightly from the tick clock is absorbed.

    An input is mixed once its prefill is queued, and again after a stall; until then it is silent. The
    sum is not limited, so loud sources can exceed ±1; the output has the most channels of any input, and
    a mono input plays on all of them. An input holds 192 blocks between two ticks (about a second of
    256-sample blocks at 48 kHz); when the ticks stop for longer, the oldest blocks are dropped and the
    status counts them.

    Inputs:
        tick: Mix one block (wire it to the clock's Block Ready); the triggering block sets the output
        in_N: An input's audio, collected until the next tick
        gain_N / mute_N: An input's level and mute

    Outputs:
        next: Control flow after a block is mixed
        mixed: The mixed block
    """

    mixer = bag(MixerSettings)

    def init(self) -> None:
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.exec_audio import EXEC_AUDIO

        self.add(EXEC_AUDIO.as_inlet("tick", label="Tick"))
        self.add(ADD[AUDIO].as_inlet(id=f"{_PREFIX}0", label="In 0", on_connect="hb_resolve"))
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC_AUDIO.as_outlet("next", label="Next"))
        self.add(AUDIO.as_outlet("mixed", label="Mixed"))

    def post_init(self) -> None:
        self.hb_lock = threading.Lock()
        self.hb_buffers: dict[int, PullBuffer] = {}
        self.hb_status_at = 0.0
        self.hb_tick_at = 0.0
        self.hb_started = 0.0  # when the first tick came; log lines show the time since
        self.hb_tick_gap = 0.0  # longest wait between two ticks, in seconds
        self.hb_dropped = 0  # blocks the inputs dropped since the start
        self._upgrade_saved_inputs()

    def hb_resolve(self, port, edge_wrapper) -> None:
        """Turn the open input into an audio input with its pins and add a new open one below it."""
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            return  # already resolved; the callback fires again whenever the edge is re-linked

        index = int(port.id[len(_PREFIX) :])
        self._collecting_input(index)
        self.add(FLOAT.as_inlet(f"gain_{index}", label=f"Gain {index}", default=1.0))
        self.add(BOOL.as_inlet(f"mute_{index}", label=f"Mute {index}", default=False))
        # Indices are never reused: a port id is part of the id of every edge attached to it.
        next_index = max(self._indices()) + 1
        self.add(
            ADD[AUDIO].as_inlet(
                id=f"{_PREFIX}{next_index}", label=f"In {next_index}", on_connect="hb_resolve"
            )
        )

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_reset()

    def on_teardown(self) -> None:
        self.hb_reset()

    def worker(self, context: ExecutionContext) -> str | None:
        if context.control_pin == "tick":
            return self.hb_tick(self._trigger_block(context))
        return None

    def hb_tick(self, clock: AudioBlock) -> str:
        rate, frames = clock.sample_rate, clock.frames
        now = time.monotonic()
        with self.hb_lock:
            if self.hb_tick_at:
                self.hb_tick_gap = max(self.hb_tick_gap, now - self.hb_tick_at)
                if now - self.hb_tick_at > LONG_WAIT:
                    logger.warning(
                        "Audio Mixer: waited %.0f ms for a tick at %.1f s",
                        (now - self.hb_tick_at) * 1000,
                        now - self.hb_started,
                    )
            if not self.hb_tick_at:
                self.hb_started = now
            self.hb_tick_at = now
            for index in self._inputs():
                batch = self.drain(f"{_PREFIX}{index}")
                self.hb_dropped += batch.dropped
                for block in batch:
                    self._buffer(index, block, rate).write(block)
            buffers = dict(self.hb_buffers)
        pulled = {index: buf.read(frames) for index, buf in buffers.items()}
        channels = max((b.channels for b in buffers.values()), default=clock.channels)
        parts = [
            (data, self._gain(index))
            for index, data in pulled.items()
            if data is not None and not self.value(f"mute_{index}")
        ]
        self.out("mixed", AudioBlock(mix(parts, channels, frames), rate))
        now = time.monotonic()
        if now - self.hb_status_at >= STATUS_INTERVAL:
            self.hb_status_at = now
            playing = sum(1 for b in buffers.values() if b.playing)
            stalls = sum(b.restarts for b in buffers.values())
            set_status(
                self,
                f"{playing} of {len(buffers)} inputs playing, stalls {stalls}, "
                f"dropped {self.hb_dropped}, longest wait for a tick {self.hb_tick_gap * 1000:.0f} ms",
            )
        return "next"

    def hb_reset(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        lock = getattr(self, "hb_lock", None)
        if lock is None:
            return
        with lock:
            for index in self._inputs():
                self.drain(f"{_PREFIX}{index}")  # blocks from before the stop must not play after a start
            self.hb_buffers.clear()
            self.hb_tick_at = self.hb_started = 0.0
            self.hb_tick_gap = 0.0
            self.hb_dropped = 0

    def _buffer(self, index: int, first: AudioBlock, rate: int) -> PullBuffer:
        """Return the input's buffer at the output *rate*, created from its first block.

        Call with ``hb_lock`` held.
        """
        buffer = self.hb_buffers.get(index)
        if buffer is None:
            buffer = PullBuffer(
                rate,
                first.channels,
                max(1, round(first.frames * rate / first.sample_rate)),
                int(self.mixer.prefill),
            )
            self.hb_buffers[index] = buffer
        return buffer

    @staticmethod
    def _trigger_block(context: ExecutionContext) -> AudioBlock:
        """Return the block of the audio event that started this flow."""
        payload = context.trigger.payload if context.trigger else None
        block = payload.get("audio") if isinstance(payload, dict) else None
        if not isinstance(block, AudioBlock):
            raise ValueError("tick needs a flow started by an audio event")
        return block

    def _collecting_input(self, index: int) -> None:
        """Make input *index* one that collects blocks until the next tick, removing its `Write` pin."""
        from haybale_core.types import DRAIN
        from haybale_audio.types.audio import AUDIO

        port_id = f"{_PREFIX}{index}"
        with self.rejig(include=[port_id, f"write_{index}"]):
            self.add(
                DRAIN[AUDIO].as_inlet(
                    id=port_id,
                    label=f"In {index}",
                    origin=PortOrigin.RESOLVED,
                    default={"max_len": _INPUT_BLOCKS},
                )
            )

    def _upgrade_saved_inputs(self) -> None:
        """Rebuild saved inputs that are plain audio inputs with `Write` pins, or hold another size."""
        for port in list(self.get_all_ports()):
            if not (port.id.startswith(_PREFIX) and port.origin is PortOrigin.RESOLVED):
                continue
            if not port.queues_values or getattr(port.data, "max_len", None) != _INPUT_BLOCKS:
                self._collecting_input(int(port.id[len(_PREFIX) :]))

    def _gain(self, index: int) -> float:
        gain = self.value(f"gain_{index}")
        return 1.0 if gain is None else float(gain)

    def _indices(self) -> list[int]:
        return [int(p.id[len(_PREFIX) :]) for p in self.get_all_ports() if p.id.startswith(_PREFIX)]

    def _inputs(self) -> list[int]:
        """Return the indices of the connected inputs: those that collect blocks."""
        return [
            int(p.id[len(_PREFIX) :])
            for p in self.get_all_ports()
            if p.id.startswith(_PREFIX) and p.queues_values
        ]
