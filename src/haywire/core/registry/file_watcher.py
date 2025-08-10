import logging
import ast
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional
from collections import defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from haywire.core.registry.base import BaseLibrary, FileChangeEvent

class LibraryFileHandler(FileSystemEventHandler):
    """Handles file system events for library files"""
    
    def __init__(self, file_watcher):
        self.file_watcher = file_watcher
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self.file_watcher._handle_file_change(event.src_path, 'modified')
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self.file_watcher._handle_file_change(event.src_path, 'created')
    
    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self.file_watcher._handle_file_change(event.src_path, 'deleted')


class FileWatcher:
    """
    A file watcher that monitors Python files and notifies registered libraries
    about changes with debouncing to prevent rapid-fire events.
    """
    
    def __init__(self, debounce_delay: float = 0.5):
        self.debounce_delay = debounce_delay
        self.libraries: Dict[str, BaseLibrary] = {}
        self.watched_paths: Dict[str, Set[str]] = defaultdict(set)  # path -> library_names
        self.observers: Dict[str, Observer] = {}  # path -> observer
        self.pending_events: Dict[str, FileChangeEvent] = {}  # file_path -> latest_event
        self.debounce_timers: Dict[str, threading.Timer] = {}  # file_path -> timer
        self._lock = threading.Lock()
        self.handler = LibraryFileHandler(self)
    
    def add_library(self, library: BaseLibrary):
        """Add a library to be watched"""
        library_name = library.metadata.name
        library_path = Path(library.file_path)
        
        # Handle both files and directories
        if library_path.is_file():
            watch_path = str(library_path.parent)
        else:
            watch_path = str(library_path)
        
        with self._lock:
            self.libraries[library_name] = library
            self.watched_paths[watch_path].add(library_name)
            
            # Start watching this path if not already watched
            if watch_path not in self.observers:
                self._start_watching_path(watch_path)
    
    def remove_library(self, library_name: str):
        """Remove a library from being watched"""
        if library_name not in self.libraries:
            return
        
        with self._lock:
            library = self.libraries[library_name]
            library_path = Path(library.file_path)
            
            if library_path.is_file():
                watch_path = str(library_path.parent)
            else:
                watch_path = str(library_path)
            
            # Remove library from watched paths
            if watch_path in self.watched_paths:
                self.watched_paths[watch_path].discard(library_name)
                
                # Stop watching if no more libraries need this path
                if not self.watched_paths[watch_path]:
                    self._stop_watching_path(watch_path)
                    del self.watched_paths[watch_path]
            
            # Remove library
            del self.libraries[library_name]
    
    def _start_watching_path(self, path: str):
        """Start watching a specific path"""
        observer = Observer()
        observer.schedule(self.handler, path, recursive=True)
        observer.start()
        self.observers[path] = observer
        print(f"Started watching: {path}")
    
    def _stop_watching_path(self, path: str):
        """Stop watching a specific path"""
        if path in self.observers:
            observer = self.observers[path]
            observer.stop()
            observer.join()
            del self.observers[path]
            print(f"Stopped watching: {path}")
    
    def _handle_file_change(self, file_path: str, event_type: str):
        """Handle file change with debouncing"""
        with self._lock:
            # Cancel existing timer for this file
            if file_path in self.debounce_timers:
                self.debounce_timers[file_path].cancel()
            
            # Create new event
            event = FileChangeEvent(
                file_path=file_path,
                event_type=event_type,
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
        
        # Notify libraries outside the lock
        self._notify_libraries(event)
        
    def start(self):
        """Start all observers (if not already started)"""
        with self._lock:
            for path, observer in self.observers.items():
                if not observer.is_alive():
                    observer.start()
                    print(f"Started observer for: {path}")
    
    def stop(self):
        """Stop all observers and clean up"""
        with self._lock:
            # Cancel all pending timers
            for timer in self.debounce_timers.values():
                timer.cancel()
            self.debounce_timers.clear()
            self.pending_events.clear()
            
            # Stop all observers
            for path in list(self.observers.keys()):
                self._stop_watching_path(path)
    
    def is_watching(self, path: str) -> bool:
        """Check if a path is currently being watched"""
        return path in self.observers
    
    def get_watched_paths(self) -> Set[str]:
        """Get all currently watched paths"""
        return set(self.observers.keys())

    def _notify_libraries(self, event: FileChangeEvent):
        """Notify affected libraries about the file change"""
        file_path = Path(event.file_path)
        
        # Find all libraries that should be notified
        affected_libraries = set()
        
        for watch_path, library_names in self.watched_paths.items():
            watch_path_obj = Path(watch_path)
            
            # Check if the changed file is within this watched path
            try:
                if file_path.is_relative_to(watch_path_obj):
                    affected_libraries.update(library_names)
            except ValueError:
                # is_relative_to can raise ValueError in some edge cases
                # Fall back to string comparison
                if str(file_path).startswith(str(watch_path_obj)):
                    affected_libraries.update(library_names)

        # For deleted files, skip validation
        if event.event_type != 'deleted':
            # Validate Python file before notifying libraries
            if not self._validate_python_file(event.file_path):
                logging.error(f"Invalid Python file: {event.file_path}. Skipping Hot Reloading.")
                return
        
        # Notify each affected library
        for library_name in affected_libraries:
            if library_name in self.libraries:
                library = self.libraries[library_name]
                try:
                    library.handle_file_change(event)
                    print(f"Notified {library_name} about {event.event_type}: {event.file_path}")
                except Exception as e:
                    print(f"Error notifying {library_name}: {e}")

    def _validate_python_file(self, file_path: str) -> bool:
        """
        Check if Python file compiles without syntax errors
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Try to parse the AST
            ast.parse(source_code, filename=file_path)
            return True
        except SyntaxError as e:
            # Get specific syntax error details
            error_details = [
                f"Syntax error in {file_path}:",
                f"  Line {e.lineno}: {e.text.strip() if e.text else 'N/A'}",
                f"  Error: {e.msg}",
                f"  Position: {' ' * (e.offset - 1) if e.offset else ''}^" if e.offset else ""
            ]
            logging.error("\n".join(filter(None, error_details)))
            return False
        except Exception as e:
            logging.error(f"Error reading/parsing {file_path}: {e}")
            return False