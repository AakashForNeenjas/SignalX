
import time
from .base import StepExecutor


class WaitForSignal(StepExecutor):
    def execute(self, step, ctx):
        sig_name = step.params.get("signal")
        op = step.params.get("op", "==")
        expected = step.params.get("expected")
        timeout_ms = step.params.get("timeout_ms", 2000)
        tol = step.params.get("tolerance", 0.0)
        if not sig_name:
            return False, "Missing signal name"
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            val = self._read_signal(sig_name, ctx)
            if val is None:
                time.sleep(0.05)
                continue
            if self._check(val, expected, op, tol):
                return True, f"{sig_name} {op} {expected} (val={val})"
            time.sleep(0.05)
        return False, f"Timeout waiting for {sig_name} {op} {expected}"

    def _read_signal(self, name, ctx):
        # Prefer CAN manager live cache
        if ctx.can_mgr and hasattr(ctx.can_mgr, "signal_cache"):
            try:
                cache = ctx.can_mgr.signal_cache.get(name, {})
                return cache.get("value")
            except Exception:
                pass
        # Fallback to signal_manager if present in ctx
        if hasattr(ctx, "signal_manager") and ctx.signal_manager:
            try:
                cache = ctx.signal_manager.signal_cache.get(name, {})
                return cache.get("value")
            except Exception:
                pass
        return None

    def _check(self, val, expected, op, tol):
        try:
            if op == "exists" or op == "not_none":
                return val is not None
            if op == "==":
                return abs(val - expected) <= tol
            if op == "!=":
                return abs(val - expected) > tol
            if op == ">":
                return val > expected
            if op == "<":
                return val < expected
            if op == ">=":
                return val >= expected
            if op == "<=":
                return val <= expected
            if op == "in_range":
                lo, hi = expected
                return lo <= val <= hi
            if op == "approx":
                return abs(val - expected) <= tol
        except Exception:
            return False
        return False
