#!/usr/bin/env python3
"""
Haywire Graph Runner CLI

Runs a graph file with the interpreter loop at a specified framerate.

Usage:
    python run_graph.py <graph_file> [--fps <framerate>] [--duration <seconds>]
    
Examples:
    python run_graph.py saves/graph_20260202_214451.json
    python run_graph.py saves/graph_20260202_214451.json --fps 60
    python run_graph.py saves/graph_20260202_214451.json --fps 30 --duration 10
    
Press Ctrl+C to stop gracefully.
"""

import argparse
import logging
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Optional

#import rerun as rr

#from math import tau
#import numpy as np
#from rerun.utilities import build_color_spiral
#from rerun.utilities import bounce_lerp

#rr.init("rerun_example_dna_abacus")

#rr.spawn()

class GraphRunner:
    """
    Standalone graph runner without UI.
    
    Loads a graph file and runs it with the interpreter loop.
    """
    
    def __init__(
        self,
        graph_path: Path,
        fps: float = 60.0,
        duration: Optional[float] = None,
        verbose: bool = False,
        log_level: str = 'WARNING'
    ):
        self.graph_path = graph_path
        self.fps = fps
        self.duration = duration
        self.verbose = verbose
        
        self.library_service = None
        self.graph = None
        self.interpreter = None
        self.loop_manager = None
        
        self._is_running = False
        self._start_time = 0.0
        self._should_stop = False

        self.log_level = log_level
    
    def setup(self):
        """Initialize library system and load graph."""
        print("=" * 60)
        print("Haywire Graph Runner")
        print("=" * 60)

        # Set log level
        level = getattr(logging, self.log_level.upper(), logging.WARNING)
        logging.getLogger('haywire').setLevel(level)        
        logging.getLogger('haywire.core.node.node_wrapper').setLevel(logging.INFO)  # Keep node stats
        logging.getLogger('haywire.core.execution.scheduler').setLevel(logging.INFO)
        logging.getLogger('haywire.core.graph.validation').setLevel(logging.INFO)
        #logging.getLogger('haywire.core.execution.vm').setLevel(logging.INFO)

        # Setup library system
        print("\n📚 Initializing library system...")
        self._setup_library_system()
        print("   ✓ Library system initialized")
        


        # Load graph
        print(f"\n📂 Loading graph: {self.graph_path}")
        self._load_graph()
        print(f"   ✓ Loaded {len(self.graph.node_wrappers)} nodes, "
              f"{len(self.graph.edge_wrappers)} edges")
        
        # Setup interpreter
        print("\n⚙️  Setting up interpreter...")
        self._setup_interpreter()
        print(f"   ✓ Interpreter ready (target: {self.fps} FPS)")
        
        # Print thread info with stack traces
        self._print_threads(show_stacks=True)

        print("\n" + "=" * 60)
    
    def _setup_library_system(self):
        """Initialize the library system."""
        from haywire.core.di.config import (
            create_library_system_service,
            set_library_system,
            set_global_injector
        )
        from haywire.core.undo.config import DEVELOPMENT_CONFIG
        
        # Find project root
        project_root = self._find_project_root()
        
        # Create library service
        self.library_service = create_library_system_service(
            workspace_root=str(project_root),
            enable_file_watching=False,  # No file watching for CLI
            watch_settings=False,
            undo_config=DEVELOPMENT_CONFIG
        )
        
        # Set global references
        set_library_system(self.library_service)
        set_global_injector(self.library_service.injector)
    
    def _find_project_root(self) -> Path:
        """Find project root by looking for pyproject.toml."""
        current = Path(__file__).parent.resolve()
        while current != current.parent:
            if (current / 'pyproject.toml').exists():
                return current
            current = current.parent
        
        # Fallback to current directory
        return Path.cwd()
    
    def _load_graph(self):
        """Load graph from file."""
        from haywire.core.graph.base import BaseGraph
        
        # Resolve path
        path = Path(self.graph_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {path}")
        
        # Create and load graph
        self.graph = BaseGraph("cli_graph", "CLI Runner Graph")
        
        if not self.graph.load_from_file(str(path)):
            raise RuntimeError(f"Failed to load graph from: {path}")
        
        self.graph.force_validation()
    
    def _setup_interpreter(self):
        """Setup interpreter and loop manager."""
        from haywire.core.execution.interpreter import Interpreter
        from haywire.core.execution.interpreter_loop_manager import InterpreterLoopManager
        
        # Create interpreter
        self.interpreter = Interpreter()
        
        # Create loop manager
        self.loop_manager = InterpreterLoopManager(
            interpreter=self.interpreter,
            target_fps=self.fps
        )
    
    def run(self):
        """Run the graph."""
        print("\n🚀 Starting interpreter...")
        
        # Validate graph
        errors = self.graph.validate()
        if errors:
            print(f"\n❌ Graph validation failed with {len(errors)} error(s):")
            for error in errors[:5]:
                print(f"   • {error}")
            if len(errors) > 5:
                print(f"   ... and {len(errors) - 5} more")
            return False
        
        # Load graph into interpreter
        try:
            self.interpreter.load_graph(self.graph)
        except Exception as e:
            print(f"\n❌ Failed to load graph: {e}")
            return False
        
        # Start loop
        self._start_time = time.time()
        self._is_running = True
        self.loop_manager.start()
        
        print(f"   ✓ Interpreter running at {self.fps} FPS")
        if self.duration:
            print(f"   ✓ Will stop after {self.duration} seconds")
        print("\n   Press Ctrl+C to stop\n")
        print("-" * 60)
        
        # Main loop - just wait and print stats
        try:
            last_stats_time = time.time()
            stats_interval = 1.0  # Print stats every second
            
            while self._is_running and not self._should_stop:
                time.sleep(0.1)
                
                # Check duration limit
                if self.duration:
                    elapsed = time.time() - self._start_time
                    if elapsed >= self.duration:
                        print(f"\n⏱️  Duration limit reached ({self.duration}s)")
                        break
                
                # Print periodic stats
                if self.verbose and time.time() - last_stats_time >= stats_interval:
                    self._print_stats()
                    last_stats_time = time.time()
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt received")
        
        return True
    
    def _print_threads(self, show_stacks: bool = False):
        """
        Print current thread information.
        
        Args:
            show_stacks: If True, show stack traces for each thread.
        """
        threads = threading.enumerate()
        print(f"\n🧵 Active threads: {len(threads)}")
        
        # Get stack frames for all threads
        import sys
        frames = sys._current_frames()
        
        for thread in threads:
            daemon_marker = " [daemon]" if thread.daemon else ""
            alive_marker = " [alive]" if thread.is_alive() else " [dead]"
            print(f"   • {thread.name}{daemon_marker}{alive_marker} (ID: {thread.ident})")
            
            # Try to show what started the thread
            if hasattr(thread, '_target') and thread._target:
                target = thread._target
                module = getattr(target, '__module__', '?')
                name = getattr(target, '__qualname__', getattr(target, '__name__', '?'))
                print(f"     Target: {module}.{name}")
            
            # Show current stack if requested
            if show_stacks and thread.ident in frames:
                print("     Stack trace:")
                frame = frames[thread.ident]
                stack = traceback.extract_stack(frame, limit=5)
                for i, (filename, lineno, func, text) in enumerate(stack):
                    # Shorten filename for readability
                    short_file = filename.split('/')[-1]
                    indent = "       " if i < len(stack) - 1 else "     → "
                    print(f"{indent}{short_file}:{lineno} in {func}()")
                    if text and i == len(stack) - 1:
                        print(f"         {text.strip()}")
        
    def stop(self):
        """Stop the interpreter gracefully."""
        if not self._is_running:
            return
        
        print("\n🛑 Stopping interpreter...")
        self._is_running = False
        
        # Stop loop manager
        if self.loop_manager and self.loop_manager.is_running:
            self.loop_manager.stop()
        
        # Wait for flows to complete
        if self.interpreter:
            try:
                self.interpreter.wait_all(timeout=2.0)
            except Exception as e:
                print(f"   ⚠️  Error waiting for flows: {e}")
        
        print("   ✓ Interpreter stopped")
    
    def cleanup(self):
        """Clean up resources."""
        print("\n🧹 Cleaning up...")
        
        # Shutdown interpreter
        if self.interpreter:
            self.interpreter.shutdown()
        
        # Cleanup library system
        if self.library_service:
            from haywire.core.di.config import set_library_system, set_global_injector
            set_library_system(None)
            set_global_injector(None)
        
        print("   ✓ Cleanup complete")

    def _print_stats(self):
        """Print current statistics."""
        stats = self.loop_manager.get_stats()
        elapsed = time.time() - self._start_time

        frame_count = stats.get('frame_count', 0)
        actual_fps = frame_count / elapsed if elapsed > 0 else 0.0
        
        print(f"   [{elapsed:6.1f}s] "
              f"Target FPS: {stats['target_fps']:.0f} | "
              f"Actual FPS: {actual_fps:.0f} | "
              f"Frames: {stats['frame_count']:,}")

    def print_summary(self):
        """Print execution summary."""
        if not self._start_time:
            return
        
        elapsed = time.time() - self._start_time
        stats = self.loop_manager.get_stats() if self.loop_manager else {}
        
        frame_count = stats.get('frame_count', 0)
        actual_fps = frame_count / elapsed if elapsed > 0 else 0.0

        print("\n" + "=" * 60)
        print("Execution Summary")
        print("=" * 60)
        print(f"   Duration:       {elapsed:.2f} seconds")
        print(f"   Target FPS:     {self.fps}")
        print(f"   Actual FPS:     {actual_fps:.1f}")
        print("=" * 60)


def main():
    
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run a Haywire graph file with the interpreter loop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s saves/my_graph.json
  %(prog)s saves/my_graph.json --fps 30
  %(prog)s saves/my_graph.json --fps 60 --duration 10
  %(prog)s saves/my_graph.json -v
        """
    )
    
    parser.add_argument(
        'graph_file',
        type=str,
        help='Path to the graph JSON file'
    )
    
    parser.add_argument(
        '--fps', '-f',
        type=float,
        default=60.0,
        help='Target framerate (default: 60)'
    )
    
    parser.add_argument(
        '--duration', '-d',
        type=float,
        default=None,
        help='Run duration in seconds (default: run until Ctrl+C)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print periodic statistics'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        type=str,
        default='WARNING',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: WARNING)'
    )   

    args = parser.parse_args()
    
    # Create runner
    runner = GraphRunner(
        graph_path=Path(args.graph_file),
        fps=args.fps,
        duration=args.duration,
        verbose=args.verbose,
        log_level=args.log_level
    )
    
    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        runner._should_stop = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    try:
        runner.setup()
        runner.run()
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        runner.stop()
        runner.print_summary()
        runner.cleanup()
    
    print("\n👋 Done!")


if __name__ == '__main__':    
    main()