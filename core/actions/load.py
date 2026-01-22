import json
import time

from core.actions.params import parse_json_dict, parse_number


def _pulse_cycle_summary(cycle, total, pulse_s, dwell_s):
    return f"Short cycle {cycle}/{total}: pulse {pulse_s:.3f}s, dwell {dwell_s:.3f}s"

def _measure_cycle_readings(ps, load, gs=None, measure_gs=False):
    readings = {}
    errors = []
    if ps:
        try:
            readings["ps_voltage"] = ps.get_voltage()
        except Exception as exc:
            errors.append(f"ps_voltage failed: {exc}")
        try:
            readings["ps_current"] = ps.get_current()
        except Exception as exc:
            errors.append(f"ps_current failed: {exc}")
        ps_power_fn = getattr(ps, "get_power", None)
        if callable(ps_power_fn):
            try:
                readings["ps_power"] = ps_power_fn()
            except Exception as exc:
                errors.append(f"ps_power failed: {exc}")
        if readings.get("ps_power") is None:
            v = readings.get("ps_voltage")
            c = readings.get("ps_current")
            if v is not None and c is not None:
                readings["ps_power"] = v * c
    else:
        errors.append("PS not initialized")

    if load:
        try:
            lv, li = load.read_voltage_current()
            readings["load_voltage"] = lv
            readings["load_current"] = li
            readings["load_power"] = lv * li if lv is not None and li is not None else None
        except Exception as exc:
            errors.append(f"load_measure failed: {exc}")
    else:
        errors.append("Load not initialized")

    if measure_gs:
        if gs:
            try:
                readings["gs_voltage"] = gs.get_grid_voltage()
            except Exception as exc:
                errors.append(f"gs_voltage failed: {exc}")
            try:
                readings["gs_current"] = gs.get_grid_current()
            except Exception as exc:
                errors.append(f"gs_current failed: {exc}")
            try:
                readings["gs_power"] = gs.measure_power_real()
            except Exception as exc:
                errors.append(f"gs_power failed: {exc}")
            try:
                readings["gs_pf"] = gs.measure_power_factor()
            except Exception as exc:
                errors.append(f"gs_pf failed: {exc}")
            try:
                readings["gs_freq"] = gs.get_grid_frequency()
            except Exception as exc:
                errors.append(f"gs_freq failed: {exc}")
            if readings.get("gs_power") is None:
                v = readings.get("gs_voltage")
                c = readings.get("gs_current")
                if v is not None and c is not None:
                    readings["gs_power"] = v * c
        else:
            errors.append("GS not initialized")

    if errors:
        readings["errors"] = errors
    return readings


