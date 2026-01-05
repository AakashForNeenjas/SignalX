
import time
from canmatrix.models import TestResult
from canmatrix.steps import EXECUTORS
from canmatrix.models import TestSuite, TestCase, TestStep, Assertion, StepType
from canmatrix.metrics import CanBusMetrics
from canmatrix import assertions as assertion_lib
import re
from canmatrix.helpers import detect_counter_checksum as _detect_counter_checksum, detect_mux_states, detect_plausibility_pairs
from canmatrix.req_resp_detector import detect_req_resp_pairs


class TestContext:
    def __init__(self, can_if, dbc_mgr, logger, can_mgr=None, signal_manager=None, metrics=None):
        self.can_if = can_if
        self.dbc_mgr = dbc_mgr
        self.logger = logger
        self.can_mgr = can_mgr
        self.signal_manager = signal_manager
        self.metrics = metrics
        self.log = logger or self

    def info(self, msg):
        if hasattr(self.logger, "info"):
            try:
                self.logger.info(msg)
            except Exception:
                pass
        else:
            print(msg)


class TestExecutor:
    def __init__(self, case, can_if, dbc_mgr, logger, can_mgr=None, signal_manager=None, metrics=None):
        self.case = case
        self.ctx = TestContext(can_if, dbc_mgr, logger, can_mgr=can_mgr, signal_manager=signal_manager, metrics=metrics)
        # Build maps of DBC choices for quick lookup: name -> choices and reverse lookup
        self._choice_map = {}
        self._choice_reverse = {}
        if dbc_mgr and getattr(dbc_mgr, "db", None):
            for msg in dbc_mgr.db.messages:
                for sig in msg.signals:
                    self._build_choice_for_signal(sig.name, sig_obj=sig)

    def run(self):
        start = time.time()
        logs = []
        assertion_results = []
        try:
            # Execute preconditions
            for step in self.case.preconditions:
                s, m = self._exec_step(step)
                logs.append(m)
                if not s:
                    raise RuntimeError(m)
            # Execute main
            for step in self.case.main_steps:
                s, m = self._exec_step(step)
                logs.append(m)
                if not s:
                    raise RuntimeError(m)
            # Execute postconditions
            for step in self.case.postconditions:
                s, m = self._exec_step(step)
                logs.append(m)
            # Evaluate assertions against current cache
            assertion_results = self._eval_assertions()
            passed = all(ar.get("passed", False) for ar in assertion_results) if assertion_results else True
            if not passed:
                for ar in assertion_results:
                    if not ar.get("passed", False):
                        logs.append(f"Assertion failed: {ar}")
        except Exception as e:
            passed = False
            logs.append(f"Error: {e}")
        end = time.time()
        return TestResult(
            case_id=self.case.id,
            passed=passed,
            log=logs,
            start_ts=start,
            end_ts=end,
            assertions=assertion_results
        )

    def _build_choice_for_signal(self, sig_name, sig_obj=None):
        """
        Build reverse/forward choice maps for a specific signal on demand.
        This ensures we can recover even if a previous init missed entries.
        """
        if sig_name in self._choice_reverse:
            return
        sig = sig_obj
        if sig is None and self.ctx and getattr(self.ctx, "dbc_mgr", None) and getattr(self.ctx.dbc_mgr, "db", None):
            for msg in self.ctx.dbc_mgr.db.messages:
                for s in msg.signals:
                    if s.name == sig_name:
                        sig = s
                        break
                if sig:
                    break
        if sig and getattr(sig, "choices", None):
            try:
                choices = dict(sig.choices)
            except Exception:
                return
            self._choice_map[sig_name] = choices
            rev = {}
            for code, text in choices.items():
                try:
                    norm_text = re.sub(r"[^a-z0-9]+", "", str(text).strip().lower())
                    rev[norm_text] = code
                    rev[str(code)] = code
                except Exception:
                    continue
            if rev:
                self._choice_reverse[sig_name] = rev

    def _exec_step(self, step):
        exec_cls = EXECUTORS.get(step.type.value if hasattr(step.type, "value") else step.type)
        if not exec_cls:
            return False, f"No executor for {step.type}"
        executor = exec_cls()
        return executor.execute(step, self.ctx)

    def _read_signal(self, sig_name):
        if self.ctx.can_mgr and hasattr(self.ctx.can_mgr, "signal_cache"):
            try:
                cache = self.ctx.can_mgr.signal_cache.get(sig_name, {})
                # Prefer raw_value (numeric) when available for reliable comparisons
                if "raw_value" in cache:
                    return cache.get("raw_value")
                return cache.get("value")
            except Exception:
                pass
        if self.ctx.signal_manager and hasattr(self.ctx.signal_manager, "signal_cache"):
            try:
                cache = self.ctx.signal_manager.signal_cache.get(sig_name, {})
                if "raw_value" in cache:
                    return cache.get("raw_value")
                return cache.get("value")
            except Exception:
                pass
        return None

    def _coerce_choice(self, val, target):
        """
        Normalize DBC choice strings (e.g., 'Enable'/'Disable', 'ERROR'/'No Error')
        to their numeric codes when possible using the DBC choices for the signal.
        """
        if isinstance(val, str):
            def _norm(s: str):
                # fold case and strip non-alnum so "No Error", "no_error", "NO-ERROR" all match
                return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())

            low = _norm(val)
            # Try DBC choices lookup by signal name
            sig_name = None
            if target and isinstance(target, str):
                if target.startswith("signal:"):
                    sig_name = target.split("signal:")[-1]
                elif "." in target:
                    sig_name = target.split(".")[-1]
            # Lazy rebuild if missing for this signal
            if sig_name and sig_name not in self._choice_reverse and self.ctx and getattr(self.ctx, "dbc_mgr", None):
                self._build_choice_for_signal(sig_name)
            if sig_name and sig_name in self._choice_reverse:
                rev = self._choice_reverse.get(sig_name, {})
                if low in rev:
                    return rev[low]
                # Secondary lookup against the forward choice map (in case reverse map missed a variant)
                choices = self._choice_map.get(sig_name, {})
                for code, text in choices.items():
                    try:
                        if low == re.sub(r"[^a-z0-9]+", "", str(text).strip().lower()):
                            return code
                    except Exception:
                        continue
            # Minimal generic fallback for boolean-style strings when DBC choices are absent
            if low in ("enable", "enabled", "true", "on", "error", "yes", "active", "connected", "present", "authenticated", "available"):
                return 1
            if low in ("disable", "disabled", "false", "off", "noerror", "noerr", "no", "inactive", "disconnected", "notconnected", "notpresent", "notauthenticated", "notavailable"):
                return 0
        return val

    def _check_op(self, val, expected, op, tol=0.0, target=None):
        # Normalize choice strings to numeric for comparisons
        val = self._coerce_choice(val, target)
        if isinstance(expected, (list, tuple)) and len(expected) == 2:
            expected = (self._coerce_choice(expected[0], target), self._coerce_choice(expected[1], target))
        if op in ("exists", "not_none"):
            return val is not None
        try:
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

    def _eval_assertions(self):
        results = []
        # keep simple prev counter state across assertions within a case run
        counter_state = getattr(self, "_counter_state", {})
        for a in self.case.assertions:
            val = None
            target = a.target
            # DBC-backed assertions (static definition checks)
            if target.startswith("dbc_msg:") and self.ctx.dbc_mgr and getattr(self.ctx.dbc_mgr, "db", None):
                try:
                    _, msg_name, field = target.split(":", 2)
                    msg = self.ctx.dbc_mgr.db.get_message_by_name(msg_name)
                    if field == "dlc":
                        val = msg.length if hasattr(msg, "length") else msg.size
                    elif field == "signal_count":
                        val = len(msg.signals)
                except Exception:
                    val = None
            elif target.endswith(".dlc") and self.ctx.dbc_mgr and getattr(self.ctx.dbc_mgr, "db", None):
                try:
                    msg_name = target.replace(".dlc", "")
                    msg = self.ctx.dbc_mgr.db.get_message_by_name(msg_name)
                    val = msg.length if hasattr(msg, "length") else msg.size
                except Exception:
                    val = None
            elif target.startswith("signal:"):
                sig_name = target.split("signal:")[-1]
                val = self._read_signal(sig_name)
            elif "." in target:
                sig_name = target.split(".")[-1]
                val = self._read_signal(sig_name)
            else:
                val = self._read_signal(target)
            # Assertion kind-specific evaluation
            if a.kind == "cycle_time" and self.ctx.metrics:
                try:
                    arb_id = int(target, 0) if isinstance(target, str) and target.startswith("0x") else int(target)
                except Exception:
                    arb_id = None
                if arb_id is not None:
                    res = assertion_lib.assert_cycle_time(self.ctx.metrics, arb_id, a.expected, a.tolerance or 0.0)
                    ok = res["passed"]
                    val = res.get("observed") if res.get("observed") is not None else res.get("message")
                else:
                    ok = False
            elif a.kind == "dlc" and self.ctx.metrics:
                try:
                    arb_id = int(target, 0) if isinstance(target, str) and target.startswith("0x") else int(target)
                except Exception:
                    arb_id = None
                if arb_id is not None:
                    res = assertion_lib.assert_dlc(self.ctx.metrics, arb_id, a.expected)
                    ok = res["passed"]
                    val = res.get("observed")
                else:
                    ok = False
            elif a.kind == "missing" and self.ctx.metrics:
                try:
                    arb_id = int(target, 0) if isinstance(target, str) and target.startswith("0x") else int(target)
                except Exception:
                    arb_id = None
                if arb_id is not None:
                    res = assertion_lib.assert_missing(self.ctx.metrics, arb_id, a.expected)
                    ok = res["passed"]
                    val = res.get("observed")
                else:
                    ok = False
            elif a.kind == "checksum" and self.ctx.metrics:
                try:
                    arb_id = int(target, 0) if isinstance(target, str) and target.startswith("0x") else int(target)
                except Exception:
                    arb_id = None
                payload = self.ctx.metrics.last_payload(arb_id) if arb_id is not None else None
                res = assertion_lib.assert_checksum_payload(payload, algo=a.op if a.op else "sum8", expected=a.expected if isinstance(a.expected, int) else None)
                ok = res["passed"]
                val = res.get("observed")
            elif a.kind == "counter":
                prev = counter_state.get(target)
                curr = val
                # if not yet read, attempt from signal cache
                if curr is None and target.startswith("signal:"):
                    sig_name = target.split("signal:")[-1]
                    curr = self._read_signal(sig_name)
                    val = curr
                res = assertion_lib.assert_counter(prev, curr, stride=int(a.tolerance or 1), rollover=int(a.expected or 16))
                ok = res["passed"]
                counter_state[target] = curr
            elif a.kind == "range":
                ok = self._check_op(val, a.expected, a.op, a.tolerance or 0.0, target=a.target)
            elif a.kind == "latency" and self.ctx.metrics:
                try:
                    if "->" in target:
                        req_str, resp_str = target.split("->", 1)
                        req_id = int(req_str, 0)
                        resp_id = int(resp_str, 0)
                    else:
                        req_id = resp_id = int(target, 0)
                except Exception:
                    req_id = resp_id = None
                if req_id is not None and resp_id is not None:
                    res = assertion_lib.assert_latency_messages(self.ctx.metrics, req_id, resp_id, a.expected)
                    ok = res["passed"]
                    val = res.get("observed")
                else:
                    ok = False
            elif a.kind == "mux_coverage" and self.ctx.metrics:
                states = self.ctx.metrics.mux_states(target.replace("mux:", "")) if hasattr(self.ctx.metrics, "mux_states") else set()
                res = assertion_lib.assert_mux_coverage(states, a.expected)
                ok = res["passed"]
                val = list(states)
            elif a.kind == "plausibility":
                try:
                    left, right = target.split("|", 1)
                except Exception:
                    left = right = None
                a_val = self._read_signal(left) if left else None
                b_val = self._read_signal(right) if right else None
                tol_pct = float(a.expected) if a.expected is not None else 20.0
                if a_val is None or b_val is None:
                    ok = False
                else:
                    maxv = max(abs(a_val), abs(b_val), 1e-6)
                    diff = abs(a_val - b_val)
                    ok = (diff / maxv) * 100.0 <= tol_pct
                    val = {"diff_pct": (diff / maxv) * 100.0, "a": a_val, "b": b_val}
            else:
                ok = self._check_op(val, a.expected, a.op, a.tolerance or 0.0, target=a.target)
            results.append({"target": a.target, "op": a.op, "expected": a.expected, "value": val, "passed": ok, "msg": a.message})
        self._counter_state = counter_state
        return results


