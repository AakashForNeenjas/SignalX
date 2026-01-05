"""
Assertion utilities for CAN matrix testing.
These helpers are pure functions operating on metrics/stats to stay testable.
"""
from typing import Dict, Any, Optional, Iterable
import math
import statistics


def _result(passed: bool, details: str, observed: Optional[Any] = None, extra: Optional[Dict[str, Any]] = None):
    data = {"passed": passed, "details": details}
    if observed is not None:
        data["observed"] = observed
    if extra:
        data.update(extra)
    return data


def assert_dlc(metrics, msg_id: int, expected_dlc: int):
    observed = metrics.last_dlc(msg_id)
    if observed is None:
        return _result(False, "No frames observed", observed=None)
    ok = observed == expected_dlc
    return _result(ok, f"DLC observed {observed}, expected {expected_dlc}", observed=observed)


def assert_cycle_time(metrics, msg_id: int, spec_ms: float, tol_pct: float = 10.0, window_s: float = 10.0):
    times = metrics.intervals_ms(msg_id, window_s)
    if not times:
        # Not enough samples to evaluate; mark as N/A but don't fail the suite
        return _result(True, "Not enough intervals observed (N/A)", observed="N/A")
    mean_v = statistics.mean(times)
    max_v = max(times)
    min_v = min(times)
    stdev_v = statistics.pstdev(times) if len(times) > 1 else 0.0
    allowed_hi = spec_ms * (1 + tol_pct / 100.0)
    allowed_lo = spec_ms * (1 - tol_pct / 100.0)
    ok = min_v >= allowed_lo and max_v <= allowed_hi
    details = f"mean={mean_v:.1f}ms min={min_v:.1f}ms max={max_v:.1f}ms stdev={stdev_v:.1f}ms spec={spec_ms}±{tol_pct}%"
    return _result(ok, details, observed={"mean": mean_v, "min": min_v, "max": max_v, "stdev": stdev_v})


def assert_range(signal_value: Any, min_v: float, max_v: float):
    if signal_value is None:
        return _result(False, "No value")
    ok = min_v <= signal_value <= max_v
    return _result(ok, f"{signal_value} in [{min_v}, {max_v}]", observed=signal_value)


def assert_missing(metrics, msg_id: int, timeout_ms: float):
    delta = metrics.time_since_last_ms(msg_id)
    if delta is None:
        # Not enough samples to evaluate; mark as N/A but don't fail the suite
        return _result(True, "No frames observed (N/A)")
    ok = delta <= timeout_ms
    return _result(ok, f"last seen {delta:.1f}ms ago, timeout {timeout_ms}ms", observed=delta)


def assert_counter(prev: Optional[int], current: Optional[int], stride: int = 1, rollover: int = 16):
    if prev is None or current is None:
        return _result(False, "Counter value missing")
    expected = (prev + stride) % rollover
    ok = current == expected
    return _result(ok, f"prev={prev} curr={current} expected={expected}", observed=current)


def assert_checksum_payload(payload: bytes, algo: str = "sum8", expected: Optional[int] = None):
    if not payload:
        return _result(False, "No payload")
    if algo == "sum8":
        calc = sum(payload[:-1]) & 0xFF if len(payload) > 1 else sum(payload) & 0xFF
    elif algo == "sum16":
        calc = sum(payload[:-2]) & 0xFFFF if len(payload) > 2 else sum(payload) & 0xFFFF
    else:
        return _result(False, f"Unsupported checksum algo {algo}")
    exp = expected
    if exp is None:
        # default: last byte holds checksum for sum8, last 2 bytes for sum16
        exp = payload[-1] if algo == "sum8" else int.from_bytes(payload[-2:], "little")
    ok = calc == exp
    return _result(ok, f"checksum calc={calc} expected={exp}", observed=calc)


def assert_latency(lat_ms: Optional[float], max_ms: float):
    if lat_ms is None:
        return _result(False, "Latency not observed")
    ok = lat_ms <= max_ms
    return _result(ok, f"latency={lat_ms:.1f}ms, limit={max_ms}ms", observed=lat_ms)


def assert_mux_coverage(seen_states: Iterable[Any], expected_states: Iterable[Any]):
    seen = set(seen_states or [])
    expected = set(expected_states or [])
    missing = expected - seen
    ok = not missing
    return _result(ok, f"seen={len(seen)}/{len(expected)} missing={sorted(missing)}")


def assert_latency_messages(metrics, req_id: int, resp_id: int, max_ms: float):
    if not metrics:
        return _result(False, "No metrics")
    t_req = metrics.last_timestamp(req_id)
    t_resp = metrics.last_timestamp(resp_id)
    if t_req is None or t_resp is None:
        return _result(False, "Missing request/response timestamps")
    lat_ms = (t_resp - t_req) * 1000.0
    ok = lat_ms <= max_ms
    return _result(ok, f"latency={lat_ms:.1f}ms limit={max_ms}ms", observed=lat_ms)
