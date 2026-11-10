"""EXEC_AUDIO: an EXEC that audio flows drive standard control nodes with, and the reverse refused."""

import pytest
from haywire.barn.builtin.types import EXEC
from haywire.barn.builtin.wires import ControlWire
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.types.wire import WireRole, wire_type_of

from haybale_audio.types.exec_audio import EXEC_AUDIO

pytestmark = pytest.mark.unit


def _chain(source: type, sink: type) -> tuple[object, str | None]:
    return AdapterFactory(AdapterRegistry()).create_chain(source, sink, "edge")  # type: ignore[arg-type]


def test_it_is_an_exec_on_the_control_wire():
    assert issubclass(EXEC_AUDIO, EXEC)
    wire = wire_type_of(EXEC_AUDIO)
    assert wire is ControlWire
    assert wire.role is WireRole.SEQUENCE


def test_it_is_registered_as_a_type_of_the_audio_library():
    assert EXEC_AUDIO.class_identity.registry_key == "haybale-audio:type:EXEC_AUDIO"
    assert EXEC_AUDIO.class_identity.label == "Audio Execution Signal"


def test_an_audio_flow_connects_to_an_audio_flow():
    chain, error = _chain(EXEC_AUDIO, EXEC_AUDIO)
    assert (chain is not None, error) == (True, None)


def test_an_audio_flow_can_drive_a_standard_control_node():
    chain, error = _chain(EXEC_AUDIO, EXEC)
    assert (chain is not None, error) == (True, None)


def test_a_standard_control_node_cannot_drive_an_audio_flow():
    chain, error = _chain(EXEC, EXEC_AUDIO)
    assert chain is None
    assert error is not None
    assert "EXEC" in error


def test_its_default_is_an_empty_payload():
    assert EXEC_AUDIO.create_default().value == {}
