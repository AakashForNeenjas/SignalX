import json
import time

from core.actions.params import parse_json_dict, parse_number


def handle_ps(action_name, params, ctx):
    if not hasattr(ctx.inst_mgr, "itech6000") or ctx.inst_mgr.itech6000 is None:
        msg = "PS action failed: PS not initialized"
        print(msg)
        return False, msg

    ps = ctx.inst_mgr.itech6000

    if "Connect" in action_name:
        ctx.log_cmd("PS CONNECT")
        if getattr(ps, "connected", False):
            msg = "PS Connect: already connected, reusing session"
            print(msg)
            return True, msg
        s, m = ps.connect()
        msg = f"PS Connect: {m}"
        print(msg)
        return s, msg

    if "Disconnect" in action_name:
        ctx.log_cmd("PS DISCONNECT")
        ps.disconnect()
        msg = "PS Disconnected"
        print(msg)
        return True, msg

    if "Output" in action_name:
        if "ON" in action_name:
            ps.power_on()
            msg = "PS Output ON"
        else:
            ps.power_off()
            msg = "PS Output OFF"
        print(msg)
        return True, msg

    if "Measure VI" in action_name:
        v, i = ps.measure_vi()
        msg = f"PS Measure VI: V={v}V I={i}A"
        print(msg)
        return True, msg

    if "Measure Voltage, Current, Power" in action_name:
        v, i, p = ps.measure_power_vi()
        msg = f"PS Measure VIP: V={v}V I={i}A P={p}W"
        print(msg)
        return True, msg

    if "Set Voltage" in action_name:
        val = parse_number(params, default=0.0, key="voltage")
        ctx.log_cmd(f"PS VOLT {val}")
        ps.set_voltage(val)
        msg = f"PS Set Voltage: {val}V"
        print(msg)
        return True, msg

    if "Set Current" in action_name:
        val = parse_number(params, default=0.0, key="current")
        ctx.log_cmd(f"PS CURR {val}")
        ps.set_current(val)
        msg = f"PS Set Current: {val}A"
        print(msg)
        return True, msg

    if "Ramp Up" in action_name or "Ramp Down" in action_name:
        data = parse_json_dict(params, default={}, strict=False)
        start = data.get("start", None)
        step = data.get("step", 1.0)
        end = data.get("end", None)
        delay = data.get("delay", data.get("dwell", 0.5))
        tolerance = data.get("tolerance", 0.5)
        retries = int(data.get("retries", 3))

        if "Ramp Up" in action_name:
            try:
                try:
                    measured_start = ps.get_voltage()
                except Exception:
                    measured_start = 0.0
                if start is None:
                    start = measured_start
                if end is None:
                    end = measured_start
                if end < start:
                    msg = f"PS Ramp Up failed: end ({end}) < start ({start})"
                    print(msg)
                    return False, msg
                current = start
                steps_executed = 0
                last_measured = measured_start
                while current <= end and (ctx.running or ctx.current_index is not None):
                    ps.set_voltage(float(current))
                    time.sleep(0.1)
                    success_local = False
                    for _ in range(retries + 1):
                        try:
                            last_measured = ps.get_voltage()
                        except Exception:
                            pass
                        if abs(last_measured - current) <= tolerance:
                            success_local = True
                            break
                        ps.set_voltage(float(current))
                        time.sleep(0.1)
                    steps_executed += 1
                    msg = f"PS RampUp step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                    print(msg)
                    ctx.emit_info(msg)
                    if not ctx.running and ctx.current_index is None:
                        break
                    time.sleep(delay)
                    current += abs(step)
                final_msg = f"PS RampUp complete: steps={steps_executed}, final_meas={last_measured}V"
                print(final_msg)
                return True, final_msg
            except Exception as e:
                msg = f"PS RampUp failed: {e}"
                print(msg)
                return False, msg

        if "Ramp Down" in action_name:
            try:
                try:
                    measured_start = ps.get_voltage()
                except Exception:
                    measured_start = 0.0
                if start is None:
                    start = measured_start
                if end is None:
                    end = measured_start
                if end > start:
                    msg = f"PS Ramp Down failed: end ({end}) > start ({start})"
                    print(msg)
                    return False, msg
                current = start
                steps_executed = 0
                last_measured = measured_start
                while current >= end and (ctx.running or ctx.current_index is not None):
                    ps.set_voltage(float(current))
                    time.sleep(0.1)
                    success_local = False
                    for _ in range(retries + 1):
                        try:
                            last_measured = ps.get_voltage()
                        except Exception:
                            pass
                        if abs(last_measured - current) <= tolerance:
                            success_local = True
                            break
                        ps.set_voltage(float(current))
                        time.sleep(0.1)
                    steps_executed += 1
                    msg = f"PS RampDown step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                    print(msg)
                    ctx.emit_info(msg)
                    if not ctx.running and ctx.current_index is None:
                        break
                    time.sleep(delay)
                    current -= abs(step)
                final_msg = f"PS RampDown complete: steps={steps_executed}, final_meas={last_measured}V"
                print(final_msg)
                return True, final_msg
            except Exception as e:
                msg = f"PS RampDown failed: {e}"
                print(msg)
                return False, msg

    if "Battery Set Charge" in action_name:
        try:
            data = parse_json_dict(params, default={}, strict=True)
            voltage = float(data.get("voltage"))
            current = float(data.get("current"))
            ps.battery_set_charge(voltage, current)
            msg = f"PS Battery Set Charge: V={voltage}V I={current}A"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Battery Set Charge failed: {e}"
            print(msg)
            return False, msg

    if "Battery Set Discharge" in action_name:
        try:
            data = parse_json_dict(params, default={}, strict=True)
            voltage = float(data.get("voltage"))
            current = float(data.get("current"))
            ps.battery_set_discharge(voltage, current)
            msg = f"PS Battery Set Discharge: V={voltage}V I={current}A"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Battery Set Discharge failed: {e}"
            print(msg)
            return False, msg

    if "Read Errors" in action_name:
        try:
            resp = ps.read_errors()
            msg = f"PS Error Status: {resp}"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Read Errors failed: {e}"
            print(msg)
            return False, msg

    if "Clear Errors" in action_name:
        try:
            ps.clear_errors()
            msg = "PS Clear Errors"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Clear Errors failed: {e}"
            print(msg)
            return False, msg

    if "Sweep Voltage" in action_name:
        try:
            d = parse_json_dict(params, default={}, strict=True)
            start = d.get("start")
            step = d.get("step")
            end = d.get("end")
            delay = d.get("delay", d.get("dwell", 0.5))
            log_file = d.get("log_file")
            measure = d.get("measure", {}) or {}
            measure_gs = bool(measure.get("gs", True))
            measure_ps = bool(measure.get("ps", True))
            measure_load = bool(measure.get("load", True))
            gs = getattr(ctx.inst_mgr, "itech7900", None)
            load = getattr(ctx.inst_mgr, "dc_load", None)

            def _measure_all():
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

            def _build_points(start_val, end_val, step_val):
                start_val = float(start_val)
                end_val = float(end_val)
                step_val = float(step_val)
                if step_val == 0:
                    raise ValueError("Step cannot be zero")
                points = []
                if start_val <= end_val:
                    v = start_val
                    step_val = abs(step_val)
                    while v <= end_val + 1e-9:
                        points.append(round(v, 6))
                        v += step_val
                else:
                    v = start_val
                    step_val = abs(step_val)
                    while v >= end_val - 1e-9:
                        points.append(round(v, 6))
                        v -= step_val
                return points

            points = _build_points(start, end, step)
            logs = []
            csv_rows = []
            for v in points:
                if ctx.stop_event.is_set() or not ctx.running:
                    break
                try:
                    ctx.log_cmd(f"PS VOLT {v}")
                    ps.set_voltage(float(v))
                except Exception as e:
                    msg = f"PS Sweep Voltage set failed at {v}: {e}"
                    logs.append(
                        {
                            "value": v,
                            "status": "fail",
                            "message": msg,
                            "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                        }
                    )
                    return False, msg
                time.sleep(delay)
                readings = _measure_all()
                logs.append(
                    {
                        "value": v,
                        "status": "ok",
                        "message": "",
                        "readings": readings,
                        "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                    }
                )
                csv_rows.append((v, readings.get("ps_voltage"), readings.get("ps_current")))

            if log_file:
                try:
                    import csv
                    with open(log_file, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(["set_v", "meas_v", "meas_i"])
                        for row in csv_rows:
                            writer.writerow(row)
                except Exception:
                    pass

            try:
                payload = json.dumps(logs)
                ctx.emit_info(f"[RAMP_LOG]{payload}")
            except Exception:
                pass

            msg = f"PS Sweep Voltage logged {len(logs)} points"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Sweep Voltage failed: {e}"
            print(msg)
            return False, msg

    if "Sweep Current" in action_name:
        try:
            d = parse_json_dict(params, default={}, strict=True)
            start = d.get("start")
            step = d.get("step")
            end = d.get("end")
            delay = d.get("delay", d.get("dwell", 0.5))
            log_file = d.get("log_file")
            ps_voltage = d.get("ps_voltage")
            measure = d.get("measure", {}) or {}
            measure_gs = bool(measure.get("gs", True))
            measure_ps = bool(measure.get("ps", True))
            measure_load = bool(measure.get("load", True))
            gs = getattr(ctx.inst_mgr, "itech7900", None)
            load = getattr(ctx.inst_mgr, "dc_load", None)

            if ps_voltage is not None:
                try:
                    ctx.log_cmd(f"PS VOLT {ps_voltage}")
                    ps.set_voltage(float(ps_voltage))
                except Exception:
                    return False, "Failed to set PS voltage limit"

            def _measure_all():
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

            def _build_points(start_val, end_val, step_val):
                start_val = float(start_val)
                end_val = float(end_val)
                step_val = float(step_val)
                if step_val == 0:
                    raise ValueError("Step cannot be zero")
                points = []
                if start_val <= end_val:
                    v = start_val
                    step_val = abs(step_val)
                    while v <= end_val + 1e-9:
                        points.append(round(v, 6))
                        v += step_val
                else:
                    v = start_val
                    step_val = abs(step_val)
                    while v >= end_val - 1e-9:
                        points.append(round(v, 6))
                        v -= step_val
                return points

            points = _build_points(start, end, step)
            logs = []
            csv_rows = []
            for v in points:
                if ctx.stop_event.is_set() or not ctx.running:
                    break
                try:
                    ctx.log_cmd(f"PS CURR {v}")
                    ps.set_current(float(v))
                except Exception as e:
                    msg = f"PS Sweep Current set failed at {v}: {e}"
                    logs.append(
                        {
                            "value": v,
                            "status": "fail",
                            "message": msg,
                            "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                        }
                    )
                    return False, msg
                time.sleep(delay)
                readings = _measure_all()
                logs.append(
                    {
                        "value": v,
                        "status": "ok",
                        "message": "",
                        "readings": readings,
                        "measure": {"gs": measure_gs, "ps": measure_ps, "load": measure_load},
                    }
                )
                csv_rows.append((v, readings.get("ps_voltage"), readings.get("ps_current")))

            if log_file:
                try:
                    import csv
                    with open(log_file, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(["set_i", "meas_v", "meas_i"])
                        for row in csv_rows:
                            writer.writerow(row)
                except Exception:
                    pass

            try:
                payload = json.dumps(logs)
                ctx.emit_info(f"[RAMP_LOG]{payload}")
            except Exception:
                pass

            msg = f"PS Sweep Current logged {len(logs)} points"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Sweep Current failed: {e}"
            print(msg)
            return False, msg

    msg = f"Unsupported PS action: {action_name}"
    print(msg)
    return False, msg
