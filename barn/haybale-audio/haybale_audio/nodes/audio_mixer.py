"""Audio Mixer — sums several audio sources into one block per tick of a clock."""

import threading
import time
from collections import deque

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

_PREFIX = "in_"
#: Blocks kept for an input that writes before the first tick fixes the output format.
_PENDING_BLOCKS = 32
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
    output to the open input at the bottom and it gets a `Write` pin, a `Gain` and a `Mute`; a new open
    input appears below.

    Wire each source's Audio Event Block Ready to its `Write` pin: the block is queued for that input.
    Wire an Audio Clock's Audio Event `Block Ready` to `Tick`. `Tick` is the moment to mix one block, so
    every tick mixes one block per input. The block that triggered the tick sets the sample rate and
    block size of the output; it is not mixed in. The sources are the numbered inputs. Inputs at another
    sample rate or block size are converted, and a source clock that differs slightly from the tick
    clock is absorbed.

    An input is mixed once its prefill is queued, and again after a stall; until then it is silent. The
    sum is not limited, so loud sources can exceed ±1; the output has the most channels of any input, and
    a mono input plays on all of them.

    Inputs:
        tick: Mix one block (wire it to the clock's Block Ready); the triggering block sets the output
        in_N / write_N: An input's audio and the pin that queues it
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
        self.hb_pending: dict[int, deque[AudioBlock]] = {}
        self.hb_format: tuple[int, int] | None = None  # sample rate and frames of the clock block
        self.hb_status_at = 0.0

    def hb_resolve(self, port, edge_wrapper) -> None:
        """Turn the open input into an audio input with its pins and add a new open one below it."""
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.exec_audio import EXEC_AUDIO

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            return  # already resolved; the callback fires again whenever the edge is re-linked

        index = int(port.id[len(_PREFIX) :])
        with self.rejig(include=[port.id]):
            self.add(AUDIO.as_inlet(id=port.id, label=f"In {index}", origin=PortOrigin.RESOLVED))
        self.add(EXEC_AUDIO.as_inlet(f"write_{index}", label=f"Write {index}"))
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
        pin = context.control_pin or ""
        if pin == "tick":
            return self.hb_tick(self._trigger_block(context))
        if pin.startswith("write_"):
            self.hb_write(int(pin[len("write_") :]))
        return None

    def hb_write(self, index: int) -> None:
        block = self.value(f"{_PREFIX}{index}")
        if not isinstance(block, AudioBlock):
            raise ValueError(f"write {index} needs an audio block on in {index}")
        with self.hb_lock:
            if self.hb_format is None:
                # The tick has not fixed the output format yet.
                self.hb_pending.setdefault(index, deque(maxlen=_PENDING_BLOCKS)).append(block)
                return
            self._buffer(index, block).write(block)

    def hb_tick(self, clock: AudioBlock) -> str:
        rate, frames = clock.sample_rate, clock.frames
        with self.hb_lock:
            self.hb_format = (rate, frames)
            for index, blocks in self.hb_pending.items():
                for block in blocks:
                    self._buffer(index, block).write(block)
            self.hb_pending.clear()
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
            set_status(self, f"{playing} of {len(buffers)} inputs playing, stalls {stalls}")
        return "next"

    def hb_reset(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        lock = getattr(self, "hb_lock", None)
        if lock is None:
            return
        with lock:
            self.hb_buffers.clear()
            self.hb_pending.clear()
            self.hb_format = None

    def _buffer(self, index: int, first: AudioBlock) -> PullBuffer:
        """Return the input's buffer, created from its first block. Call with ``hb_lock`` held."""
        buffer = self.hb_buffers.get(index)
        if buffer is None:
            assert self.hb_format is not None
            rate = self.hb_format[0]
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

    def _gain(self, index: int) -> float:
        gain = self.value(f"gain_{index}")
        return 1.0 if gain is None else float(gain)

    def _indices(self) -> list[int]:
        return [int(p.id[len(_PREFIX) :]) for p in self.get_all_ports() if p.id.startswith(_PREFIX)]
