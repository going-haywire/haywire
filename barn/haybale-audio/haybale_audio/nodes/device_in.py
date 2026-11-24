"""Device In — records a sound device's input as audio blocks."""

from __future__ import annotations

import time

from haybale_audio.emitter import STATUS_INTERVAL, BlockPump, deliver_to_subscribers, set_status
from haybale_audio.io.device import DeviceInput, input_device_names
from haybale_audio.value import AudioBlock
from haywire.api import (
    CHOICES,
    EXEC,
    INT,
    STRING,
    BaseNode,
    ExecutionContext,
    LabelWidget,
    NodeSettings,
    NodeType,
    Promotable,
    bag,
    node,
    setting,
)

_DEFAULT_DEVICE = "System default"
_DEVICE_RATE = "Device default"
_DEVICE_CHANNELS = "All device channels"


class DeviceInSettings(NodeSettings):
    """Where and how the sound is recorded. Applies on the next start."""

    device = setting[CHOICES](
        _DEFAULT_DEVICE,
        label="Device",
        category="Input",
        description="Input device to record from. The list is read when the node is shown.",
        widget_config={"options": lambda: [_DEFAULT_DEVICE, *input_device_names()]},
        promotable=Promotable.CONFIG,
    )
    channels = setting[CHOICES](
        _DEVICE_CHANNELS,
        label="Channels",
        category="Input",
        description="Channels to record. More than the device has records all of the device's.",
        widget_config={"options": [_DEVICE_CHANNELS, "1", "2"]},
        promotable=Promotable.CONFIG,
    )
    sample_rate = setting[CHOICES](
        _DEVICE_RATE,
        label="Sample Rate",
        category="Input",
        description="Samples per second. The device's own rate needs no conversion by the sound system.",
        widget_config={"options": [_DEVICE_RATE, "44100", "48000", "96000"]},
        promotable=Promotable.CONFIG,
    )
    block_size = setting[INT](
        256,
        min=16,
        max=8192,
        label="Block Size",
        category="Input",
        description="Samples per block. 256 at 48 kHz is a block every 5.3 ms.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Device In",
    description="Records a sound device's input as audio blocks",
    menu="audio/source",
    search_tags=["audio", "record", "microphone", "mic", "input", "device", "sound", "line in", "emit"],
    node_type=NodeType.CONTROL,
)
class DeviceInNode(BaseNode):
    """Records from an input device (a microphone, an audio interface) and delivers each block to
    every Audio Event listening, at the pace of the device's own clock.

    The status shows what the device really delivers: channels, sample rate, block size and its
    input latency. A device can impose its own block size: the status then shows the size asked
    for in brackets, and a Reblock node fixes the size where a node needs it.

    Two counters show lost audio. `lost` counts blocks dropped because the flow ran behind for
    more than half a second. `overflow` counts the times the device itself lost input because the
    program was busy too long.

    Wired to a Device Out, the two devices run on two clocks that differ slightly; Device Out
    absorbs the difference.

    Inputs:
        start / stop: Begin or end recording
        callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes

    Outputs:
        started / stopped: Control flow after the matching input
    """

    recording = bag(DeviceInSettings)

    def init(self) -> None:
        from haybale_audio.types.callback import AUDIO_CALLBACK
        from haybale_core.types import POOLED

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(
            POOLED[AUDIO_CALLBACK].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=LabelWidget.config()))
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self.hb_input: DeviceInput | None = None
        self.hb_pump: BlockPump | None = None
        self.hb_status_at = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_stop()

    def on_teardown(self) -> None:
        self.hb_stop()

    def worker(self, context: ExecutionContext) -> str | None:
        if context.control_pin == "start":
            return self.hb_start(context)
        if context.control_pin == "stop":
            self.hb_stop()
            set_status(self, "Stopped")
            return "stopped"
        return None

    def hb_start(self, context: ExecutionContext) -> str | None:
        if self.hb_pump is not None and self.hb_pump.running:
            return "started"
        if not (self.value("callbacks") or {}):
            set_status(self, "No subscriber")
            return None
        device = DeviceInput(
            _device(str(self.recording.device)),
            _number(str(self.recording.sample_rate)),
            _number(str(self.recording.channels)),
            int(self.recording.block_size),
        )
        self.hb_input = device  # set first: a stream that opens and then fails to start is still closed
        device.open()

        def deliver(block: AudioBlock, number: int, seconds: float) -> None:
            deliver_to_subscribers(context, self.value("callbacks"), block, number, seconds)
            self.hb_report(device)

        self.hb_pump = BlockPump(produce=device.read, deliver=deliver, on_end=self.hb_on_end, paced=False)
        self.hb_pump.start()
        set_status(self, f"Listening {device.channels} ch at {device.sample_rate} Hz")
        return "started"

    def hb_report(self, device: DeviceInput) -> None:
        now = time.monotonic()
        if now - self.hb_status_at < STATUS_INTERVAL:
            return
        self.hb_status_at = now
        set_status(self, status_text(device))

    def hb_on_end(self, error: Exception | None) -> None:
        if error is not None:
            set_status(self, f"Error: {error}")

    def hb_stop(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        device = getattr(self, "hb_input", None)
        if device is not None:
            device.close()  # ends the pump's wait for the next block
            self.hb_input = None
        pump = getattr(self, "hb_pump", None)
        if pump is not None:
            pump.stop()
            self.hb_pump = None


def status_text(device: DeviceInput) -> str:
    """Return the status line of a running ``device``: what it really delivers, and what it lost."""
    blocks = f"blocks {device.block_frames}"
    if device.block_frames != device.block_size:
        blocks += f" (asked {device.block_size})"
    return (
        f"Listening {device.channels} ch at {device.sample_rate} Hz, {blocks}, "
        f"latency {device.latency * 1000:.1f} ms, lost {device.lost}, overflow {device.overflows}"
    )


def _device(text: str) -> str | int | None:
    text = text.strip()
    if not text or text == _DEFAULT_DEVICE:
        return None
    return int(text) if text.isdigit() else text


def _number(text: str) -> int | None:
    """Return the number a choice names; ``None`` for the device's own value."""
    text = text.strip()
    return int(text) if text.isdigit() else None
