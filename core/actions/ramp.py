import json
import time
from datetime import datetime

from core.actions.params import parse_json_dict


def handle_ramp_action(action_name, params, ctx):
    """
    Generic ramp handler for GS/PS/CAN targets. Uses the same JSON schema
    defined in ACTION_DEFINITIONS.json.
    """
    try:
        data = parse_json_dict(params, default={}, strict=True)
    except Exception as e:
        return False, f"Invalid ramp params: {e}"

    target = data.get("target", {})
    if not isinstance(target, dict):
        return False, "Invalid target definition"

    target_type = str(target.get("type", "")).upper()
    start = float(data.get("start", 0.0))
    step = float(data.get("step", 1.0))
    end = float(data.get("end", 0.0))
    dwell = float(data.get("dwell", 0.5))
    tolerance = float(data.get("tolerance", 0.5))
    retries = int(data.get("retries", 2))
    verify = bool(data.get("verify", False))
    gs_voltage = data.get("gs_voltage", None)
    ps_voltage = data.get("ps_voltage", None)

    measure = data.get("measure", {}) or {}
    measure_gs = bool(measure.get("gs", True))
    measure_ps = bool(measure.get("ps", True))
    measure_load = bool(measure.get("load", True))

    gs = getattr(ctx.inst_mgr, "itech7900", None)
    ps = getattr(ctx.inst_mgr, "itech6006", None) or getattr(ctx.inst_mgr, "itech6000", None)
    load = getattr(ctx.inst_mgr, "dc_load", None)

    if target_type == "GS_FREQUENCY" and gs_voltage is None:
        return False, "GS_FREQUENCY requires gs_voltage"
    if target_type == "PS_CURRENT" and ps_voltage is not None and ps:
        try:
            ctx.log_cmd(f"PS VOLT {ps_voltage}")
            ps.set_voltage(float(ps_voltage))
        except Exception:
            return False, "Failed to set PS voltage limit"

    if step == 0:
        return False, "Step cannot be zero"

    if start <= end:
        points = []
        v = start
        while v <= end + 1e-9:
            points.append(round(v, 6))
            v += abs(step)
    else:
        points = []
        v = start
        while v >= end - 1e-9:
            points.append(round(v, 6))
            v -= abs(step)

    def set_target(val):
        if target_type == "GS_VOLT":
            if not gs:
                return False, "GS not initialized"
            ctx.log_cmd(f"GS VOLT {val}")
            gs.set_grid_voltage(float(val))
            return True, f"GS Voltage set to {val}"
        if target_type == "GS_FREQUENCY":
            if not gs:
                return False, "GS not initialized"
            ctx.log_cmd(f"GS VOLT {gs_voltage}")
            gs.set_grid_voltage(float(gs_voltage))
            ctx.log_cmd(f"GS FREQ {val}")
            gs.set_grid_frequency(float(val))
            return True, f"GS Frequency set to {val}"
        if target_type == "PS_VOLT":
            if not ps:
                return False, "PS not initialized"
            ctx.log_cmd(f"PS VOLT {val}")
            ps.set_voltage(float(val))
            return True, f"PS Voltage set to {val}"
        if target_type == "PS_CURRENT":
            if not ps:
                return False, "PS not initialized"
            ctx.log_cmd(f"PS CURR {val}")
            ps.set_current(float(val))
            return True, f"PS Current set to {val}"
        if target_type == "CAN_SIGNAL":
            if not ctx.can_mgr or not ctx.can_mgr.dbc_parser:
                return False, "CAN manager or DBC missing"
            msg_name = target.get("message")
            sig_name = target.get("signal")
            if not msg_name or not sig_name:
                return False, "Missing CAN message/signal"
            try:
                if hasattr(ctx.can_mgr, "apply_signal_override"):
                    ctx.can_mgr.apply_signal_override(msg_name, sig_name, val, refresh_cyclic=True)
                else:
                    ctx.can_mgr.send_message_with_overrides(msg_name, {sig_name: val})
                return True, f"CAN {msg_name}.{sig_name}={val}"
            except Exception as e:
                return False, f"CAN set failed: {e}"
        return False, "Unsupported target type"

    def measure_all():
        readings = {}
        if measure_gs:
            if not gs:
                readings["gs_error"] = "GS not initialized"
            else:
                gs_errors = []

                def _gs_try(key, func):
                    try:
                        readings[key] = func()
                    except Exception as e:
                        gs_errors.append(f"{key} failed: {e}")

                _gs_try("gs_voltage", gs.get_grid_voltage)
                _gs_try("gs_current", gs.get_grid_current)
                _gs_try("gs_power", gs.measure_power_real)
                _gs_try("gs_pf", gs.measure_power_factor)
                _gs_try("gs_ithd", gs.measure_thd_current)
                _gs_try("gs_vthd", gs.measure_thd_voltage)
                _gs_try("gs_freq", gs.get_grid_frequency)
                if readings.get("gs_power") is None:
                    v = readings.get("gs_voltage")
                    c = readings.get("gs_current")
                    if v is not None and c is not None:
                        readings["gs_power"] = v * c
                if readings.get("gs_pf") is None:
                    v = readings.get("gs_voltage")
                    c = readings.get("gs_current")
                    p = readings.get("gs_power")
                    app = v * c if v is not None and c is not None else None
                    if app:
                        readings["gs_pf"] = p / app if p is not None else None
                if gs_errors:
                    readings["gs_error"] = "; ".join(gs_errors)
        if measure_ps:
            if not ps:
                readings["ps_error"] = "PS not initialized"
            else:
                ps_errors = []

                def _ps_try(key, func):
                    try:
                        readings[key] = func()
                    except Exception as e:
                        ps_errors.append(f"{key} failed: {e}")

                _ps_try("ps_voltage", ps.get_voltage)
                _ps_try("ps_current", ps.get_current)
                ps_power_fn = getattr(ps, "get_power", None)
                if callable(ps_power_fn):
                    _ps_try("ps_power", ps_power_fn)
                else:
                    ps_errors.append("ps_power unsupported")
                if readings.get("ps_power") is None:
                    v = readings.get("ps_voltage")
                    c = readings.get("ps_current")
                    if v is not None and c is not None:
                        readings["ps_power"] = v * c
                if ps_errors:
                    readings["ps_error"] = "; ".join(ps_errors)
        if measure_load:
            if not load:
                readings["load_error"] = "Load not initialized"
            else:
                try:
                    lv, li = load.read_voltage_current()
                    readings["load_voltage"] = lv
                    readings["load_current"] = li
                    readings["load_power"] = lv * li if lv is not None and li is not None else None
                except Exception as e:
                    readings["load_error"] = f"Load measure failed: {e}"
        return readings

    logs = []
    for val in points:
        if ctx.stop_event.is_set() or not ctx.running:
            break
        ok, msg = set_target(val)
        if not ok:
            logs.append(
                {
                    "value": val,
                    "status": "fail",
                    "message": msg,
                    "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                }
            )
            return False, f"Ramp aborted at {val}: {msg}"

        if verify:
            verified = False
            for _ in range(retries + 1):
                try:
                    if target_type == "GS_VOLT" and gs:
                        rb = gs.get_grid_voltage()
                        if abs(rb - val) <= tolerance:
                            verified = True
                            break
                    if target_type == "GS_FREQUENCY" and gs:
                        rb = gs.get_grid_frequency()
                        if abs(rb - val) <= tolerance:
                            verified = True
                            break
                    if target_type == "PS_VOLT" and ps:
                        rb = ps.get_voltage()
                        if abs(rb - val) <= tolerance:
                            verified = True
                            break
                    if target_type == "PS_CURRENT" and ps:
                        rb = ps.get_current()
                        if abs(rb - val) <= tolerance:
                            verified = True
                            break
                    if target_type == "CAN_SIGNAL":
                        cache = getattr(ctx.can_mgr, "signal_cache", {})
                        sig = target.get("signal")
                        if cache.get(sig, {}).get("value") is not None:
                            verified = True
                            break
                except Exception:
                    pass
                time.sleep(0.1)
            if not verified:
                logs.append(
                    {
                        "value": val,
                        "status": "fail",
                        "message": "Verify failed",
                        "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                    }
                )
                return False, f"Verify failed at {val}"

        time.sleep(dwell)
        readings = measure_all()
        logs.append(
            {
                "value": val,
                "status": "ok",
                "readings": readings,
                "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
            }
        )

    try:
        payload = json.dumps(logs)
        ctx.emit_info(f"[RAMP_LOG]{payload}")
    except Exception:
        pass

    ctx.log(20, f"Ramp completed with {len(logs)} points")
    return True, f"Ramp completed ({len(logs)} points)"


def handle_line_load_action(action_name, params, ctx):
    """
    Nested GS/PS/DL sweep with measurements and tolerance checks.
    """
    try:
        cfg = parse_json_dict(params, default={}, strict=True)
    except Exception as e:
        return False, f"Invalid JSON params: {e}"

    gs_cfg = cfg.get("gs", {}) or {}
    ps_cfg = cfg.get("ps", {}) or {}
    dl_cfg = cfg.get("dl", {}) or {}
    verify = cfg.get("verify", {}) or {}
    retries = int(cfg.get("retries", 2))
    dl_reset = bool(cfg.get("dl_reset", True))
    abort_on_fail = bool(cfg.get("abort_on_fail", True))

    def _build_points(start, end, step, label):
        try:
            start = float(start)
            end = float(end)
            step = float(step)
        except Exception:
            raise ValueError(f"{label} values must be numeric")
        if step == 0:
            raise ValueError(f"{label} step cannot be zero")
        points = []
        if start <= end:
            step = abs(step)
            v = start
            while v <= end + 1e-9:
                points.append(round(v, 6))
                v += step
        else:
            step = -abs(step)
            v = start
            while v >= end - 1e-9:
                points.append(round(v, 6))
                v += step
        return points

    try:
        gs_points = _build_points(gs_cfg.get("start", 0), gs_cfg.get("end", 0), gs_cfg.get("step", 1), "GS")
        ps_points = _build_points(ps_cfg.get("start", 0), ps_cfg.get("end", 0), ps_cfg.get("step", 1), "PS")
        dl_points = _build_points(dl_cfg.get("start", 0), dl_cfg.get("end", 0), dl_cfg.get("step", 1), "DL")
    except Exception as e:
        return False, f"Line/Load params invalid: {e}"

    gs_dwell = float(gs_cfg.get("dwell", 0.5))
    ps_dwell = float(ps_cfg.get("dwell", 0.5))
    dl_dwell = float(dl_cfg.get("dwell", 0.5))
    gs_tol = float(gs_cfg.get("tolerance", 0.5))
    ps_tol = float(ps_cfg.get("tolerance", 0.5))
    dl_tol = float(dl_cfg.get("tolerance", 0.1))
    verify_gs = bool(verify.get("gs", True))
    verify_ps = bool(verify.get("ps", True))
    verify_dl = bool(verify.get("dl", True))

    gs = getattr(ctx.inst_mgr, "itech7900", None)
    ps = getattr(ctx.inst_mgr, "itech6006", None) or getattr(ctx.inst_mgr, "itech6000", None)
    load = getattr(ctx.inst_mgr, "dc_load", None)

    if not gs:
        return False, "GS not initialized"
    if not ps:
        return False, "PS not initialized"
    if not load:
        return False, "DC Load not initialized"

    def _verify_value(read_func, target, tol):
        last = None
        for _ in range(retries + 1):
            try:
                last = read_func()
            except Exception:
                last = None
            if last is not None and abs(last - target) <= tol:
                return True, last
            time.sleep(0.1)
        return False, last

    def _measure_all():
        readings = {}
        gs_errors = []
        ps_errors = []
        load_errors = []

        def _gs_try(key, func):
            try:
                readings[key] = func()
            except Exception as e:
                gs_errors.append(f"{key} failed: {e}")

        def _ps_try(key, func):
            try:
                readings[key] = func()
            except Exception as e:
                ps_errors.append(f"{key} failed: {e}")

        _gs_try("gs_voltage", gs.get_grid_voltage)
        _gs_try("gs_current", gs.get_grid_current)
        _gs_try("gs_power", gs.measure_power_real)
        _gs_try("gs_pf", gs.measure_power_factor)
        _gs_try("gs_ithd", gs.measure_thd_current)
        _gs_try("gs_vthd", gs.measure_thd_voltage)
        _gs_try("gs_freq", gs.get_grid_frequency)
        if readings.get("gs_power") is None:
            v = readings.get("gs_voltage")
            c = readings.get("gs_current")
            if v is not None and c is not None:
                readings["gs_power"] = v * c
        if readings.get("gs_pf") is None:
            v = readings.get("gs_voltage")
            c = readings.get("gs_current")
            p = readings.get("gs_power")
            app = v * c if v is not None and c is not None else None
            if app:
                readings["gs_pf"] = p / app if p is not None else None
        if gs_errors:
            readings["gs_error"] = "; ".join(gs_errors)

        _ps_try("ps_voltage", ps.get_voltage)
        _ps_try("ps_current", ps.get_current)
        ps_power_fn = getattr(ps, "get_power", None)
        if callable(ps_power_fn):
            _ps_try("ps_power", ps_power_fn)
        else:
            ps_errors.append("ps_power unsupported")
        if readings.get("ps_power") is None:
            v = readings.get("ps_voltage")
            c = readings.get("ps_current")
            if v is not None and c is not None:
                readings["ps_power"] = v * c
        if ps_errors:
            readings["ps_error"] = "; ".join(ps_errors)

        try:
            lv, li = load.read_voltage_current()
            readings["load_voltage"] = lv
            readings["load_current"] = li
            readings["load_power"] = lv * li if lv is not None and li is not None else None
        except Exception as e:
            load_errors.append(f"Load measure failed: {e}")
        if load_errors:
            readings["load_error"] = "; ".join(load_errors)
        return readings

    logs = []
    for gs_v in gs_points:
        if ctx.stop_event.is_set() or not ctx.running:
            break
        try:
            ctx.log_cmd(f"GS VOLT {gs_v}")
            gs.set_grid_voltage(gs_v)
            gs.power_on()
        except Exception as e:
            msg = f"GS set failed: {e}"
            logs.append(
                {
                    "gs_set": gs_v,
                    "ps_set": None,
                    "dl_set": None,
                    "status": "fail",
                    "message": msg,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            if abort_on_fail:
                return False, msg
            continue
        time.sleep(gs_dwell)
        if verify_gs:
            gs_ok, _ = _verify_value(gs.get_grid_voltage, gs_v, gs_tol)
            if not gs_ok:
                msg = f"GS verify failed at {gs_v}"
                logs.append(
                    {
                        "gs_set": gs_v,
                        "ps_set": None,
                        "dl_set": None,
                        "status": "fail",
                        "message": msg,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                if abort_on_fail:
                    return False, msg
                continue

        for ps_v in ps_points:
            if ctx.stop_event.is_set() or not ctx.running:
                break
            try:
                ctx.log_cmd(f"PS VOLT {ps_v}")
                ps.set_voltage(ps_v)
                ps.power_on()
            except Exception as e:
                msg = f"PS set failed: {e}"
                logs.append(
                    {
                        "gs_set": gs_v,
                        "ps_set": ps_v,
                        "dl_set": None,
                        "status": "fail",
                        "message": msg,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                if abort_on_fail:
                    return False, msg
                continue
            time.sleep(ps_dwell)
            if verify_ps:
                ps_ok, _ = _verify_value(ps.get_voltage, ps_v, ps_tol)
                if not ps_ok:
                    msg = f"PS verify failed at {ps_v}"
                    logs.append(
                        {
                            "gs_set": gs_v,
                            "ps_set": ps_v,
                            "dl_set": None,
                            "status": "fail",
                            "message": msg,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    if abort_on_fail:
                        return False, msg
                    continue

            for dl_i in dl_points:
                if ctx.stop_event.is_set() or not ctx.running:
                    break
                ok, msg = ctx.inst_mgr.dc_load_set_cc(dl_i)
                if not ok:
                    logs.append(
                        {
                            "gs_set": gs_v,
                            "ps_set": ps_v,
                            "dl_set": dl_i,
                            "status": "fail",
                            "message": msg,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    if abort_on_fail:
                        return False, msg
                    continue
                ok, msg = ctx.inst_mgr.dc_load_enable_input(True)
                if not ok:
                    logs.append(
                        {
                            "gs_set": gs_v,
                            "ps_set": ps_v,
                            "dl_set": dl_i,
                            "status": "fail",
                            "message": msg,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    if abort_on_fail:
                        return False, msg
                    continue
                time.sleep(dl_dwell)

                readings = _measure_all()
                gs_meas = readings.get("gs_voltage")
                ps_meas = readings.get("ps_voltage")
                dl_meas = readings.get("load_current")

                gs_ok = True if not verify_gs else (gs_meas is not None and abs(gs_meas - gs_v) <= gs_tol)
                ps_ok = True if not verify_ps else (ps_meas is not None and abs(ps_meas - ps_v) <= ps_tol)
                dl_ok = True if not verify_dl else (dl_meas is not None and abs(dl_meas - dl_i) <= dl_tol)
                status = "ok" if (gs_ok and ps_ok and dl_ok) else "fail"
                message = ""
                if status != "ok":
                    issues = []
                    if not gs_ok:
                        issues.append("GS tolerance")
                    if not ps_ok:
                        issues.append("PS tolerance")
                    if not dl_ok:
                        issues.append("DL tolerance")
                    message = "Verify failed: " + ", ".join(issues)

                logs.append(
                    {
                        "gs_set": gs_v,
                        "ps_set": ps_v,
                        "dl_set": dl_i,
                        "status": status,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                        "checks": {"gs_ok": gs_ok, "ps_ok": ps_ok, "dl_ok": dl_ok},
                        "readings": readings,
                    }
                )

                if status != "ok" and abort_on_fail:
                    return False, message or "Line/Load verification failed"

            if dl_reset:
                ctx.inst_mgr.dc_load_enable_input(False)

    try:
        payload = json.dumps(logs)
        ctx.emit_info(f"[LINELOAD_LOG]{payload}")
    except Exception:
        pass

    ctx.log(20, f"Line/Load regulation completed with {len(logs)} points")
    return True, f"Line/Load regulation completed ({len(logs)} points)"
