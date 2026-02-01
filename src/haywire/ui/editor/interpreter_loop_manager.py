"""
Interactive Interpreter Loop Manager.

Manages continuous execution loop for interactive interpreter sessions.
Dispatches BEGIN_PLAY, TICK, and SHUTDOWN events at configurable framerates.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from threading import Thread, Lock
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
    
    Usage:
        # Create manager
        manager = InterpreterLoopManager(interpreter, target_fps=60.0)
        
        # Start loop (dispatches BEGIN_PLAY, then periodic TICK)
        manager.start()
        
        # Stop loop (dispatches SHUTDOWN)
        manager.stop()
        
        # Get performance stats
        stats = manager.get_stats()
        print(f"Running at {stats['actual_fps']:.1f} FPS")
    """
    
    def __init__(
        self,
        interpreter: 'Interpreter',
        target_fps: float = 60.0
    ):
        """
        Initialize loop manager.
        
        Args:
            interpreter: Interpreter instance to dispatch events to
            target_fps: Target framerate (frames per second)
        """
        self.interpreter = interpreter
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps
        
        # Loop control
        self.is_running = False
        self.loop_thread: Optional[Thread] = None
        self.should_stop = False
        self._lock = Lock()
        
        # Performance tracking
        self.last_tick_time = 0.0
        self.actual_fps = 0.0
        self.frame_count = 0
        self._fps_samples = []
        self._max_fps_samples = 10  # Rolling average over 10 frames
        
        logger.info(
            f"InterpreterLoopManager created with target {target_fps} FPS"
        )
    
    def start(self):
        """
        Start the execution loop.
        
        Dispatches BEGIN_PLAY event, then starts continuous TICK loop.
        Thread-safe - can be called multiple times.
        """
        with self._lock:
            if self.is_running:
                logger.warning("Loop already running, ignoring start()")
                return
            
            self.should_stop = False
            self.is_running = True
            self.frame_count = 0
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
        with self._lock:
            if not self.is_running:
                logger.warning("Loop not running, ignoring stop()")
                return
            
            self.should_stop = True
        
        logger.info("Stopping interpreter loop...")
        
        # Wait for loop thread to exit
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=2.0)
            
            if self.loop_thread.is_alive():
                logger.warning("Loop thread did not exit cleanly")
        
        # Dispatch SHUTDOWN event
        logger.info("Dispatching SHUTDOWN event")
        self.interpreter.dispatch_system_event(SystemEventType.SHUTDOWN)
        
        with self._lock:
            self.is_running = False
        
        logger.info("Interpreter loop stopped")
    
    def _loop_worker(self):
        """
        Worker function that runs in separate thread.
        
        Continuously dispatches TICK events at the target framerate
        until stop() is called.
        """
        logger.debug("Loop worker thread started")
        
        self.last_tick_time = time.time()
        
        while not self.should_stop:
            frame_start = time.time()
            
            # Calculate delta time
            delta_time = frame_start - self.last_tick_time
            self.last_tick_time = frame_start
            
            # Dispatch TICK event with delta_time payload
            try:
                self.interpreter.dispatch_system_event(
                    SystemEventType.TICK,
                    payload={'delta_time': delta_time}
                )
            except Exception as e:
                logger.error(f"Error dispatching TICK event: {e}", exc_info=True)
            
            # Update performance metrics
            with self._lock:
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
                
                with self._lock:
                    self._fps_samples.append(frame_fps)
                    if len(self._fps_samples) > self._max_fps_samples:
                        self._fps_samples.pop(0)
                    
                    # Update average FPS
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
        
        Examples:
            manager.set_target_fps(30.0)  # Slow to 30 FPS
            manager.set_target_fps(120.0) # Speed up to 120 FPS
        """
        if fps <= 0:
            logger.warning(f"Invalid FPS {fps}, must be > 0")
            return
        
        with self._lock:
            self.target_fps = fps
            self.target_frame_time = 1.0 / fps
        
        logger.info(f"Target FPS updated to {fps:.1f}")
    
    def get_stats(self) -> dict:
        """
        Get performance statistics.
        
        Thread-safe - can be called from any thread.
        
        Returns:
            Dictionary with current loop state and performance metrics:
            - is_running: bool
            - target_fps: float
            - actual_fps: float (rolling average)
            - frame_count: int
        
        Examples:
            stats = manager.get_stats()
            print(f"FPS: {stats['actual_fps']:.1f}")
        """
        with self._lock:
            return {
                'is_running': self.is_running,
                'target_fps': self.target_fps,
                'actual_fps': self.actual_fps,
                'frame_count': self.frame_count
            }
    
    def __str__(self) -> str:
        stats = self.get_stats()
        return (
            f"InterpreterLoopManager("
            f"running={stats['is_running']}, "
            f"target={stats['target_fps']:.1f}fps, "
            f"actual={stats['actual_fps']:.1f}fps, "
            f"frames={stats['frame_count']})"
        )
