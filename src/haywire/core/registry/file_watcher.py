import logging
import os
import time
import ast
import threading
import traceback
from pathlib import Path
from typing import Dict, Set, Callable, Optional
from abc import ABC, abstractmethod
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

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
    File watcher that monitors library directories for changes and notifies libraries
    """
    
    def __init__(self, debounce_delay: float = 0.5):
        self.debounce_delay = debounce_delay
        self.observer = Observer()
        self.handler = LibraryFileHandler(self)
        self.watched_libraries: Dict[str, BaseLibrary] = {}  # library_name -> library instance
        self.watched_paths: Dict[str, Set[str]] = {}  # file_path -> set of library_names
        self.library_directories: Dict[str, str] = {}  # library_name -> directory_path
        self.watched_paths_last_event: Dict[str, float] = {}
        self.pending_changes: Dict[str, FileChangeEvent] = {}  # file_path -> latest event
        self.debounce_timer = None
        self.is_running = False
        self._lock = threading.Lock()
        
    def add_library(self, library: BaseLibrary):
        """Add a library to be watched"""
        library_name = library.metadata.name
        library_path = Path(library.file_path)
        
        with self._lock:
            self.watched_libraries[library_name] = library
            self.library_directories[library_name] = str(library_path)
            
            # Watch all Python files in the library directory and subdirectories
            for py_file in library_path.rglob("*.py"):
                file_path = str(py_file)
                if file_path not in self.watched_paths:
                    self.watched_paths[file_path] = set()
                    self.watched_paths_last_event[file_path] = time.time()
                self.watched_paths[file_path].add(library_name)

            logging.info(f"Added library '{library_name}' at {library_path} to file watcher.")

        # Start watching the library directory
        if not self.is_running:
            self.start()
        
        # Add the library path to the observer if not already watching
        try:
            self.observer.schedule(self.handler, str(library_path), recursive=True)
        except Exception as e:
            logging.warning(f"Could not watch library '{library_name}': {e}")

    def remove_library(self, library_name: str):
        """Remove a library from being watched"""
        with self._lock:
            if library_name in self.watched_libraries:
                del self.watched_libraries[library_name]
                
                # Remove from library directories
                if library_name in self.library_directories:
                    del self.library_directories[library_name]
                
                # Remove library from watched paths
                paths_to_remove = []
                for file_path, library_names in self.watched_paths.items():
                    library_names.discard(library_name)
                    if not library_names:
                        paths_to_remove.append(file_path)
                
                for file_path in paths_to_remove:
                    del self.watched_paths[file_path]
                    if file_path in self.watched_paths_last_event:
                        del self.watched_paths_last_event[file_path]

                logging.info(f"Removed library '{library_name}' from file watcher.")

    def start(self):
        """Start the file watcher"""
        if not self.is_running:
            logging.info("Starting file watcher...")
            self.observer.start()
            self.is_running = True
            logging.info("Started file watcher...")
    
    def stop(self):
        """Stop the file watcher"""
        if self.is_running:
            logging.info("Stopping file watcher...")
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            logging.info("Stopped file watcher...")

    def _find_libraries_for_file(self, file_path: str) -> Set[str]:
        """Find which libraries should be notified about changes to a file"""
        file_path = Path(file_path).resolve()
        matching_libraries = set()
        
        for library_name, library_dir in self.library_directories.items():
            library_path = Path(library_dir).resolve()
            try:
                # Check if file is within the library directory
                file_path.relative_to(library_path)
                matching_libraries.add(library_name)
            except ValueError:
                # File is not within this library directory
                continue
        
        return matching_libraries

    def _handle_file_change(self, file_path: str, event_type: str):
        """Handle a file change event with debouncing"""
        file_path = os.path.abspath(file_path)
        
        with self._lock:
            # For new files, dynamically determine which libraries they belong to
            if file_path not in self.watched_paths:
                matching_libraries = self._find_libraries_for_file(file_path)
                if matching_libraries:
                    self.watched_paths[file_path] = matching_libraries
                    self.watched_paths_last_event[file_path] = time.time()
                    logging.debug(f"Dynamically registered new file: {file_path} for libraries: {matching_libraries}")
                else:
                    # File doesn't belong to any watched library
                    return
            
            # For deleted files, clean up tracking
            if event_type == 'deleted':
                library_names = list(self.watched_paths[file_path])
                if library_names:
                    self.pending_changes[file_path] = FileChangeEvent(
                        file_path, event_type, library_names[0]
                    )
                # Remove from tracking after processing
                del self.watched_paths[file_path]
                if file_path in self.watched_paths_last_event:
                    del self.watched_paths_last_event[file_path]
            else:
                # Store the event (this will overwrite any previous event for the same file)
                library_names = list(self.watched_paths[file_path])
                if library_names:
                    self.pending_changes[file_path] = FileChangeEvent(
                        file_path, event_type, library_names[0]
                    )
        
        # Reset the debounce timer
        if self.debounce_timer:
            self.debounce_timer.cancel()
        
        self.debounce_timer = threading.Timer(self.debounce_delay, self._process_pending_changes)
        self.debounce_timer.start()
    
    def _process_pending_changes(self):
        """Process all pending file changes after debounce period"""
        with self._lock:
            changes_to_process = dict(self.pending_changes)
            self.pending_changes.clear()
        
        for file_path, event in changes_to_process.items():
            self._notify_libraries(event)
    
    def _notify_libraries(self, event: FileChangeEvent):
        """Notify affected libraries about the file change"""
        affected_libraries = self.watched_paths.get(event.file_path, set())

        if event.file_path.endswith('.py'):
            # For deleted files, skip validation
            if event.event_type != 'deleted':
                # Validate Python file before notifying libraries
                if not self._validate_python_file(event.file_path):
                    logging.error(f"Invalid Python file: {event.file_path}. Skipping Hot Reloading.")
                    return

            for library_name in affected_libraries:
                library = self.watched_libraries.get(library_name)
                if library:
                    try:
                        library.handle_file_change(event)
                    except Exception as e:
                        logging.error(f"Unable to notify library '{library_name}' about file change: {e}")

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