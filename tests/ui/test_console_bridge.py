"""Tests for ConsoleBridge module-level instance."""

from haywire.ui.console_bridge import get_bridge, console_print, ConsoleBridge


def test_get_bridge_returns_console_bridge():
    bridge = get_bridge()
    assert isinstance(bridge, ConsoleBridge)


def test_get_bridge_returns_same_instance():
    assert get_bridge() is get_bridge()


def test_console_print_queues_message():
    bridge = get_bridge()
    bridge.clear()
    console_print("hello test")
    # Drain one message from the queue
    msg = bridge.message_queue.get_nowait()
    assert msg == "hello test"


def test_no_get_instance_classmethod():
    assert not hasattr(ConsoleBridge, "get_instance"), (
        "ConsoleBridge.get_instance() should be removed in favour of get_bridge()"
    )
