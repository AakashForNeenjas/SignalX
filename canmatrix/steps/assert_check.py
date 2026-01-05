from .base import StepExecutor
from canmatrix import assertions


class AssertCheck(StepExecutor):
    """
    Execute a single assertion described in step.params.
    Supported kinds: cycle_time, dlc, range, missing, latency, checksum, counter, mux_coverage
    """
    def execute(self, step, ctx):
        kind = step.params.get("kind")
        if not kind:
            return False, "Assertion kind missing"

        metrics = getattr(ctx, "metrics", None)
        if kind == "cycle_time":
            msg_id = step.params.get("arb_id")
            spec_ms = step.params.get("spec_ms")
            tol_pct = step.params.get("tol_pct", 10.0)
            if not metrics:
                return False, "Metrics not available for cycle_time"
            res = assertions.assert_cycle_time(metrics, msg_id, spec_ms, tol_pct)
            return res["passed"], res["details"]

        if kind == "dlc":
            msg_id = step.params.get("arb_id")
            expected = step.params.get("expected")
            if not metrics:
                return False, "Metrics not available for dlc"
            res = assertions.assert_dlc(metrics, msg_id, expected)
            return res["passed"], res["details"]

        if kind == "range":
            val = None
            sig = step.params.get("signal")
            if sig and ctx.can_mgr and hasattr(ctx.can_mgr, "signal_cache"):
                cache = ctx.can_mgr.signal_cache.get(sig, {})
                val = cache.get("value")
            res = assertions.assert_range(val, step.params.get("min"), step.params.get("max"))
            return res["passed"], res["details"]

        if kind == "missing":
            msg_id = step.params.get("arb_id")
            timeout_ms = step.params.get("timeout_ms", 500)
            if not metrics:
                return False, "Metrics not available for missing"
            res = assertions.assert_missing(metrics, msg_id, timeout_ms)
            return res["passed"], res["details"]

        if kind == "latency":
            lat_ms = step.params.get("lat_ms")
            max_ms = step.params.get("max_ms")
            res = assertions.assert_latency(lat_ms, max_ms)
            return res["passed"], res["details"]

        if kind == "checksum":
            flag = step.params.get("ok", False)
            res = assertions.assert_checksum(flag)
            return res["passed"], res["details"]

        if kind == "counter":
            prev = step.params.get("prev")
            curr = step.params.get("curr")
            stride = step.params.get("stride", 1)
            rollover = step.params.get("rollover", 16)
            res = assertions.assert_counter(prev, curr, stride, rollover)
            return res["passed"], res["details"]

        if kind == "mux_coverage":
            seen = step.params.get("seen", [])
            expected = step.params.get("expected", [])
            res = assertions.assert_mux_coverage(seen, expected)
            return res["passed"], res["details"]

        return False, f"Unknown assertion kind {kind}"