def handle_load(action_name, params, ctx):
    if "Connect" in action_name:
        return ctx.inst_mgr.init_load()
    if "Disconnect" in action_name:
        return ctx.inst_mgr.end_load()

    if not getattr(ctx.inst_mgr, "dc_load", None):
        return False, "DC Load not initialized"

    if action_name.startswith("Short Circuit Cycle"):
        data = parse_json_dict(params, default={}, strict=True)
        cycles = int(data.get("cycles", 0) or 0)
        pulse_s = parse_number(data.get("pulse_s"), default=None)
        input_on_delay_s = parse_number(data.get("input_on_delay_s"), default=0.0)
        dwell_s = parse_number(data.get("dwell_s"), default=0.0)
        precharge_s = parse_number(data.get("precharge_s"), default=0.0)
        cc_a = parse_number(data.get("cc_a"), default=None)
        ps_output = bool(data.get("ps_output", True))
        ps_toggle_each_cycle = bool(data.get("ps_toggle_each_cycle", False))
        gs_telemetry = bool(data.get("gs_telemetry", False))
        input_toggle = bool(data.get("input_on_each_cycle", True))
        stop_on_fail = bool(data.get("stop_on_fail", True))

        if cycles <= 0:
            return False, "cycles must be > 0"
        if pulse_s is None or pulse_s <= 0:
            return False, "pulse_s must be > 0"
        if input_on_delay_s is None or input_on_delay_s < 0:
            return False, "input_on_delay_s must be >= 0"
        if dwell_s is None or dwell_s < 0:
            return False, "dwell_s must be >= 0"
        if precharge_s is None or precharge_s < 0:
            return False, "precharge_s must be >= 0"

        ps = getattr(ctx.inst_mgr, "itech6000", None)
        gs = getattr(ctx.inst_mgr, "itech7900", None)
        if ps_output:
            if ps is None:
                return False, "PS not initialized"
            if not ps_toggle_each_cycle:
                ctx.log_cmd("PS OUTPUT ON")
                try:
                    ps.power_on()
                except Exception as exc:
                    return False, f"PS Output ON failed: {exc}"
                if precharge_s:
                    time.sleep(precharge_s)

        if cc_a is not None:
            ok, msg = ctx.inst_mgr.dc_load_set_cc(cc_a)
            if not ok and stop_on_fail:
                if ps_output and ps:
                    try:
                        ps.power_off()
                    except Exception:
                        pass
                return False, msg

        logs = []
        last_error = None
        for idx in range(1, cycles + 1):
            if ctx.stop_event.is_set() or not ctx.running:
                last_error = "Sequence stopped"
                break
            ctx.emit_info(_pulse_cycle_summary(idx, cycles, pulse_s, dwell_s))

            cycle_start = time.perf_counter()
            cycle_ps_on = False
            pulse_actual_s = None
            dwell_actual_s = None
            input_delay_actual_s = None
            ps_on_s = None
            ps_off_s = None
            ok = True
            msg = ""

            try:
                if ps_output and ps_toggle_each_cycle:
                    ctx.log_cmd("PS OUTPUT ON")
                    try:
                        ps_on_start = time.perf_counter()
                        ps.power_on()
                        ps_on_s = time.perf_counter() - ps_on_start
                        cycle_ps_on = True
                    except Exception as exc:
                        last_error = f"PS Output ON failed: {exc}"
                        if stop_on_fail:
                            break
                        else:
                            continue
                    if precharge_s:
                        time.sleep(precharge_s)

                if input_toggle:
                    if input_on_delay_s:
                        try:
                            delay_start = time.perf_counter()
                            ctx.inst_mgr.dc_load_enable_input(True)
                            time.sleep(input_on_delay_s)
                            input_delay_actual_s = time.perf_counter() - delay_start
                        except Exception as exc:
                            msg = f"Input ON delay failed: {exc}"
                            ok = False
                            if stop_on_fail:
                                last_error = msg
                                break
                        finally:
                            try:
                                ctx.inst_mgr.dc_load_enable_input(False)
                            except Exception:
                                pass
                    pulse_start = time.perf_counter()
                    ok, msg = ctx.inst_mgr.dc_load_short_pulse(pulse_s)
                    pulse_actual_s = time.perf_counter() - pulse_start
                else:
                    if input_on_delay_s:
                        try:
                            delay_start = time.perf_counter()
                            ctx.inst_mgr.dc_load_enable_input(True)
                            time.sleep(input_on_delay_s)
                            input_delay_actual_s = time.perf_counter() - delay_start
                        except Exception as exc:
                            msg = f"Input ON delay failed: {exc}"
                            ok = False
                            if stop_on_fail:
                                last_error = msg
                                break
                        finally:
                            try:
                                ctx.inst_mgr.dc_load_enable_input(False)
                            except Exception:
                                pass
                    ok, msg = ctx.inst_mgr.dc_load_start_short_circuit()
                    if ok:
                        try:
                            pulse_start = time.perf_counter()
                            ctx.inst_mgr.dc_load_enable_input(True)
                            time.sleep(pulse_s)
                            pulse_actual_s = time.perf_counter() - pulse_start
                        except Exception as exc:
                            ok = False
                            msg = f"Short cycle failed: {exc}"
                        finally:
                            try:
                                ctx.inst_mgr.dc_load_stop_short_circuit()
                            except Exception:
                                pass
            finally:
                if ps_output and ps_toggle_each_cycle and cycle_ps_on:
                    try:
                        ps_off_start = time.perf_counter()
                        ps.power_off()
                        ps_off_s = time.perf_counter() - ps_off_start
                    except Exception:
                        pass

            if not ok:
                last_error = msg
                if stop_on_fail:
                    break
            if dwell_s:
                dwell_start = time.perf_counter()
                time.sleep(dwell_s)
                dwell_actual_s = time.perf_counter() - dwell_start

            readings = _measure_cycle_readings(ps, getattr(ctx.inst_mgr, "dc_load", None), gs, gs_telemetry)
            errors = readings.pop("errors", [])
            logs.append(
                {
                    "cycle": idx,
                    "status": "ok" if ok else "fail",
                    "message": msg,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timing": {
                        "pulse_set_s": pulse_s,
                        "pulse_actual_s": pulse_actual_s,
                        "input_on_delay_set_s": input_on_delay_s,
                        "input_on_delay_actual_s": input_delay_actual_s,
                        "dwell_set_s": dwell_s,
                        "dwell_actual_s": dwell_actual_s,
                        "ps_on_s": ps_on_s,
                        "ps_off_s": ps_off_s,
                        "cycle_total_s": time.perf_counter() - cycle_start,
                    },
                    "readings": readings,
                    "errors": errors,
                }
            )

        if not input_toggle:
            try:
                ctx.inst_mgr.dc_load_enable_input(False)
            except Exception:
                pass

        if ps_output and ps and not ps_toggle_each_cycle:
            try:
                ps.power_off()
            except Exception:
                pass

        try:
            payload = json.dumps(logs)
            ctx.emit_info(f"[SHORTCYCLE_LOG]{payload}")
        except Exception:
            pass
        if last_error:
            return False, last_error
        return True, f"Short circuit cycle completed ({cycles} cycles)"

    if action_name.startswith("Short Circuit Pulse"):
        try:
            duration = float(params)
        except Exception:
            return False, "Invalid short-circuit duration"
        ctx.log_cmd(f"LOAD SHORT PULSE {duration}")
        return ctx.inst_mgr.dc_load_short_pulse(duration)
    if action_name.startswith("Short Circuit ON"):
        ctx.log_cmd("LOAD SHORT ON")
        return ctx.inst_mgr.dc_load_start_short_circuit()
    if action_name.startswith("Short Circuit OFF"):
        ctx.log_cmd("LOAD SHORT OFF")
        return ctx.inst_mgr.dc_load_stop_short_circuit()

    if "Input ON" in action_name:
        return ctx.inst_mgr.dc_load_enable_input(True)
    if "Input OFF" in action_name:
        return ctx.inst_mgr.dc_load_enable_input(False)

    if action_name.startswith("Set CC"):
        try:
            val = float(params)
        except Exception:
            return False, "Invalid current value"
        ctx.log_cmd(f"LOAD CC {val}")
        return ctx.inst_mgr.dc_load_set_cc(val)

    if action_name.startswith("Set CV"):
        try:
            val = float(params)
        except Exception:
            return False, "Invalid voltage value"
        ctx.log_cmd(f"LOAD CV {val}")
        return ctx.inst_mgr.dc_load_set_cv(val)

    if action_name.startswith("Set CP"):
        try:
            val = float(params)
        except Exception:
            return False, "Invalid power value"
        ctx.log_cmd(f"LOAD CP {val}")
        return ctx.inst_mgr.dc_load_set_cp(val)

    if action_name.startswith("Set CR"):
        try:
            val = float(params)
        except Exception:
            return False, "Invalid resistance value"
        ctx.log_cmd(f"LOAD CR {val}")
        return ctx.inst_mgr.dc_load_set_cr(val)

    if action_name.startswith("Measure VI"):
        return ctx.inst_mgr.dc_load_measure_vi()
    if action_name.startswith("Measure Power"):
        return ctx.inst_mgr.dc_load_measure_power()

    msg = f"Unsupported LOAD action: {action_name}"
    print(msg)
    return False, msg
