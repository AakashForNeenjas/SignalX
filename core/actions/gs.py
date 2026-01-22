import time

from core.actions.params import parse_json_dict, parse_number


def handle_gs(action_name, params, ctx):
    if not hasattr(ctx.inst_mgr, "itech7900") or ctx.inst_mgr.itech7900 is None:
        print("GS action failed: Instrument not initialized")
        return False, "GS action failed: Instrument not initialized"

    gs = ctx.inst_mgr.itech7900

    if "Set Voltage" in action_name:
        val = parse_number(params, default=None, strip_units=("v", "volt", "volts"))
        if val is None:
            raise ValueError("Invalid voltage value")
        ctx.log_cmd(f"GS VOLT {val}")
        gs.set_grid_voltage(val)
        msg = f"GS Set Voltage: {val}V"
        print(msg)
        return True, msg

    if action_name.startswith("Set Current"):
        val = parse_number(params, default=None, strip_units=("a", "amp", "amps"))
        if val is None:
            raise ValueError("Invalid current value")
        ctx.log_cmd(f"GS CURR {val}")
        gs.set_grid_current(val)
        msg = f"GS Set Current: {val}A"
        print(msg)
        return True, msg

    if action_name.startswith("Set Frequency"):
        val = parse_number(params, default=None, strip_units=("hz",))
        if val is None:
            raise ValueError("Invalid frequency value")
        ctx.log_cmd(f"GS FREQ {val}")
        gs.set_grid_frequency(val)
        msg = f"GS Set Frequency: {val}Hz"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Voltage"):
        val = gs.get_grid_voltage()
        msg = f"GS Measure Voltage: {val}V"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Current"):
        val = gs.get_grid_current()
        msg = f"GS Measure Current: {val}A"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Frequency"):
        val = gs.get_grid_frequency()
        msg = f"GS Measure Frequency: {val}Hz"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Power Real"):
        val = gs.measure_power_real()
        msg = f"GS Measure Power Real: {val}W"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Power Reactive"):
        val = gs.measure_power_reactive()
        msg = f"GS Measure Power Reactive: {val}VAR"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Power Apparent"):
        val = gs.measure_power_apparent()
        msg = f"GS Measure Power Apparent: {val}VA"
        print(msg)
        return True, msg

    if action_name.startswith("Measure Power Factor"):
        val = gs.measure_power_factor()
        msg = f"GS Measure Power Factor: {val}"
        print(msg)
        return True, msg

    if action_name.startswith("Measure THD Current"):
        val = gs.measure_thd_current()
        msg = f"GS Measure THD Current: {val}%"
        print(msg)
        return True, msg

    if action_name.startswith("Measure THD Voltage"):
        val = gs.measure_thd_voltage()
        msg = f"GS Measure THD Voltage: {val}%"
        print(msg)
        return True, msg

    if action_name.startswith("Power:"):
        if "ON" in action_name:
            ctx.log_cmd("GS OUTP ON")
            gs.power_on()
            msg = "GS Power ON"
            print(msg)
        else:
            ctx.log_cmd("GS OUTP OFF")
            gs.power_off()
            msg = "GS Power OFF"
            print(msg)
        return True, msg

    if action_name.startswith("Ramp Up Voltage"):
        data = parse_json_dict(params, default={}, strict=False)
        if not data and params:
            end_val = parse_number(params, default=None)
            if end_val is not None:
                data = {"end": end_val}

        start = data.get("start", None)
        step = data.get("step", 1.0)
        end = data.get("end", None)
        delay = data.get("delay", 0.5)
        tolerance = data.get("tolerance", 0.5)
        retries = int(data.get("retries", 3))

        try:
            measured_start = gs.get_grid_voltage()
        except Exception:
            measured_start = 0.0
        if start is None:
            start = measured_start
        if end is None:
            end = measured_start

        if end < start:
            msg = f"Ramp Up failed: end ({end}) < start ({start})."
            print(msg)
            return False, msg

        current = start
        steps_executed = 0
        last_measured = measured_start
        while current <= end and (ctx.running or ctx.current_index is not None):
            gs.set_grid_voltage(float(current))
            time.sleep(0.1)

            success_local = False
            for _ in range(retries + 1):
                try:
                    last_measured = gs.get_grid_voltage()
                except Exception:
                    pass
                if abs(last_measured - current) <= tolerance:
                    success_local = True
                    break
                gs.set_grid_voltage(float(current))
                time.sleep(0.1)

            steps_executed += 1
            msg = f"GS RampUp step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
            print(msg)
            ctx.emit_info(msg)

            if not ctx.running and ctx.current_index is None:
                break
            time.sleep(delay)
            current += abs(step)

        final_msg = f"GS RampUp complete: steps={steps_executed}, final_meas={last_measured}V"
        print(final_msg)
        return True, final_msg

    if action_name.startswith("Ramp Down Voltage"):
        data = parse_json_dict(params, default={}, strict=False)
        if not data and params:
            end_val = parse_number(params, default=None)
            if end_val is not None:
                data = {"end": end_val}

        start = data.get("start", None)
        step = data.get("step", 1.0)
        end = data.get("end", None)
        delay = data.get("delay", 0.5)
        tolerance = data.get("tolerance", 0.5)
        retries = int(data.get("retries", 3))

        try:
            measured_start = gs.get_grid_voltage()
        except Exception:
            measured_start = 0.0
        if start is None:
            start = measured_start
        if end is None:
            end = measured_start

        if end > start:
            msg = f"Ramp Down failed: end ({end}) > start ({start})."
            print(msg)
            return False, msg

        current = start
        steps_executed = 0
        last_measured = measured_start
        while current >= end and (ctx.running or ctx.current_index is not None):
            gs.set_grid_voltage(float(current))
            time.sleep(0.1)

            success_local = False
            for _ in range(retries + 1):
                try:
                    last_measured = gs.get_grid_voltage()
                except Exception:
                    pass
                if abs(last_measured - current) <= tolerance:
                    success_local = True
                    break
                gs.set_grid_voltage(float(current))
                time.sleep(0.1)

            steps_executed += 1
            msg = f"GS RampDown step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
            print(msg)
            ctx.emit_info(msg)

            if not ctx.running and ctx.current_index is None:
                break
            time.sleep(delay)
            current -= abs(step)

        final_msg = f"GS RampDown complete: steps={steps_executed}, final_meas={last_measured}V"
        print(final_msg)
        return True, final_msg

    if action_name.startswith("Reset System"):
        gs.reset_system()
        msg = "GS Reset System"
        print(msg)
        return True, msg

    if action_name.startswith("Ramp Set & Measure"):
        from core.actions import ramp
        return ramp.handle_ramp_action(action_name, params, ctx)

    if action_name.startswith("Get IDN"):
        resp = ""
        try:
            resp = gs.query("*IDN?")
            msg = f"GS IDN: {resp}"
            print(msg)
        except Exception:
            msg = "GS IDN: (no response)"
        return True, msg

    if action_name.startswith("Check Error"):
        resp = ""
        try:
            resp = gs.query("SYST:ERR?")
            msg = f"GS Error Status: {resp}"
            print(msg)
        except Exception:
            msg = "GS Error Status: (no response)"
        return True, msg

    if action_name.startswith("Clear Protection"):
        try:
            gs.write("PROT:CLER")
        except Exception:
            pass
        msg = "GS Clear Protection"
        print(msg)
        return True, msg

    if action_name.startswith("Clear Errors"):
        try:
            if hasattr(gs, "clear_errors"):
                gs.clear_errors()
            else:
                try:
                    gs.write("SYST:ERR:CLEAR")
                except Exception:
                    gs.write("*CLS")
            msg = "GS Clear Errors"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"GS Clear Errors failed: {e}"
            print(msg)
            return False, msg

    msg = f"Unsupported GS action: {action_name}"
    print(msg)
    return False, msg
