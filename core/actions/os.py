from core.actions.params import parse_json_dict, parse_number


def handle_os(action_name, params, ctx):
    if not hasattr(ctx.inst_mgr, "siglent") or ctx.inst_mgr.siglent is None:
        msg = "OS action failed: Oscilloscope not initialized"
        print(msg)
        return False, msg

    scope = ctx.inst_mgr.siglent

    def _parse_num(default=None):
        return parse_number(params, default=default)

    def _parse_dict():
        return parse_json_dict(params, default={})

    if "Run" in action_name:
        try:
            ctx.log_cmd("OS RUN")
            scope.run()
            msg = "OS Run"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"OS Run failed: {e}"
            print(msg)
            return False, msg

    if "Stop" in action_name:
        try:
            ctx.log_cmd("OS STOP")
            scope.stop()
            msg = "OS Stop"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"OS Stop failed: {e}"
            print(msg)
            return False, msg

    if "Get Waveform" in action_name:
        try:
            ctx.log_cmd("OS GET WAVEFORM")
            data = scope.get_waveform()
            msg = f"OS Waveform length: {len(data) if data else 0}"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"OS Get Waveform failed: {e}"
            print(msg)
            return False, msg

    if "Set Timebase" in action_name:
        val = _parse_num()
        try:
            ctx.log_cmd(f"OS TIM:SCAL {val}")
            scope.write(f"TIM:SCAL {val}")
            return True, f"OS Timebase set to {val}"
        except Exception as e:
            return False, f"OS Set Timebase failed: {e}"

    if "Set Channel Enable" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        state = str(d.get("state", "ON")).upper()
        try:
            ctx.log_cmd(f"OS C{ch}:TRA {state}")
            scope.write(f"C{ch}:TRA {state}")
            return True, f"OS CH{ch} {state}"
        except Exception as e:
            return False, f"OS Set Channel Enable failed: {e}"

    if "Set Channel Scale" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        scale = d.get("scale", _parse_num())
        try:
            ctx.log_cmd(f"OS C{ch}:SCAL {scale}")
            scope.write(f"C{ch}:SCAL {scale}")
            return True, f"OS CH{ch} scale {scale}"
        except Exception as e:
            return False, f"OS Set Channel Scale failed: {e}"

    if "Set Channel Offset" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        offset = d.get("offset", _parse_num())
        try:
            ctx.log_cmd(f"OS C{ch}:OFFS {offset}")
            scope.write(f"C{ch}:OFFS {offset}")
            return True, f"OS CH{ch} offset {offset}"
        except Exception as e:
            return False, f"OS Set Channel Offset failed: {e}"

    if "Set Coupling" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        mode = d.get("mode", "DC").upper()
        try:
            ctx.log_cmd(f"OS C{ch}:COUP {mode}")
            scope.write(f"C{ch}:COUP {mode}")
            return True, f"OS CH{ch} coupling {mode}"
        except Exception as e:
            return False, f"OS Set Coupling failed: {e}"

    if "Set Bandwidth Limit" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        state = str(d.get("state", "ON")).upper()
        try:
            ctx.log_cmd(f"OS C{ch}:BWL {state}")
            scope.write(f"C{ch}:BWL {state}")
            return True, f"OS CH{ch} BWL {state}"
        except Exception as e:
            return False, f"OS Set Bandwidth Limit failed: {e}"

    if "Set Probe Attenuation" in action_name:
        d = _parse_dict()
        ch = d.get("channel", 1)
        att = d.get("attenuation", _parse_num(10))
        try:
            ctx.log_cmd(f"OS C{ch}:PROB {att}")
            scope.write(f"C{ch}:PROB {att}")
            return True, f"OS CH{ch} probe {att}x"
        except Exception as e:
            return False, f"OS Set Probe Attenuation failed: {e}"

    if "Set Acquisition Mode" in action_name:
        mode = str(params or "NORM").upper()
        try:
            ctx.log_cmd(f"OS ACQ:MDEP {mode}")
            scope.write(f"ACQ:MDEP {mode}")
            return True, f"OS Acquisition mode {mode}"
        except Exception as e:
            return False, f"OS Set Acquisition Mode failed: {e}"

    if "Set Memory Depth" in action_name:
        depth = _parse_num()
        try:
            ctx.log_cmd(f"OS ACQ:MDEP {depth}")
            scope.write(f"ACQ:MDEP {depth}")
            return True, f"OS Memory depth {depth}"
        except Exception as e:
            return False, f"OS Set Memory Depth failed: {e}"

    if "Set Trigger Source" in action_name:
        src = str(params or "C1").upper()
        try:
            ctx.log_cmd(f"OS TRIG:SOUR {src}")
            scope.write(f"TRIG:SOUR {src}")
            return True, f"OS Trigger source {src}"
        except Exception as e:
            return False, f"OS Set Trigger Source failed: {e}"

    if "Set Trigger Type" in action_name:
        typ = str(params or "EDGE").upper()
        try:
            ctx.log_cmd(f"OS TRIG:MODE {typ}")
            scope.write(f"TRIG:MODE {typ}")
            return True, f"OS Trigger type {typ}"
        except Exception as e:
            return False, f"OS Set Trigger Type failed: {e}"

    if "Set Trigger Level" in action_name:
        level = _parse_num()
        try:
            ctx.log_cmd(f"OS TRIG:LEV {level}")
            scope.write(f"TRIG:LEV {level}")
            return True, f"OS Trigger level {level}"
        except Exception as e:
            return False, f"OS Set Trigger Level failed: {e}"

    if "Set Trigger Slope" in action_name or "Set Trigger Polarity" in action_name:
        slope = str(params or "POS").upper()
        try:
            ctx.log_cmd(f"OS TRIG:SLOP {slope}")
            scope.write(f"TRIG:SLOP {slope}")
            return True, f"OS Trigger slope {slope}"
        except Exception as e:
            return False, f"OS Set Trigger Slope failed: {e}"

    if "Force Trigger" in action_name:
        try:
            ctx.log_cmd("OS TRIG:FORC")
            scope.write("TRIG:FORC")
            return True, "OS Trigger forced"
        except Exception as e:
            return False, f"OS Force Trigger failed: {e}"

    if "Auto Setup" in action_name:
        try:
            ctx.log_cmd("OS AUTO")
            scope.write("AUTO")
            return True, "OS Auto setup"
        except Exception as e:
            return False, f"OS Auto Setup failed: {e}"

    if "Measure (single)" in action_name:
        d = _parse_dict()
        meas = d.get("type", "VPP").upper()
        ch = d.get("channel", 1)
        try:
            ctx.log_cmd(f"OS C{ch}:MEAS:{meas}?")
            resp = scope.query(f"C{ch}:MEAS:{meas}?")
            return True, f"OS Measure {meas} CH{ch}: {resp}"
        except Exception as e:
            return False, f"OS Measure failed: {e}"

    if "Measure (all enabled)" in action_name:
        try:
            ctx.log_cmd("OS MEAS:ALL?")
            resp = scope.query("MEAS:ALL?")
            return True, f"OS Measures: {resp}"
        except Exception as e:
            return False, f"OS Measure all failed: {e}"

    if "Acquire Screenshot" in action_name:
        d = _parse_dict()
        path = d.get("path", "scope.png")
        try:
            ctx.log_cmd("OS SCDP?")
            data = scope.query("SCDP?")
            with open(path, "wb") as f:
                if isinstance(data, bytes):
                    f.write(data)
                else:
                    f.write(str(data).encode())
            return True, f"OS Screenshot saved: {path}"
        except Exception as e:
            return False, f"OS Acquire Screenshot failed: {e}"

    if "Save Setup" in action_name:
        d = _parse_dict()
        path = d.get("path", "setup.stp")
        try:
            ctx.log_cmd(f"OS SAVE:SETT \"{path}\"")
            scope.write(f"SAVE:SETT \"{path}\"")
            return True, f"OS Setup saved: {path}"
        except Exception as e:
            return False, f"OS Save Setup failed: {e}"

    if "Load Setup" in action_name:
        d = _parse_dict()
        path = d.get("path", "setup.stp")
        try:
            ctx.log_cmd(f"OS LOAD:SETT \"{path}\"")
            scope.write(f"LOAD:SETT \"{path}\"")
            return True, f"OS Setup loaded: {path}"
        except Exception as e:
            return False, f"OS Load Setup failed: {e}"

    msg = f"Unsupported OS action: {action_name}"
    print(msg)
    return False, msg
