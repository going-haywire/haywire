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
        # In UI setup (per session):
        bridge = ConsoleBridge.get_instance()
        log = ui.log(max_lines=100)
        timer = bridge.register_log_with_polling(log)
        
        # Store timer reference for cleanup:
        session_data['console_timer'] = timer
        
        # In worker thread (e.g., Print Message node):
        from haywire.ui.console_bridge import console_print
        console_print("Hello from node!")
    """
    
    _instance: Optional['ConsoleBridge'] = None
    _lock = Lock()
    
    def __init__(self):
        self.message_queue: Queue[str] = Queue()
        self.log_elements: dict = {}  # Maps log element to its timer
        self._max_messages_per_poll = 50
        self._history: list[str] = []
        self._max_history = 500
        
    @classmethod
    def get_instance(cls) -> 'ConsoleBridge':
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConsoleBridge()
            return cls._instance
    
    def register_log_with_polling(self, log_element, interval: float = 0.1):
        """
        Register a ui.log element and create a dedicated timer for it.
        
        Each timer polls the shared queue and broadcasts to ALL log elements.
        This ensures all sessions see the same output even if only one timer
        fires (in multi-session scenarios).
        
        Returns:
            The timer object for cleanup by caller.
        """
        # Create a timer in current client context that broadcasts to all logs
        timer = ui.timer(interval, self._poll_and_broadcast)
        self.log_elements[log_element] = timer
        return timer
    
    def register_log(self, log_element):
        """
        Register a ui.log element (deprecated - use register_log_with_polling).
        
        Kept for backwards compatibility.
        """
        if log_element not in self.log_elements:
            self.log_elements[log_element] = None
    
    def unregister_log(self, log_element):
        """Unregister a ui.log element and cancel its timer."""
        if log_element in self.log_elements:
            timer = self.log_elements[log_element]
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            del self.log_elements[log_element]
    
    def start_polling(self, interval: float = 0.1):
        """
        Start polling (deprecated - use register_log_with_polling instead).
        
        Kept for backwards compatibility but doesn't work correctly with
        multiple sessions.
        """
        pass  # No-op, kept for compatibility
    
    def stop_polling(self):
        """Stop polling (deprecated)."""
        pass  # No-op, kept for compatibility
    
    def _poll_and_broadcast(self):
        """
        Poll message queue and broadcast to ALL log elements.
        
        This is called by timers from different client contexts, but it
        broadcasts messages to all registered log elements. This ensures
        all sessions see all console output.
        """
        messages = []
        
        # Drain queue (up to batch limit) - thread-safe with lock
        with self._lock:
            for _ in range(self._max_messages_per_poll):
                try:
                    msg = self.message_queue.get_nowait()
                    messages.append(msg)
                except Empty:
                    break
        
        # Broadcast to ALL log elements (outside lock to avoid UI blocking)
        if messages:
            for log_element in list(self.log_elements.keys()):
                try:
                    for msg in messages:
                        log_element.push(msg)
                except Exception:
                    # Log element might be deleted, remove it
                    self.unregister_log(log_element)
    
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