#!/usr/bin/env python3
"""
Haywire Synchronous Graph Runner

Runs a graph as fast as possible without any threading.
Useful for benchmarking and batch processing.

Usage:
    python run_graph_sync.py <graph_file> [--flow <event_type>] [--iterations <count>]

Examples:
    python run_graph_sync.py saves/graph.json --flow tick --iterations 1000
    python run_graph_sync.py saves/graph.json --flow begin_play
    python run_graph_sync.py saves/graph.json --list-flows
"""

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict


class SyncGraphRunner:
    """
    Runs a graph synchronously without any threading.

    Executes a specified flow in a tight loop as fast as possible.
    """

    def __init__(
        self,
        graph_path: Path,
        flow_type: str = "tick",
        iterations: Optional[int] = None,
        duration: Optional[float] = None,
        run_startup_flow: bool = True,
    ):
        self.graph_path = graph_path
        self.flow_type = flow_type.lower()
        self.iterations = iterations
        self.duration = duration
        self.run_startup_flow = run_startup_flow

        self.library_service = None
        self.graph = None
        self.vm = None
        self.flows: Dict[str, any] = {}  # event_key -> flow
        self.main_flow = None

        self._should_stop = False
        self._frame_count = 0
        self._start_time = 0.0

    def setup(self):
        """Initialize everything."""
        print("=" * 60)
        print("Haywire Sync Graph Runner")
        print("=" * 60)

        # Setup library system
        print("\n📚 Initializing library system...")
        self._setup_library_system()
        print("   ✓ Library system initialized")

        # Load graph
        print(f"\n📂 Loading graph: {self.graph_path}")
        self._load_graph()
        print(f"   ✓ Loaded {len(self.graph.node_wrappers)} nodes, {len(self.graph.edge_wrappers)} edges")

        # Assemble flows
        print("\n⚙️  Assembling flows...")
        self._assemble_flows()

        print("\n" + "=" * 60)

    def _setup_library_system(self):
        """Initialize the library system."""
        from haywire.core.di.config import (
            create_library_system_service,
            set_library_system,
            set_global_injector,
        )
        from haywire.core.undo.config import DEVELOPMENT_CONFIG

        project_root = self._find_project_root()

        self.library_service = create_library_system_service(
            workspace_root=str(project_root),
            enable_file_watching=False,
            watch_settings=False,
            undo_config=DEVELOPMENT_CONFIG,
        )

        set_library_system(self.library_service)
        set_global_injector(self.library_service.injector)

    def _find_project_root(self) -> Path:
        """Find project root."""
        current = Path(__file__).parent.resolve()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        return Path.cwd()

    def _load_graph(self):
        """Load graph from file."""
        from haywire.core.graph.base import BaseGraph

        path = Path(self.graph_path)
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {path}")

        self.graph = BaseGraph("sync_graph", "Sync Runner Graph")
        if not self.graph.load_from_file(str(path)):
            raise RuntimeError(f"Failed to load graph from: {path}")

    def _assemble_flows(self):
        """Assemble flows and setup VM."""
        from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
        from haywire.core.execution.vm import HaywireVM
        from haywire.core.execution.event_source import SystemEvent, SystemEventType

        # Create VM
        self.vm = HaywireVM()

        # Assemble flows
        assembly_manager = FlowAssemblyManager()
        assembled_flows = assembly_manager.assemble_graph(self.graph)

        # Map event types to flows
        event_type_map = {
            "begin_play": SystemEventType.BEGIN_PLAY,
            "shutdown": SystemEventType.SHUTDOWN,
        }

        # Store all flows by their subscription key and friendly name
        for flow in assembled_flows:
            key = flow.get_subscription_key()
            self.flows[key] = flow

            # Also map by friendly name
            for name, event_type in event_type_map.items():
                if key == SystemEvent(event_type).get_subscription_key():
                    self.flows[name] = flow

        # Print available flows
        print(f"   Found {len(assembled_flows)} flow(s):")
        for flow in assembled_flows:
            key = flow.get_subscription_key()
            friendly_name = self._get_friendly_name(key)
            node_count = len(list(flow.get_all_nodes()))
            print(f"      • {friendly_name} ({node_count} nodes)")

        # Find main flow to run
        if self.flow_type in self.flows:
            self.main_flow = self.flows[self.flow_type]
            friendly_name = self._get_friendly_name(self.main_flow.get_subscription_key())
            print(f"\n   ✓ Selected flow: {friendly_name}")
        else:
            available = [self._get_friendly_name(f.get_subscription_key()) for f in assembled_flows]
            raise RuntimeError(f"Flow '{self.flow_type}' not found. Available: {', '.join(available)}")

    def _get_friendly_name(self, subscription_key: str) -> str:
        """Convert subscription key to friendly name."""
        from haywire.core.execution.event_source import SystemEvent, SystemEventType

        name_map = {
            SystemEvent(SystemEventType.BEGIN_PLAY).get_subscription_key(): "begin_play",
            SystemEvent(SystemEventType.SHUTDOWN).get_subscription_key(): "shutdown",
        }

        return name_map.get(subscription_key, subscription_key)

    def list_flows(self) -> List[str]:
        """Return list of available flow names."""
        return [
            self._get_friendly_name(f.get_subscription_key())
            for f in self.flows.values()
            if hasattr(f, "get_subscription_key")
        ]

    def run(self):
        """Run the graph synchronously."""
        from haywire.core.execution.event_source import Trigger, SystemEvent, SystemEventType

        print("\n🚀 Starting synchronous execution...")

        # Call startup on main flow nodes
        print("   Calling node startup...")
        self._call_startup(self.main_flow)

        # Optionally run begin_play first (if not the main flow)
        if self.run_startup_flow and self.flow_type != "begin_play":
            begin_play_flow = self.flows.get("begin_play")
            if begin_play_flow:
                print("   Executing BEGIN_PLAY flow...")
                self._call_startup(begin_play_flow)
                trigger = Trigger(
                    source_key=SystemEvent(SystemEventType.BEGIN_PLAY).get_subscription_key(),
                    payload={},
                    timestamp=time.time(),
                )
                self.vm.execute_control_flow(begin_play_flow, trigger)

        # Determine subscription key for main flow
        main_flow_key = self.main_flow.get_subscription_key()

        self._start_time = time.time()
        self._frame_count = 0
        last_time = self._start_time
        last_report_time = self._start_time

        print(f"   Running '{self._get_friendly_name(main_flow_key)}' loop...")
        if self.iterations:
            print(f"   Target: {self.iterations:,} iterations")
        if self.duration:
            print(f"   Target: {self.duration} seconds")
        print("\n   Press Ctrl+C to stop\n")
        print("-" * 60)

        # Main loop
        try:
            while not self._should_stop:
                now = time.time()
                delta_time = now - last_time
                last_time = now

                # Create trigger with appropriate payload
                trigger = Trigger(
                    source_key=main_flow_key, payload={"delta_time": delta_time}, timestamp=now
                )

                # Execute flow directly
                self.vm.execute_control_flow(self.main_flow, trigger)

                self._frame_count += 1

                # Check iteration limit
                if self.iterations and self._frame_count >= self.iterations:
                    print(f"\n✓ Reached {self.iterations:,} iterations")
                    break

                # Check duration limit
                elapsed = now - self._start_time
                if self.duration and elapsed >= self.duration:
                    print(f"\n✓ Reached {self.duration}s duration")
                    break

                # Periodic progress report
                if now - last_report_time >= 1.0:
                    fps = self._frame_count / elapsed if elapsed > 0 else 0
                    print(f"   [{elapsed:6.1f}s] Frames: {self._frame_count:,} | FPS: {fps:,.0f}")
                    last_report_time = now

        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt")

        return True

    def _call_startup(self, flow):
        """Call startup on all nodes in a flow."""
        self.vm.call_flow_startup(flow)

    def _call_shutdown(self, flow):
        """Call shutdown on all nodes in a flow."""
        self.vm.call_flow_shutdown(flow)

    def stop(self):
        """Stop execution."""
        self._should_stop = True
        print("\n🛑 Stopping...")

        # Shutdown main flow
        if self.main_flow:
            self._call_shutdown(self.main_flow)

        # Shutdown begin_play flow if it was run
        if self.run_startup_flow and self.flow_type != "begin_play":
            begin_play_flow = self.flows.get("begin_play")
            if begin_play_flow:
                self._call_shutdown(begin_play_flow)

        print("   ✓ Stopped")

    def cleanup(self):
        """Clean up resources."""
        print("\n🧹 Cleaning up...")

        if self.library_service:
            from haywire.core.di.config import set_library_system, set_global_injector

            set_library_system(None)
            set_global_injector(None)

        print("   ✓ Done")

    def print_summary(self):
        """Print execution summary."""
        if not self._start_time or self._frame_count == 0:
            return

        elapsed = time.time() - self._start_time
        fps = self._frame_count / elapsed if elapsed > 0 else 0
        us_per_frame = (elapsed * 1_000_000) / self._frame_count if self._frame_count > 0 else 0

        print("\n" + "=" * 60)
        print("Execution Summary")
        print("=" * 60)
        print(f"   Flow:            {self._get_friendly_name(self.main_flow.get_subscription_key())}")
        print(f"   Duration:        {elapsed:.2f} seconds")
        print(f"   Total Frames:    {self._frame_count:,}")
        print(f"   Average FPS:     {fps:,.0f}")
        print(f"   Time per Frame:  {us_per_frame:.2f} μs")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run a Haywire graph synchronously (no threading).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s saves/graph.json --flow tick --iterations 1000
  %(prog)s saves/graph.json --flow begin_play
  %(prog)s saves/graph.json --list-flows
  %(prog)s saves/graph.json --flow tick --duration 5
  %(prog)s saves/graph.json --flow tick --no-startup
        """,
    )

    parser.add_argument("graph_file", type=str, help="Path to graph JSON file")

    parser.add_argument(
        "--flow",
        "-f",
        type=str,
        default="tick",
        help="Flow to run: tick, begin_play, shutdown, or subscription key (default: tick)",
    )

    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=None,
        help="Number of iterations (default: run until stopped)",
    )

    parser.add_argument(
        "--duration", "-d", type=float, default=None, help="Duration in seconds (default: run until stopped)"
    )

    parser.add_argument("--list-flows", action="store_true", help="List available flows and exit")

    parser.add_argument("--no-startup", action="store_true", help="Skip running BEGIN_PLAY before main flow")

    args = parser.parse_args()

    # Disable logging for clean benchmarks
    import logging

    logging.getLogger("haywire").setLevel(logging.WARNING)
    logging.getLogger("haywire.core.node.node_wrapper").setLevel(logging.INFO)  # Keep node stats

    runner = SyncGraphRunner(
        graph_path=Path(args.graph_file),
        flow_type=args.flow,
        iterations=args.iterations,
        duration=args.duration,
        run_startup_flow=not args.no_startup,
    )

    # Signal handler
    def signal_handler(signum, frame):
        runner._should_stop = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        runner.setup()

        # List flows mode
        if args.list_flows:
            print("\n👋 Done (list-flows mode)")
            runner.cleanup()
            return

        runner.run()
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
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


if __name__ == "__main__":
    main()
