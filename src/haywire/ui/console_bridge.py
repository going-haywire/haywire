"""
Thread-safe console bridge for NiceGUI.

Allows worker threads to print messages that appear in the UI.
"""
from __future__ import annotations
from typing import Optional, Callable
from threading import Lock
from queue import Queue, Empty
from nicegui import ui
import time


class ConsoleBridge:
    """
    Thread-safe bridge between worker threads and NiceGUI log elements.
    
    Usage:
        # In UI setup:
        bridge = ConsoleBridge.get_instance()
        log = ui.log(max_lines=100)
        bridge.register_log(log)
        bridge.start_polling()
        
        # In worker thread (e.g., Print Message node):
        from haywire.ui.console_bridge import console_print
        console_print("Hello from node!")
    """
    
    _instance: Optional['ConsoleBridge'] = None
    _lock = Lock()
    
    def __init__(self):
        self.message_queue: Queue[str] = Queue()
        self.log_elements: list = []
        self._polling_timer = None
        self._max_messages_per_poll = 50
        self._history: list[str] = []  # Add this
        self._max_history = 500        # Add this
        
    @classmethod
    def get_instance(cls) -> 'ConsoleBridge':
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConsoleBridge()
            return cls._instance
    
    def register_log(self, log_element):
        """Register a ui.log element to receive output."""
        if log_element not in self.log_elements:
            self.log_elements.append(log_element)
    
    def unregister_log(self, log_element):
        """Unregister a ui.log element."""
        if log_element in self.log_elements:
            self.log_elements.remove(log_element)
    
    def start_polling(self, interval: float = 0.1):
        """Start polling for messages (call from main thread)."""
        if self._polling_timer is None:
            self._polling_timer = ui.timer(interval, self._poll_messages)
    
    def stop_polling(self):
        """Stop polling for messages."""
        if self._polling_timer:
            self._polling_timer.cancel()
            self._polling_timer = None
    
    def _poll_messages(self):
        """Poll message queue and push to log elements (runs on main thread)."""
        messages = []
        
        # Drain queue (up to batch limit)
        for _ in range(self._max_messages_per_poll):
            try:
                msg = self.message_queue.get_nowait()
                messages.append(msg)
            except Empty:
                break
        
        # Push to all log elements
        if messages:
            for log in self.log_elements[:]:  # Copy list to avoid mutation issues
                try:
                    for msg in messages:
                        log.push(msg)
                except Exception:
                    # Log element might be deleted, remove it
                    self.unregister_log(log)
    
    def write(self, message: str):
        """Queue a message for display (thread-safe)."""
        if message.strip():
            self.message_queue.put(message.rstrip())
            # Keep history for copy
            self._history.append(message.rstrip())
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def get_history_text(self) -> str:
        """Get all history as text for copying."""
        return '\n'.join(self._history)

    def clear_history(self):
        """Clear the history buffer."""
        self._history.clear()
            
    def clear(self):
        """Clear the message queue."""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except Empty:
                break


# Convenience function for nodes
def console_print(*args, **kwargs):
    """
    Print to the NiceGUI console (thread-safe).
    
    Can be called from any thread, including node execution threads.
    
    Usage:
        from haywire.ui.console_bridge import console_print
        console_print("Value:", 42)
    """
    message = ' '.join(str(arg) for arg in args)
    bridge = ConsoleBridge.get_instance()
    bridge.write(message)