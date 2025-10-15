from enum import Enum
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional
from collections import defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..inventory.base import FileChangeEvent, FileEventType, HotReloadRegistry
from ..inventory.library_identity import LibraryIdentity

class LibraryFileHandler(FileSystemEventHandler):
    """Handles file system events for a specific library path with debouncing"""
    
    def __init__(self, library_identity: LibraryIdentity, registry: HotReloadRegistry, debounce_delay: float = 0.5):
        self.library_identity = library_identity
        self.registry = registry
        self.debounce_delay = debounce_delay
        self.pending_events: Dict[str, FileChangeEvent] = {}  # file_path -> latest_event
        self.debounce_timers: Dict[str, threading.Timer] = {}  # file_path -> timer
        self._lock = threading.Lock()
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self._handle_file_change(event.src_path, FileEventType.MODIFIED)
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self._handle_file_change(event.src_path, FileEventType.CREATED)
    
    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self._handle_file_change(event.src_path, FileEventType.DELETED)
    
    def _handle_file_change(self, file_path: str, event_type: FileEventType):
        """Handle file change with debouncing"""
        with self._lock:
            # Cancel existing timer for this file
            if file_path in self.debounce_timers:
                self.debounce_timers[file_path].cancel()
            
            # Create new event with library_identity
            event = FileChangeEvent(
                file_path=file_path,
                event_type=event_type,
                library_identity=self.library_identity,
                timestamp=time.time()
            )
            
            # Store latest event
            self.pending_events[file_path] = event
            
            # Set up debounce timer
            timer = threading.Timer(
                self.debounce_delay,
                self._process_debounced_event,
                args=[file_path]
            )
            self.debounce_timers[file_path] = timer
            timer.start()
    
    def _process_debounced_event(self, file_path: str):
        """Process the event after debounce delay"""
        with self._lock:
            if file_path not in self.pending_events:
                return
            
            event = self.pending_events[file_path]
            del self.pending_events[file_path]
            
            if file_path in self.debounce_timers:
                del self.debounce_timers[file_path]
        
        self.registry.event_dispatcher(event)
    
    def cleanup(self):
        """Clean up pending timers"""
        with self._lock:
            for timer in self.debounce_timers.values():
                timer.cancel()
            self.debounce_timers.clear()
            self.pending_events.clear()


class FileWatcher:
    """
    Manages the lifecycle of file observers and their handlers.
    Each path gets its own observer and handler.
    """
    
    def __init__(self):
        self.observers: Dict[str, Observer] = {}  # path -> observer
        self.handlers: Dict[str, LibraryFileHandler] = {}  # path -> handler
        self._lock = threading.Lock()
    
    def add_watch(self, path: str, library_identity: LibraryIdentity, registry: HotReloadRegistry, debounce_delay: float = 0.5):
        """Add a path to be watched for a specific library and registry"""
        with self._lock:
            if path in self.observers:
                raise ValueError(f"Path {path} is already being watched")
            
            # Create handler for this library/path combination
            handler = LibraryFileHandler(library_identity, registry, debounce_delay)
            
            # Create and start observer
            observer = Observer()
            observer.schedule(handler, path, recursive=True)
            observer.start()
            
            # Store references
            self.observers[path] = observer
            self.handlers[path] = handler
            
            logging.info(f"Started watching {path} for library '{library_identity.label}'")
    
    def remove_watch(self, path: str):
        """Remove a path from being watched"""
        with self._lock:
            if path not in self.observers:
                return
            
            # Stop observer
            observer = self.observers[path]
            observer.stop()
            observer.join()
            
            # Cleanup handler
            handler = self.handlers[path]
            handler.cleanup()
            
            # Remove references
            del self.observers[path]
            del self.handlers[path]
            
            logging.info(f"Stopped watching {path}")
    
    def start(self):
        """Start all observers (if not already started)"""
        with self._lock:
            for path, observer in self.observers.items():
                if not observer.is_alive():
                    observer.start()
                    logging.info(f"Started observer for: {path}")
    
    def stop(self):
        """Stop all observers and clean up"""
        with self._lock:
            for path in list(self.observers.keys()):
                self.remove_watch(path)
    
    def is_watching(self, path: str) -> bool:
        """Check if a path is currently being watched"""
        return path in self.observers
    
    def get_watched_paths(self) -> Set[str]:
        """Get all currently watched paths"""
        return set(self.observers.keys())