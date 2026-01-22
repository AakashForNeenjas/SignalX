import time
import threading
import traceback
from PyQt6.QtCore import QObject, pyqtSignal
from core.actions.executor import ActionExecutor

class Sequencer(QObject):
    step_completed = pyqtSignal(int, str) # step_index, status
    action_info = pyqtSignal(int, str)    # step_index, message
    sequence_finished = pyqtSignal()
    
    def __init__(self, instrument_manager, can_manager, logger=None):
        super().__init__()
        self.inst_mgr = instrument_manager
        self.can_mgr = can_manager
        self.steps = []
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.logger = logger
        self.executor = ActionExecutor(self)

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass

    def _log_cmd(self, message):
        """Log instrument command intent for traceability."""
        self._log(20, f"CMD: {message}")
        print(f"[CMD] {message}")

    def set_steps(self, steps):
        self.steps = steps

    def start_sequence(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_sequence)
        self.thread.daemon = True
        self.thread.start()
        self._log(20, "Sequence started")

    def stop_sequence(self):
        self.running = False
        self.stop_event.set()
        self._log(20, "Sequence stop requested")

    def _run_sequence(self):
        print("Starting Sequence...")
        self._log(20, "Sequence thread running")
        try:
            for i, step in enumerate(self.steps):
                if self.stop_event.is_set() or not self.running:
                    self._log(20, "Sequence aborted by user")
                    break
                
                action = step.get('action')
                params = step.get('params')
                
                print(f"Executing Step {i+1}: {action}")
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
                        self._log(20 if success else 30, f"Step {i+1}: {message}")

                    if success:
                        self.step_completed.emit(i, "Pass")
                        print(f"Step {i+1}: Pass")
                    else:
                        self.step_completed.emit(i, "Fail")
                        print(f"Step {i+1}: Fail")
                        # Stop on failure
                        self.running = False
                        self.stop_event.set()
                        break
                        
                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"Step {i+1} Failed with exception: {e}")
                    self._log(40, f"Step {i+1} exception: {e}\n{tb}")
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
            print("Sequence Finished")
            self._log(20, "Sequence finished")

    def _execute_action(self, action, params, index=None):
        """
        Execute an action and return (success: bool, message: str).
        All actions must verify their success and return an informative message for the UI.
        """
        return self.executor.execute(action, params, index)

    def _handle_ramp_action(self, action_name, params):
        ctx = ActionContext(self)
        from core.actions import ramp
        return ramp.handle_ramp_action(action_name, params, ctx)

    def _handle_line_load_action(self, action_name, params):
        ctx = ActionContext(self)
        from core.actions import ramp
        return ramp.handle_line_load_action(action_name, params, ctx)
