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
        delay = data.get("delay", 0.5)
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
            delay = d.get("delay", 0.5)
            log_file = d.get("log_file")
            results = ps.sweep_voltage_and_log(start, step, end, delay=delay, log_path=log_file)
            msg = f"PS Sweep Voltage logged {len(results)} points"
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
            delay = d.get("delay", 0.5)
            log_file = d.get("log_file")
            results = ps.sweep_current_and_log(start, step, end, delay=delay, log_path=log_file)
            msg = f"PS Sweep Current logged {len(results)} points"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"PS Sweep Current failed: {e}"
            print(msg)
            return False, msg

    msg = f"Unsupported PS action: {action_name}"
    print(msg)
    return False, msg
