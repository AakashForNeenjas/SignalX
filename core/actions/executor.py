import json
import time

from core.actions.context import ActionContext
from core.actions.dispatch import dispatch_action
from core.actions.validation import validate_action_params


class ActionExecutor:
    def __init__(self, sequencer):
        self.sequencer = sequencer

    def execute(self, action, params, index=None):
        """
        Execute an action and return (success: bool, message: str).
        Normalizes unexpected return shapes to a failure.
        """
        start_ts = time.perf_counter()
        ok, validation_msg = validate_action_params(action, params)
        if not ok:
            return self._finalize(action, False, validation_msg, "INVALID_PARAMS", start_ts)
        try:
            self.sequencer._current_index = index
            ctx = ActionContext(self.sequencer)
            result = dispatch_action(action, params, ctx)
            if not isinstance(result, tuple) or len(result) != 2:
                return self._finalize(
                    action,
                    False,
                    f"Action returned invalid result shape: {result}",
                    "INVALID_RESULT",
                    start_ts,
                )
            success, message = result
            code = "OK" if success else "FAILED"
            final_message = message or ("OK" if success else "Action failed")
            return self._finalize(action, success, final_message, code, start_ts)
        except Exception as exc:
            msg = f"Action '{action}' failed with exception: {exc}"
            print(msg)
            return self._finalize(action, False, msg, "EXCEPTION", start_ts)

    def _finalize(self, action, success, message, code, start_ts):
        duration_ms = (time.perf_counter() - start_ts) * 1000.0
        result = {
            "action": action,
            "success": success,
            "code": code,
            "duration_ms": round(duration_ms, 3),
            "message": message,
        }
        try:
            self.sequencer.last_action_result = result
            self.sequencer.last_action_duration_ms = result["duration_ms"]
        except Exception:
            pass
        try:
            payload = json.dumps(result, ensure_ascii=True)
            self.sequencer._log(20 if success else 30, f"[ACTION_RESULT] {payload}")
        except Exception:
            pass
        return success, message