class TestRunner:
    def __init__(self, can_if, dbc_mgr, logger=None, can_mgr=None, signal_manager=None):
        self.can_if = can_if
        self.dbc_mgr = dbc_mgr
        self.logger = logger
        self.can_mgr = can_mgr
        self.signal_manager = signal_manager
        self.metrics = None
        self._metrics_listener = None
        if self.can_mgr:
            self.metrics = CanBusMetrics(dbc_mgr=self.dbc_mgr)
            try:
                self._metrics_listener = self.metrics.attach(self.can_mgr)
            except Exception:
                self.metrics = None

    def run_suite(self, suite, cases=None):
        results = []
        selected = cases or suite.cases
        for case in selected:
            exec_ = TestExecutor(case, self.can_if, self.dbc_mgr, self.logger, can_mgr=self.can_mgr, signal_manager=self.signal_manager, metrics=self.metrics)
            res = exec_.run()
            results.append(res)
        # detach metrics listener
        if self._metrics_listener and self.metrics and self.can_mgr:
            self.metrics.detach(self.can_mgr, self._metrics_listener)
        return results


def build_auto_suite_from_dbc(dbc_mgr):
    """
    Build an auto-generated suite with static + dynamic checks for every DBC message.
    Static: validate DBC definition (DLC, signal count) without live traffic.
    Dynamic: wait for one frame of the message and assert a few signals got decoded.
    """
    if not dbc_mgr or not getattr(dbc_mgr, "db", None):
        return TestSuite(name="AutoSuite", cases=[])
    cases = []
    validations = dbc_mgr.validate_messages() if hasattr(dbc_mgr, "validate_messages") else []
    warnings_by_msg = {v["message"]: v.get("warnings", []) for v in validations}
    calc_len_by_msg = {v["message"]: v.get("calc_len") for v in validations}
    messages = list(dbc_mgr.db.messages)
    req_resp_pairs = detect_req_resp_pairs(messages)
    for msg in messages:
        sig_names = [s.name for s in msg.signals]
        sig_desc = ", ".join(sig_names) if sig_names else "no signals"
        dlc_val = getattr(msg, "length", None)
        if dlc_val is None and hasattr(msg, "size"):
            dlc_val = msg.size
        # ----- Static definition check -----
        static_case = TestCase(
            id=f"ST-{msg.name}",
            name=f"Static Check {msg.name}",
            description=f"Static definition check for {msg.name} signals: {sig_desc}",
            tags=["static"],
            assertions=[
                Assertion(target=f"dbc_msg:{msg.name}:dlc", op="==", expected=dlc_val, message="DBC DLC matches definition"),
                Assertion(target=f"dbc_msg:{msg.name}:signal_count", op="==", expected=len(sig_names), message="Signal count matches DBC")
            ]
        )
        calc_len = calc_len_by_msg.get(msg.name)
        if calc_len:
            # Pass if required bytes fit within DLC (DLC >= required), not strict equality
            static_case.assertions.append(
                Assertion(target=f"dbc_msg:{msg.name}:dlc", op=">=", expected=calc_len, message=f"Signal packing fits in DLC (needs {calc_len} bytes)")
            )
        if warnings_by_msg.get(msg.name):
            static_case.description += f" | Warnings: {warnings_by_msg[msg.name]}"
        cases.append(static_case)
        # ----- Dynamic check (lightweight) -----
        # Use a timeout derived from cycle_time when available to avoid timing out on slow cyclic frames.
        cycle_spec = getattr(msg, "cycle_time", None)
        base_timeout_ms = 2000
        if cycle_spec:
            base_timeout_ms = max(base_timeout_ms, int(cycle_spec * 2))
        dyn_steps = [
            TestStep(type=StepType.WAIT_FOR_MESSAGE, params={"message": msg.name, "timeout_ms": base_timeout_ms, "expected_dlc": dlc_val})
        ]
        dyn_asserts = []
        # Assert DLC observed on bus
        dyn_asserts.append(
            Assertion(target=f"{hex(msg.frame_id)}", op="==", expected=dlc_val, kind="dlc", message="DLC observed on bus")
        )
        # Assert cycle time if specified in DBC
        if cycle_spec:
            # Give metrics time to collect multiple frames for timing; ensure at least ~3 cycles.
            extra_wait = max(2000, int(cycle_spec * 3))
            dyn_steps.append(TestStep(type=StepType.WAIT_TIME, params={"ms": extra_wait}))
            dyn_asserts.append(
                Assertion(
                    target=f"{hex(msg.frame_id)}",
                    op="==",
                    expected=cycle_spec,
                    kind="cycle_time",
                    # Use 20% tolerance (or at least 20ms) to account for bus/OS jitter
                    tolerance=max(20.0, cycle_spec * 0.2),
                    message="Cycle time within tolerance"
                )
            )
            # Missing message timeout at 3x spec as a heuristic
            dyn_asserts.append(
                Assertion(target=f"{hex(msg.frame_id)}", op="<=", expected=cycle_spec * 3, kind="missing", message="No missing frame beyond timeout")
            )
        for sig in msg.signals:
            dyn_asserts.append(Assertion(target=f"signal:{sig.name}", op="not_none", expected=0, message=f"{sig.name} observed on bus"))
            # Range check if min/max defined
            if getattr(sig, "minimum", None) is not None and getattr(sig, "maximum", None) is not None:
                dyn_asserts.append(
                    Assertion(
                        target=f"signal:{sig.name}",
                        op="in_range",
                        expected=(sig.minimum, sig.maximum),
                        kind="range",
                        message=f"{sig.name} within [{sig.minimum}, {sig.maximum}]"
                    )
                )
        # Auto-detect counters and checksums by naming heuristics and placement
        counters, checksums = _detect_counter_checksum(msg, dlc_val)
        for c in counters:
            dyn_asserts.append(
                Assertion(
                    target=f"signal:{c['signal']}",
                    op="==",
                    expected=c["rollover"],
                    tolerance=c["stride"],
                    kind="counter",
                    message=f"Counter {c['signal']} stride {c['stride']} rollover {c['rollover']}"
                )
            )
        for chk in checksums:
            dyn_asserts.append(
                Assertion(
                    target=f"{hex(msg.frame_id)}",
                    op=chk["algo"],
                    expected=None,
                    kind="checksum",
                    message=f"Checksum ({chk['algo']})"
                )
            )
        # Request/response latency if paired
        for pair in req_resp_pairs:
            if pair["req_name"] == msg.name:
                try:
                    resp = dbc_mgr.db.get_message_by_name(pair["resp_name"])
                    dyn_asserts.append(
                        Assertion(
                            target=f"{hex(msg.frame_id)}->{hex(resp.frame_id)}",
                            op="==",
                            expected=200.0,  # default max latency ms
                            kind="latency",
                            message=f"Latency {msg.name}->{resp.name} <= 200ms"
                        )
                    )
                except Exception:
                    pass
        # Multiplexed coverage
        mux_states = detect_mux_states(msg)
        if mux_states:
            dyn_asserts.append(
                Assertion(
                    target=f"mux:{msg.name}",
                    op="==",
                    expected=mux_states,
                    kind="mux_coverage",
                    message=f"Observed mux states for {msg.name}"
                )
            )
        # Plausibility pairs
        plaus_pairs = detect_plausibility_pairs(msg)
        for p in plaus_pairs:
            dyn_asserts.append(
                Assertion(
                    target=f"{p['a']}|{p['b']}",
                    op="==",
                    expected=p["tol_pct"],
                    kind="plausibility",
                    message=f"Plausibility {p['a']} vs {p['b']} <= {p['tol_pct']}% diff"
                )
            )
        dyn_case = TestCase(
            id=f"DYN-{msg.name}",
            name=f"Dynamic Check {msg.name}",
            description=f"Dynamic placeholder for {msg.name} signals: {sig_desc}",
            tags=["dynamic"],
            main_steps=dyn_steps,
            assertions=dyn_asserts
        )
        cases.append(dyn_case)
    return TestSuite(name="Automated CAN Matrix Test Suite", cases=cases)
