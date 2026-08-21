"""RosterChanged / AgentConnected / AgentDisconnected — vocabulary contract."""

from dataclasses import FrozenInstanceError

import pytest

from haywire.core.signals import (
    AgentConnected,
    AgentDisconnected,
    RosterChanged,
    Signal,
    SignalDispatcher,
    SignalPeer,
)


@pytest.mark.parametrize("cls", [RosterChanged, AgentConnected, AgentDisconnected])
def test_all_three_are_cross_session(cls):
    """Emitter and subscriber live in different process roles."""
    assert cls.cross_session is True


@pytest.mark.parametrize("cls", [RosterChanged, AgentConnected, AgentDisconnected])
def test_all_three_are_signals(cls):
    assert issubclass(cls, Signal)


def test_roster_changed_is_payload_free():
    """Subscribers re-read RosterCache."""
    RosterChanged()  # must not require arguments


@pytest.mark.parametrize("cls", [AgentConnected, AgentDisconnected])
def test_agent_signals_name_their_principal(cls):
    """Not re-derivable: MCP sessions are not enumerable after the fact."""
    assert cls(principal="scout").principal == "scout"


@pytest.mark.parametrize("cls", [AgentConnected, AgentDisconnected])
def test_agent_signals_are_keyword_only(cls):
    """Matches the kw_only convention of the rest of the vocabulary."""
    with pytest.raises(TypeError):
        cls("scout")  # type: ignore[misc]


@pytest.mark.parametrize("cls", [AgentConnected, AgentDisconnected])
def test_agent_signals_are_frozen(cls):
    signal = cls(principal="a")
    with pytest.raises(FrozenInstanceError):
        signal.principal = "b"  # type: ignore[misc]


def test_roster_changed_is_frozen():
    signal = RosterChanged()
    with pytest.raises(FrozenInstanceError):
        signal.cross_session = False  # type: ignore[misc]


def test_roster_changed_reaches_a_non_session_peer():
    """The subscriber (the Farmhand host) is not a browser session."""
    dispatcher = SignalDispatcher()
    emitter, host = SignalPeer(dispatcher), SignalPeer(dispatcher)

    seen: list[Signal] = []
    host.subscribe(RosterChanged, seen.append)

    emitter.publish(RosterChanged())

    assert len(seen) == 1


def test_agent_connected_reaches_browser_peers():
    """The subscriber (the shell's presence row) is in a browser session."""
    dispatcher = SignalDispatcher()
    host, shell = SignalPeer(dispatcher), SignalPeer(dispatcher)

    seen: list[AgentConnected] = []
    shell.subscribe(AgentConnected, seen.append)

    host.publish(AgentConnected(principal="scout"))

    assert [s.principal for s in seen] == ["scout"]
