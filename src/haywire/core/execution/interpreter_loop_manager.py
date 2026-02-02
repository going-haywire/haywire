"""
Interactive Interpreter Loop Manager.

Manages continuous execution loop for interactive interpreter sessions.
Dispatches BEGIN_PLAY, TICK, and SHUTDOWN events at configurable framerates.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable
from threading import Thread, Lock, Event
import time
import logging

if TYPE_CHECKING:
    from haywire.core.execution.interpreter import Interpreter

from haywire.core.execution.event_source import SystemEventType

logger = logging.getLogger(__name__)


class InterpreterLoopManager:
    """
    Manages continuous execution loop for interactive interpreter.
    
    Responsibilities:
    - Maintain persistent loop thread
    - Dispatch TICK events at configured framerate
    - Handle START/STOP lifecycle
    - Track performance metrics (FPS, frame time)
    - Backpressure to prevent queue buildup
    
    Usage:
        manager = InterpreterLoopManager(interpreter, target_fps=60.0)
        manager.start()
        stats = manager.get_stats()
        manager.stop()
    """
    
    def __init__(
        self,
        interpreter: 'Interpreter',
        target_fps: float = 60.0,
        max_queued_ticks: int = 2
    ):
        """
        Initialize loop manager.
        
        Args:
            interpreter: Interpreter instance to dispatch events to
            target_fps: Target framerate (frames per second)
            max_queued_ticks: Maximum pending ticks before dropping frames
        """
        self.interpreter = interpreter
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps
        self.max_queued_ticks = max_queued_ticks
        
        # Loop control
        self.is_running = False
        self.loop_thread: Optional[Thread] = None
        self.should_stop = False
        
        # Backpressure tracking
        self._pending_ticks = 0
        self._tick_lock = Lock()
        
        # Performance tracking (use atomics where possible)
        self.last_tick_time = 0.0
        self.actual_fps = 0.0
        self.frame_count = 0
        self.dropped_frames = 0
        self._fps_samples: list[float] = []
        self._max_fps_samples = 10
        self._stats_lock = Lock()
        
        logger.info(
            f"InterpreterLoopManager created: "
            f"target={target_fps}FPS, max_queued={max_queued_ticks}"
        )
    
    def start(self):
        """
        Start the execution loop.
        
        Dispatches BEGIN_PLAY event, then starts continuous TICK loop.
        Thread-safe - can be called multiple times.
        """
        if self.is_running:
            logger.warning("Loop already running, ignoring start()")
            return
        
        self.should_stop = False
        self.is_running = True
        self.frame_count = 0
        self.dropped_frames = 0
        
        with self._tick_lock:
            self._pending_ticks = 0
        
        with self._stats_lock:
            self._fps_samples.clear()
        
        # Dispatch BEGIN_PLAY event
        logger.info("Dispatching BEGIN_PLAY event")
        self.interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        
        # Start loop thread
        self.loop_thread = Thread(
            target=self._loop_worker,
            name="InterpreterLoop",
            daemon=True
        )
        self.loop_thread.start()
        
        logger.info("Interpreter loop started")
    
    def stop(self):
        """
        Stop the execution loop.
        
        Dispatches SHUTDOWN event and waits for thread to exit.
        Thread-safe - can be called multiple times.
        """
        if not self.is_running:
            logger.warning("Loop not running, ignoring stop()")
            return
        
        logger.info("Stopping interpreter loop...")
        
        self.should_stop = True
        
        # Wait for loop thread to exit
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=2.0)
            
            if self.loop_thread.is_alive():
                logger.warning("Loop thread did not exit cleanly")
        
        # Dispatch SHUTDOWN event
        logger.info("Dispatching SHUTDOWN event")
        self.interpreter.dispatch_system_event(SystemEventType.SHUTDOWN)
        
        self.is_running = False
        
        logger.info(
            f"Interpreter loop stopped. "
            f"Frames: {self.frame_count}, Dropped: {self.dropped_frames}"
        )
    
    def _on_tick_complete(self):
        """Called when a tick finishes execution. Reduces pending count."""
        with self._tick_lock:
            self._pending_ticks = max(0, self._pending_ticks - 1)
    
    def _loop_worker(self):
        """
        Worker function that runs in separate thread.
        
        Continuously dispatches TICK events at the target framerate
        until stop() is called. Implements backpressure by dropping
        frames when execution falls behind.
        """
        logger.debug("Loop worker thread started")
        
        self.last_tick_time = time.time()
        
        while not self.should_stop:
            frame_start = time.time()
            
            # Check backpressure
            with self._tick_lock:
                if self._pending_ticks >= self.max_queued_ticks:
                    # Drop this frame - we're falling behind
                    self.dropped_frames += 1
                    logger.debug(
                        f"Dropping frame (pending={self._pending_ticks})"
                    )
                    time.sleep(self.target_frame_time * 0.5)
                    continue
                
                self._pending_ticks += 1
            
            # Calculate delta time
            delta_time = frame_start - self.last_tick_time
            self.last_tick_time = frame_start
            
            # Dispatch TICK event with completion callback
            try:
                self.interpreter.dispatch_system_event(
                    SystemEventType.TICK,
                    payload={
                        'delta_time': delta_time,
                        '_on_complete': self._on_tick_complete
                    }
                )
            except Exception as e:
                logger.error(f"Error dispatching TICK event: {e}", exc_info=True)
                self._on_tick_complete()  # Still decrement on error
            
            # Update frame count
            self.frame_count += 1
            
            # Sleep to maintain target framerate
            frame_elapsed = time.time() - frame_start
            sleep_time = max(0, self.target_frame_time - frame_elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Calculate actual FPS (rolling average)
            actual_frame_time = time.time() - frame_start
            if actual_frame_time > 0:
                frame_fps = 1.0 / actual_frame_time
                
                with self._stats_lock:
                    self._fps_samples.append(frame_fps)
                    if len(self._fps_samples) > self._max_fps_samples:
                        self._fps_samples.pop(0)
                    
                    self.actual_fps = (
                        sum(self._fps_samples) / len(self._fps_samples)
                    )
        
        logger.debug("Loop worker thread exiting")
    
    def set_target_fps(self, fps: float):
        """
        Update target framerate.
        
        Can be called while loop is running to adjust framerate dynamically.
        
        Args:
            fps: New target framerate (must be > 0)
        """
        if fps <= 0:
            logger.warning(f"Invalid FPS {fps}, must be > 0")
            return
        
        self.target_fps = fps
        self.target_frame_time = 1.0 / fps
        
        logger.info(f"Target FPS updated to {fps:.1f}")
    
    def get_stats(self) -> dict:
        """
        Get performance statistics.
        
        Thread-safe - can be called from any thread.
        
        Returns:
            Dictionary with current loop state and performance metrics
        """
        with self._stats_lock:
            actual_fps = self.actual_fps
        
        with self._tick_lock:
            pending = self._pending_ticks
        
        return {
            'is_running': self.is_running,
            'target_fps': self.target_fps,
            'actual_fps': actual_fps,
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames,
            'pending_ticks': pending
        }
    
    def __str__(self) -> str:
        stats = self.get_stats()
        return (
            f"InterpreterLoopManager("
            f"running={stats['is_running']}, "
            f"target={stats['target_fps']:.1f}fps, "
            f"actual={stats['actual_fps']:.1f}fps, "
            f"frames={stats['frame_count']}, "
            f"dropped={stats['dropped_frames']})"
        )