"""Sequence executor for automated test procedures."""

import time
import threading
import traceback
from concurrent.futures import Future
from typing import List, Dict, Any, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal
from core.actions.executor import ActionExecutor
from core.logging_utils import LoggerMixin
from core.threading_utils import ManagedThreadPool


class Sequencer(LoggerMixin, QObject):
    """Executes sequences of test actions with thread management."""

    step_completed = pyqtSignal(int, str)  # step_index, status
    action_info = pyqtSignal(int, str)     # step_index, message
    sequence_finished = pyqtSignal()

    def __init__(
        self,
        instrument_manager: Any,
        can_manager: Any,
        logger: Optional[Any] = None
    ) -> None:
        """Initialize Sequencer.

        Args:
            instrument_manager: InstrumentManager instance
            can_manager: CANManager instance
            logger: Optional logger instance for logging (deprecated, uses LoggerMixin)
        """
        super().__init__()
        self.inst_mgr: Any = instrument_manager
        self.can_mgr: Any = can_manager
        self.steps: List[Dict[str, Any]] = []
        self.running: bool = False
        self.sequence_thread: Optional[threading.Thread] = None
        self._sequence_future: Optional[Future[None]] = None
        self.stop_event: threading.Event = threading.Event()
        self._external_logger: Optional[Any] = logger  # Keep for backwards compatibility
        self.executor: ActionExecutor = ActionExecutor(self)
        # Thread pool for sequence execution with integrated logging
        self._thread_pool: ManagedThreadPool = ManagedThreadPool(
            max_workers=2,
            thread_name_prefix="Sequencer",
            logger=self.logger
        )
        self.log_info("Sequencer initialized")

    def _log(self, level: int, message: str) -> None:
        """Log message using LoggerMixin (legacy interface for compatibility).

        Args:
            level: Logging level (10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR)
            message: Log message
        """
        # Use LoggerMixin's logger
        if level >= 40:
            self.log_error(message)
        elif level >= 30:
            self.log_warning(message)
        elif level >= 20:
            self.log_info(message)
        else:
            self.log_debug(message)

    def _log_cmd(self, message: str) -> None:
        """Log instrument command intent for traceability.

        Args:
            message: Command message to log
        """
        self.log_info(f"CMD: {message}")

    def set_steps(self, steps: List[Dict[str, Any]]) -> None:
        """Set sequence steps.

        Args:
            steps: List of step dictionaries containing action and params
        """
        self.steps = steps
        self.log_debug("Sequence steps loaded", step_count=len(steps))

    def start_sequence(self) -> None:
        """Start executing the sequence in a background thread."""
        if self.running:
            self.log_warning("Sequence already running, ignoring start request")
            return
        self.running = True
        self.stop_event.clear()
        # Use thread pool for better resource management
        self._sequence_future = self._thread_pool.submit(
            self._run_sequence,
            task_name="sequence_execution"
        )
        # Also create a thread reference for backwards compatibility with tests
        self.sequence_thread = threading.Thread(target=lambda: None)
        self.sequence_thread.daemon = True
        self.sequence_thread._started.set()  # Mark as "started" for is_alive() check  # type: ignore[attr-defined]
        self.log_info("Sequence started", step_count=len(self.steps))

    def stop_sequence(self) -> None:
        """Request sequence execution to stop."""
        self.running = False
        self.stop_event.set()
        # Cancel the thread pool task if possible
        if self._sequence_future:
            self._thread_pool.cancel_task("sequence_execution")
        self.log_info("Sequence stop requested")

    def is_sequence_running(self) -> bool:
        """Check if sequence is currently running.

        Returns:
            True if sequence is running, False otherwise
        """
        return self._thread_pool.is_task_running("sequence_execution") or self.running

    def shutdown(self) -> None:
        """Shutdown the sequencer and its thread pool."""
        self.stop_sequence()
        self._thread_pool.shutdown(wait=True)
        self.log_info("Sequencer shutdown complete")

    def _run_sequence(self) -> None:
        self.log_info("Sequence thread running")
        try:
            for i, step in enumerate(self.steps):
                if self.stop_event.is_set() or not self.running:
                    self.log_info("Sequence aborted by user")
                    break

                action = step.get('action')
                params = step.get('params')

                self.log_debug(f"Executing step {i+1}", action=action)
                self.step_completed.emit(i, "Running")

                try:
                    # Execute action and get success/failure status and message
                    result = self._execute_action(action, params, i)
                    if not isinstance(result, tuple) or len(result) != 2:
                        success, message = False, f"Action returned invalid result shape: {result}"
                    else:
                        success, message = result
                    # Emit message to output log using action_info
                    if message:
                        self.action_info.emit(i, message)
                        if success:
                            self.log_info(f"Step {i+1}: {message}")
                        else:
                            self.log_warning(f"Step {i+1}: {message}")

                    if success:
                        self.step_completed.emit(i, "Pass")
                        self.log_debug(f"Step {i+1}: Pass")
                    else:
                        self.step_completed.emit(i, "Fail")
                        self.log_warning(f"Step {i+1}: Fail")
                        # Stop on failure
                        self.running = False
                        self.stop_event.set()
                        break

                except Exception as e:
                    tb = traceback.format_exc()
                    self.log_error(f"Step {i+1} exception: {e}", exc_info=True)
                    self.step_completed.emit(i, "Fail")
                    # Stop on failure
                    self.running = False
                    self.stop_event.set()
                    break

                # Delay between steps, but remain responsive to stop
                delay = 0.5
                elapsed = 0.0
                while elapsed < delay and self.running and not self.stop_event.is_set():
                    time.sleep(0.05)
                    elapsed += 0.05

        finally:
            self.running = False
            self.stop_event.set()
            self.sequence_finished.emit()
            self.log_info("Sequence finished")

    def _execute_action(
        self,
        action: str,
        params: Dict[str, Any],
        index: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Execute an action and return result.

        Args:
            action: Action name to execute
            params: Action parameters dictionary
            index: Optional step index for logging

        Returns:
            Tuple of (success, message)
        """
        return self.executor.execute(action, params, index)  # type: ignore[no-any-return]

    def _handle_ramp_action(
        self,
        action_name: str,
        params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Handle ramp action execution.

        Args:
            action_name: Ramp action name
            params: Action parameters

        Returns:
            Tuple of (success, message)
        """
        from core.actions.context import ActionContext
        from core.actions import ramp
        ctx = ActionContext(self)
        return ramp.handle_ramp_action(action_name, params, ctx)  # type: ignore[no-any-return]

    def _handle_line_load_action(
        self,
        action_name: str,
        params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Handle line load action execution.

        Args:
            action_name: Line load action name
            params: Action parameters

        Returns:
            Tuple of (success, message)
        """
        from core.actions.context import ActionContext
        from core.actions import ramp
        ctx = ActionContext(self)
        return ramp.handle_line_load_action(action_name, params, ctx)  # type: ignore[no-any-return]
