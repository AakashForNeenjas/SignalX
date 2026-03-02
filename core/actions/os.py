from typing import Any, Dict, Iterable, Optional

from core.actions.params import parse_json_dict, parse_number, parse_int


_TIME_UNITS = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
_FREQ_UNITS = {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}
_VOLT_UNITS = {"v": 1.0, "mv": 1e-3}
_CURR_UNITS = {"a": 1.0, "ma": 1e-3}


def _parse_with_units(value: Any, default: Optional[float] = None, unit_map: Optional[Dict[str, float]] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if len(value) == 1:
            return _parse_with_units(next(iter(value.values())), default=default, unit_map=unit_map)
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        lower = text.lower()
        if unit_map:
            for unit, scale in sorted(unit_map.items(), key=lambda kv: -len(kv[0])):
                if lower.endswith(unit):
                    num_text = lower[: -len(unit)].strip()
                    try:
                        return float(num_text) * scale
                    except Exception:
                        break
        return parse_number(text, default=default)
    return default


def _num(params: Any, keys: Iterable[str] = (), default: Optional[float] = None, unit_map: Optional[Dict[str, float]] = None) -> Optional[float]:
    if not isinstance(params, dict):
        val = _parse_with_units(params, default=None, unit_map=unit_map)
        if val is not None:
            return val
    data = parse_json_dict(params, default={}, strict=False)
    for key in keys:
        if key in data:
            val = _parse_with_units(data.get(key), default=None, unit_map=unit_map)
            if val is not None:
                return val
    return default


def _text(params: Any, keys: Iterable[str] = (), default: Optional[str] = None) -> Optional[str]:
    if not isinstance(params, dict):
        if isinstance(params, str) and params.strip():
            return params.strip()
    data = parse_json_dict(params, default={}, strict=False)
    for key in keys:
        if key in data:
            val = data.get(key)
            if val is None:
                continue
            return str(val).strip()
    return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "enable", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disable", "disabled"}:
            return False
    return default


def _bool(params: Any, keys: Iterable[str] = (), default: bool = False) -> bool:
    if not isinstance(params, dict):
        return _to_bool(params, default=default)
    data = parse_json_dict(params, default={}, strict=False)
    for key in keys:
        if key in data:
            return _to_bool(data.get(key), default=default)
    return default


def _parse_channel(value: Any, default: int = 1) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip().upper()
        if text.startswith("CH"):
            text = text[2:]
        if text.startswith("C"):
            text = text[1:]
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return int(digits)
    return default


def _channel(params: Any, keys: Iterable[str] = ("channel", "ch", "source", "src"), default: int = 1) -> int:
    if isinstance(params, dict):
        data = parse_json_dict(params, default={}, strict=False)
        for key in keys:
            if key in data:
                return _parse_channel(data.get(key), default=default)
    return _parse_channel(params, default=default)


def _source_str(params: Any, keys: Iterable[str] = ("source", "src", "channel", "ch"), default: str = "C1") -> str:
    raw = _text(params, keys=keys, default=None)
    if raw is None:
        raw = params if not isinstance(params, dict) else None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return f"C{int(raw)}"
    if isinstance(raw, str):
        text = raw.strip().upper()
        if text.startswith("CH"):
            text = "C" + text[2:]
        if text.isdigit():
            return f"C{text}"
        return text
    return default


def _ref_str(params: Any, keys: Iterable[str] = ("ref", "reference"), default: str = "REFA") -> str:
    val = _text(params, keys=keys, default=default)
    if not val:
        return default
    text = val.strip().upper()
    if text.startswith("REF"):
        return text
    return f"REF{text}"


def handle_os(action_name: str, params: Any, ctx):
    if not hasattr(ctx.inst_mgr, "siglent") or ctx.inst_mgr.siglent is None:
        return False, "OS action failed: oscilloscope not initialized"

    scope = ctx.inst_mgr.siglent
    sim = bool(getattr(scope, "simulation_mode", False))
    drv = getattr(scope, "_driver", None)
    if not sim and (drv is None or not getattr(scope, "connected", False)):
        return False, "OS action failed: oscilloscope not connected"

    def _sim_msg(msg: str):
        return True, f"{msg} (Simulation)"

    if action_name == "Identify":
        if sim:
            return _sim_msg("OS Identify")
        try:
            resp = drv.idn()
            return True, f"OS Identify: {resp}"
        except Exception as exc:
            return False, f"OS Identify failed: {exc}"

    if action_name == "Reset":
        if sim:
            return _sim_msg("OS Reset")
        try:
            drv.reset()
            return True, "OS Reset"
        except Exception as exc:
            return False, f"OS Reset failed: {exc}"

    if action_name == "Clear Status":
        if sim:
            return _sim_msg("OS Clear Status")
        try:
            drv.clear_status()
            return True, "OS Clear Status"
        except Exception as exc:
            return False, f"OS Clear Status failed: {exc}"

    if action_name == "Get System Status":
        if sim:
            return _sim_msg("OS Get System Status")
        try:
            resp = drv.get_system_status()
            return True, f"OS System Status: {resp}"
        except Exception as exc:
            return False, f"OS Get System Status failed: {exc}"

    if action_name == "Get Error":
        if sim:
            return _sim_msg("OS Get Error")
        try:
            resp = drv.get_error()
            return True, f"OS Error: {resp}"
        except Exception as exc:
            return False, f"OS Get Error failed: {exc}"

    if action_name == "Buzzer":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Buzzer {'ON' if on else 'OFF'}")
        try:
            drv.buzzer(on)
            return True, f"OS Buzzer {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Buzzer failed: {exc}"

    if action_name == "Auto Setup":
        if sim:
            return _sim_msg("OS Auto Setup")
        try:
            drv.auto_setup()
            return True, "OS Auto Setup"
        except Exception as exc:
            return False, f"OS Auto Setup failed: {exc}"

    if action_name == "Run":
        if sim:
            return _sim_msg("OS Run")
        try:
            drv.run()
            return True, "OS Run"
        except Exception as exc:
            return False, f"OS Run failed: {exc}"

    if action_name == "Stop":
        if sim:
            return _sim_msg("OS Stop")
        try:
            drv.stop()
            return True, "OS Stop"
        except Exception as exc:
            return False, f"OS Stop failed: {exc}"

    if action_name == "Single":
        if sim:
            return _sim_msg("OS Single")
        try:
            drv.single()
            return True, "OS Single"
        except Exception as exc:
            return False, f"OS Single failed: {exc}"

    if action_name == "Normal":
        if sim:
            return _sim_msg("OS Normal")
        try:
            drv.normal()
            return True, "OS Normal"
        except Exception as exc:
            return False, f"OS Normal failed: {exc}"

    if action_name == "Force Trigger":
        if sim:
            return _sim_msg("OS Force Trigger")
        try:
            drv.force_trigger()
            return True, "OS Force Trigger"
        except Exception as exc:
            return False, f"OS Force Trigger failed: {exc}"

    if action_name == "Wait For Trigger":
        timeout = _num(params, keys=("timeout", "timeout_s", "wait_s"), default=10.0, unit_map=_TIME_UNITS)
        if sim:
            return _sim_msg(f"OS Wait For Trigger ({timeout}s)")
        try:
            ok = drv.wait_for_trigger(timeout=timeout)
            return True, f"OS Wait For Trigger: {'Triggered' if ok else 'Timeout'}"
        except Exception as exc:
            return False, f"OS Wait For Trigger failed: {exc}"

    if action_name == "Configure Channel":
        ch = _channel(params, default=1)
        vdiv = _num(params, keys=("vdiv", "scale", "volts_per_div"), default=None, unit_map=_VOLT_UNITS)
        if vdiv is None:
            return False, "Configure Channel requires vdiv"
        coupling = _text(params, keys=("coupling",), default="D1M")
        probe = _num(params, keys=("probe", "atten", "attenuation"), default=1.0)
        offset = _num(params, keys=("offset", "ofs"), default=0.0, unit_map=_VOLT_UNITS)
        bw = _text(params, keys=("bw", "bw_limit", "bandwidth"), default="FULL")
        enable = _bool(params, keys=("enable", "enabled", "on"), default=True)
        if sim:
            return _sim_msg(f"OS Configure Channel C{ch}")
        try:
            drv.configure_channel(ch, vdiv, coupling=coupling, probe=probe, offset=offset, bw=bw, enable=enable)
            return True, f"OS Configure Channel C{ch}"
        except Exception as exc:
            return False, f"OS Configure Channel failed: {exc}"

    if action_name == "Channel ON":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Channel C{ch} ON")
        try:
            drv.channel_on(ch)
            return True, f"OS Channel C{ch} ON"
        except Exception as exc:
            return False, f"OS Channel ON failed: {exc}"

    if action_name == "Channel OFF":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Channel C{ch} OFF")
        try:
            drv.channel_off(ch)
            return True, f"OS Channel C{ch} OFF"
        except Exception as exc:
            return False, f"OS Channel OFF failed: {exc}"

    if action_name == "Set Coupling":
        ch = _channel(params, default=1)
        mode = _text(params, keys=("coupling", "mode"), default="D1M")
        if sim:
            return _sim_msg(f"OS Set Coupling C{ch} {mode}")
        try:
            drv.set_coupling(ch, mode)
            return True, f"OS Set Coupling C{ch} {mode}"
        except Exception as exc:
            return False, f"OS Set Coupling failed: {exc}"

    if action_name == "Set Vdiv":
        ch = _channel(params, default=1)
        vdiv = _num(params, keys=("vdiv", "scale", "volts_per_div"), default=None, unit_map=_VOLT_UNITS)
        if vdiv is None:
            return False, "Set Vdiv requires vdiv"
        if sim:
            return _sim_msg(f"OS Set Vdiv C{ch} {vdiv}")
        try:
            drv.set_vdiv(ch, vdiv)
            return True, f"OS Set Vdiv C{ch} {vdiv}"
        except Exception as exc:
            return False, f"OS Set Vdiv failed: {exc}"

    if action_name == "Set Offset":
        ch = _channel(params, default=1)
        offset = _num(params, keys=("offset", "ofs"), default=None, unit_map=_VOLT_UNITS)
        if offset is None:
            return False, "Set Offset requires offset"
        if sim:
            return _sim_msg(f"OS Set Offset C{ch} {offset}")
        try:
            drv.set_offset(ch, offset)
            return True, f"OS Set Offset C{ch} {offset}"
        except Exception as exc:
            return False, f"OS Set Offset failed: {exc}"

    if action_name == "Set Probe":
        ch = _channel(params, default=1)
        probe = _num(params, keys=("probe", "atten", "attenuation"), default=None)
        if probe is None:
            return False, "Set Probe requires probe"
        if sim:
            return _sim_msg(f"OS Set Probe C{ch} {probe}")
        try:
            drv.set_probe(ch, probe)
            return True, f"OS Set Probe C{ch} {probe}"
        except Exception as exc:
            return False, f"OS Set Probe failed: {exc}"

    if action_name == "Set BW Limit":
        ch = _channel(params, default=1)
        bw = _text(params, keys=("bw", "bw_limit", "bandwidth"), default="FULL")
        if sim:
            return _sim_msg(f"OS Set BW Limit C{ch} {bw}")
        try:
            drv.set_bw_limit(ch, bw)
            return True, f"OS Set BW Limit C{ch} {bw}"
        except Exception as exc:
            return False, f"OS Set BW Limit failed: {exc}"

    if action_name == "Set Skew":
        ch = _channel(params, default=1)
        skew = _num(params, keys=("skew", "seconds", "s"), default=None, unit_map=_TIME_UNITS)
        if skew is None:
            return False, "Set Skew requires skew"
        if sim:
            return _sim_msg(f"OS Set Skew C{ch} {skew}")
        try:
            drv.set_skew(ch, skew)
            return True, f"OS Set Skew C{ch} {skew}"
        except Exception as exc:
            return False, f"OS Set Skew failed: {exc}"

    if action_name == "Set Invert":
        ch = _channel(params, default=1)
        on = _bool(params, keys=("on", "invert", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Set Invert C{ch} {'ON' if on else 'OFF'}")
        try:
            drv.set_invert(ch, on)
            return True, f"OS Set Invert C{ch} {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Set Invert failed: {exc}"

    if action_name == "Set Unit":
        ch = _channel(params, default=1)
        unit = _text(params, keys=("unit",), default="V")
        if sim:
            return _sim_msg(f"OS Set Unit C{ch} {unit}")
        try:
            drv.set_unit(ch, unit)
            return True, f"OS Set Unit C{ch} {unit}"
        except Exception as exc:
            return False, f"OS Set Unit failed: {exc}"

    if action_name == "Set Timebase":
        tdiv = _num(params, keys=("tdiv", "timebase", "seconds_per_div"), default=None, unit_map=_TIME_UNITS)
        if tdiv is None:
            return False, "Set Timebase requires tdiv"
        if sim:
            return _sim_msg(f"OS Set Timebase {tdiv}")
        try:
            drv.set_tdiv(tdiv)
            return True, f"OS Set Timebase {tdiv}"
        except Exception as exc:
            return False, f"OS Set Timebase failed: {exc}"

    if action_name == "Set Time Offset":
        ofs = _num(params, keys=("offset", "time_offset", "seconds"), default=None, unit_map=_TIME_UNITS)
        if ofs is None:
            return False, "Set Time Offset requires offset"
        if sim:
            return _sim_msg(f"OS Set Time Offset {ofs}")
        try:
            drv.set_time_offset(ofs)
            return True, f"OS Set Time Offset {ofs}"
        except Exception as exc:
            return False, f"OS Set Time Offset failed: {exc}"

    if action_name == "Set Memory Depth":
        depth = _text(params, keys=("depth", "memory", "size"), default=None)
        if depth is None:
            return False, "Set Memory Depth requires depth"
        if sim:
            return _sim_msg(f"OS Set Memory Depth {depth}")
        try:
            drv.set_memory_size(depth)
            return True, f"OS Set Memory Depth {depth}"
        except Exception as exc:
            return False, f"OS Set Memory Depth failed: {exc}"

    if action_name == "Set Hor Magnify":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Set Hor Magnify {'ON' if on else 'OFF'}")
        try:
            drv.set_hor_magnify(on)
            return True, f"OS Set Hor Magnify {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Set Hor Magnify failed: {exc}"

    if action_name == "Set Hor Magnify Scale":
        scale = _num(params, keys=("scale", "seconds_per_div", "tdiv"), default=None, unit_map=_TIME_UNITS)
        if scale is None:
            return False, "Set Hor Magnify Scale requires scale"
        if sim:
            return _sim_msg(f"OS Set Hor Magnify Scale {scale}")
        try:
            drv.set_hor_magnify_scale(scale)
            return True, f"OS Set Hor Magnify Scale {scale}"
        except Exception as exc:
            return False, f"OS Set Hor Magnify Scale failed: {exc}"

    if action_name == "Set Hor Magnify Position":
        pos = _num(params, keys=("position", "seconds", "pos"), default=None, unit_map=_TIME_UNITS)
        if pos is None:
            return False, "Set Hor Magnify Position requires position"
        if sim:
            return _sim_msg(f"OS Set Hor Magnify Position {pos}")
        try:
            drv.set_hor_magnify_position(pos)
            return True, f"OS Set Hor Magnify Position {pos}"
        except Exception as exc:
            return False, f"OS Set Hor Magnify Position failed: {exc}"

    if action_name == "Get Sample Rate":
        if sim:
            return _sim_msg("OS Get Sample Rate")
        try:
            resp = drv.get_sample_rate()
            return True, f"OS Sample Rate: {resp}"
        except Exception as exc:
            return False, f"OS Get Sample Rate failed: {exc}"

    if action_name == "Get Memory Depth":
        if sim:
            return _sim_msg("OS Get Memory Depth")
        try:
            resp = drv.get_memory_size()
            return True, f"OS Memory Depth: {resp}"
        except Exception as exc:
            return False, f"OS Get Memory Depth failed: {exc}"

    if action_name == "Get Timebase":
        if sim:
            return _sim_msg("OS Get Timebase")
        try:
            resp = drv.get_tdiv()
            return True, f"OS Timebase: {resp}"
        except Exception as exc:
            return False, f"OS Get Timebase failed: {exc}"

    if action_name == "Get Time Offset":
        if sim:
            return _sim_msg("OS Get Time Offset")
        try:
            resp = drv.get_time_offset()
            return True, f"OS Time Offset: {resp}"
        except Exception as exc:
            return False, f"OS Get Time Offset failed: {exc}"

    if action_name == "Setup Edge Trigger":
        ch = _channel(params, default=1)
        level = _num(params, keys=("level", "trig_level"), default=0.0, unit_map=_VOLT_UNITS)
        slope = _text(params, keys=("slope",), default="POS")
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Edge Trigger C{ch}")
        try:
            drv.setup_edge_trigger(ch, level, slope=slope, coupling=coupling)
            return True, f"OS Setup Edge Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Edge Trigger failed: {exc}"

    if action_name == "Setup Pulse Trigger":
        ch = _channel(params, default=1)
        level = _num(params, keys=("level",), default=0.0, unit_map=_VOLT_UNITS)
        width = _num(params, keys=("width", "pulse_width"), default=1e-3, unit_map=_TIME_UNITS)
        kind = _text(params, keys=("kind", "polarity"), default="POSITIVE")
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Pulse Trigger C{ch}")
        try:
            drv.setup_pulse_trigger(ch, level, width=width, kind=kind, coupling=coupling)
            return True, f"OS Setup Pulse Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Pulse Trigger failed: {exc}"

    if action_name == "Setup Slope Trigger":
        ch = _channel(params, default=1)
        level_high = _num(params, keys=("level_high", "high"), default=0.0, unit_map=_VOLT_UNITS)
        level_low = _num(params, keys=("level_low", "low"), default=0.0, unit_map=_VOLT_UNITS)
        slope = _text(params, keys=("slope",), default="POSITIVE")
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Slope Trigger C{ch}")
        try:
            drv.setup_slope_trigger(ch, level_high, level_low, slope=slope, coupling=coupling)
            return True, f"OS Setup Slope Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Slope Trigger failed: {exc}"

    if action_name == "Setup Video Trigger":
        ch = _channel(params, default=1)
        standard = _text(params, keys=("standard",), default="NTSC")
        line = parse_int(_num(params, keys=("line",), default=1), default=1)
        sync = _text(params, keys=("sync",), default="H")
        if sim:
            return _sim_msg(f"OS Setup Video Trigger C{ch}")
        try:
            drv.setup_video_trigger(ch, standard=standard, line=line, sync=sync)
            return True, f"OS Setup Video Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Video Trigger failed: {exc}"

    if action_name == "Setup Dropout Trigger":
        ch = _channel(params, default=1)
        level = _num(params, keys=("level",), default=0.0, unit_map=_VOLT_UNITS)
        width = _num(params, keys=("width",), default=1e-3, unit_map=_TIME_UNITS)
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Dropout Trigger C{ch}")
        try:
            drv.setup_dropout_trigger(ch, level, width=width, coupling=coupling)
            return True, f"OS Setup Dropout Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Dropout Trigger failed: {exc}"

    if action_name == "Setup Runt Trigger":
        ch = _channel(params, default=1)
        level_high = _num(params, keys=("level_high", "high"), default=0.0, unit_map=_VOLT_UNITS)
        level_low = _num(params, keys=("level_low", "low"), default=0.0, unit_map=_VOLT_UNITS)
        width = _num(params, keys=("width",), default=1e-3, unit_map=_TIME_UNITS)
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Runt Trigger C{ch}")
        try:
            drv.setup_runt_trigger(ch, level_high, level_low, width=width, coupling=coupling)
            return True, f"OS Setup Runt Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Runt Trigger failed: {exc}"

    if action_name == "Setup Window Trigger":
        ch = _channel(params, default=1)
        level_high = _num(params, keys=("level_high", "high"), default=0.0, unit_map=_VOLT_UNITS)
        level_low = _num(params, keys=("level_low", "low"), default=0.0, unit_map=_VOLT_UNITS)
        time_low = _num(params, keys=("time_low", "low_time"), default=0.0, unit_map=_TIME_UNITS)
        time_high = _num(params, keys=("time_high", "high_time"), default=0.0, unit_map=_TIME_UNITS)
        coupling = _text(params, keys=("coupling",), default="DC")
        if sim:
            return _sim_msg(f"OS Setup Window Trigger C{ch}")
        try:
            drv.setup_window_trigger(ch, level_high, level_low, time_low, time_high, coupling=coupling)
            return True, f"OS Setup Window Trigger C{ch}"
        except Exception as exc:
            return False, f"OS Setup Window Trigger failed: {exc}"

    if action_name == "Setup Pattern Trigger":
        c1 = _text(params, keys=("c1",), default="X")
        c2 = _text(params, keys=("c2",), default="X")
        c3 = _text(params, keys=("c3",), default="X")
        c4 = _text(params, keys=("c4",), default="X")
        logic = _text(params, keys=("logic",), default="AND")
        threshold = _num(params, keys=("threshold", "thresh"), default=1.4, unit_map=_VOLT_UNITS)
        if sim:
            return _sim_msg("OS Setup Pattern Trigger")
        try:
            drv.setup_pattern_trigger(c1=c1, c2=c2, c3=c3, c4=c4, logic=logic, threshold=threshold)
            return True, "OS Setup Pattern Trigger"
        except Exception as exc:
            return False, f"OS Setup Pattern Trigger failed: {exc}"

    if action_name == "Set Trigger Holdoff":
        holdoff = _num(params, keys=("holdoff", "seconds"), default=None, unit_map=_TIME_UNITS)
        if holdoff is None:
            return False, "Set Trigger Holdoff requires holdoff"
        if sim:
            return _sim_msg(f"OS Set Trigger Holdoff {holdoff}")
        try:
            drv.set_trig_holdoff(holdoff)
            return True, f"OS Set Trigger Holdoff {holdoff}"
        except Exception as exc:
            return False, f"OS Set Trigger Holdoff failed: {exc}"

    if action_name == "Set Trigger Level":
        ch = _channel(params, default=1)
        level = _num(params, keys=("level", "value"), default=None, unit_map=_VOLT_UNITS)
        if level is None:
            return False, "Set Trigger Level requires level"
        if sim:
            return _sim_msg(f"OS Set Trigger Level C{ch} {level}")
        try:
            drv.set_trig_level(ch, level)
            return True, f"OS Set Trigger Level C{ch} {level}"
        except Exception as exc:
            return False, f"OS Set Trigger Level failed: {exc}"

    if action_name == "Set Trigger Slope":
        slope = _text(params, keys=("slope",), default="POS")
        if sim:
            return _sim_msg(f"OS Set Trigger Slope {slope}")
        try:
            drv.set_trig_slope(slope)
            return True, f"OS Set Trigger Slope {slope}"
        except Exception as exc:
            return False, f"OS Set Trigger Slope failed: {exc}"

    if action_name == "Set Trigger Coupling":
        mode = _text(params, keys=("coupling", "mode"), default="DC")
        if sim:
            return _sim_msg(f"OS Set Trigger Coupling {mode}")
        try:
            drv.set_trig_coupling(mode)
            return True, f"OS Set Trigger Coupling {mode}"
        except Exception as exc:
            return False, f"OS Set Trigger Coupling failed: {exc}"

    if action_name == "Set Trigger Type":
        trig_type = _text(params, keys=("type", "trig_type"), default="EDGE")
        if sim:
            return _sim_msg(f"OS Set Trigger Type {trig_type}")
        try:
            drv.set_trigger_type(trig_type)
            return True, f"OS Set Trigger Type {trig_type}"
        except Exception as exc:
            return False, f"OS Set Trigger Type failed: {exc}"

    if action_name == "Trigger 50%":
        if sim:
            return _sim_msg("OS Trigger 50%")
        try:
            drv.trig_50()
            return True, "OS Trigger 50%"
        except Exception as exc:
            return False, f"OS Trigger 50% failed: {exc}"

    if action_name == "Set Acquire Mode":
        mode = _text(params, keys=("mode",), default="SAMPLING")
        if sim:
            return _sim_msg(f"OS Set Acquire Mode {mode}")
        try:
            drv.set_acquire_mode(mode)
            return True, f"OS Set Acquire Mode {mode}"
        except Exception as exc:
            return False, f"OS Set Acquire Mode failed: {exc}"

    if action_name == "Set Average Count":
        count = parse_int(_num(params, keys=("count",), default=16), default=16)
        if sim:
            return _sim_msg(f"OS Set Average Count {count}")
        try:
            drv.set_average_count(count)
            return True, f"OS Set Average Count {count}"
        except Exception as exc:
            return False, f"OS Set Average Count failed: {exc}"

    if action_name == "Set Interpolation":
        mode = _text(params, keys=("mode",), default="SINX")
        if sim:
            return _sim_msg(f"OS Set Interpolation {mode}")
        try:
            drv.set_interpolation(mode)
            return True, f"OS Set Interpolation {mode}"
        except Exception as exc:
            return False, f"OS Set Interpolation failed: {exc}"

    if action_name == "Set Sequence":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        count = parse_int(_num(params, keys=("count",), default=1), default=1)
        if sim:
            return _sim_msg(f"OS Set Sequence {'ON' if on else 'OFF'} count={count}")
        try:
            drv.set_sequence(on, count=count)
            return True, f"OS Set Sequence {'ON' if on else 'OFF'} count={count}"
        except Exception as exc:
            return False, f"OS Set Sequence failed: {exc}"

    if action_name == "Set XY Mode":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Set XY Mode {'ON' if on else 'OFF'}")
        try:
            drv.set_xy_mode(on)
            return True, f"OS Set XY Mode {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Set XY Mode failed: {exc}"

    if action_name == "Measure Value":
        ch = _channel(params, default=1)
        param = _text(params, keys=("param", "type", "measure"), default="MEAN")
        if sim:
            return _sim_msg(f"OS Measure Value C{ch} {param}")
        try:
            val = drv.measure_value(ch, param)
            return True, f"OS Measure Value C{ch} {param}: {val}"
        except Exception as exc:
            return False, f"OS Measure Value failed: {exc}"

    if action_name == "Measure PkPk":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Measure PkPk C{ch}")
        try:
            val = drv.measure_pkpk(ch)
            return True, f"OS Measure PkPk C{ch}: {val}"
        except Exception as exc:
            return False, f"OS Measure PkPk failed: {exc}"

    if action_name == "Measure All":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Measure All C{ch}")
        try:
            resp = drv.measure_all(ch)
            return True, f"OS Measure All C{ch}: {resp}"
        except Exception as exc:
            return False, f"OS Measure All failed: {exc}"

    if action_name == "Add Measurement":
        ch = _channel(params, default=1)
        param = _text(params, keys=("param", "type", "measure"), default=None)
        if not param:
            return False, "Add Measurement requires param"
        if sim:
            return _sim_msg(f"OS Add Measurement C{ch} {param}")
        try:
            drv.add_measurement(ch, param)
            return True, f"OS Add Measurement C{ch} {param}"
        except Exception as exc:
            return False, f"OS Add Measurement failed: {exc}"

    if action_name == "Clear Measurements":
        if sim:
            return _sim_msg("OS Clear Measurements")
        try:
            drv.clear_measurements()
            return True, "OS Clear Measurements"
        except Exception as exc:
            return False, f"OS Clear Measurements failed: {exc}"

    if action_name == "Set Statistics":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Set Statistics {'ON' if on else 'OFF'}")
        try:
            drv.set_statistics(on)
            return True, f"OS Set Statistics {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Set Statistics failed: {exc}"

    if action_name == "Reset Statistics":
        if sim:
            return _sim_msg("OS Reset Statistics")
        try:
            drv.reset_statistics()
            return True, "OS Reset Statistics"
        except Exception as exc:
            return False, f"OS Reset Statistics failed: {exc}"

    if action_name == "Get Statistics":
        ch = _channel(params, default=1)
        param = _text(params, keys=("param", "type", "measure"), default="MEAN")
        if sim:
            return _sim_msg(f"OS Get Statistics C{ch} {param}")
        try:
            resp = drv.get_statistics(ch, param)
            return True, f"OS Statistics C{ch} {param}: {resp}"
        except Exception as exc:
            return False, f"OS Get Statistics failed: {exc}"

    if action_name == "Counter ON":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Counter ON C{ch}")
        try:
            drv.set_counter(True, ch=ch)
            return True, f"OS Counter ON C{ch}"
        except Exception as exc:
            return False, f"OS Counter ON failed: {exc}"

    if action_name == "Counter OFF":
        if sim:
            return _sim_msg("OS Counter OFF")
        try:
            drv.set_counter(False, ch=1)
            return True, "OS Counter OFF"
        except Exception as exc:
            return False, f"OS Counter OFF failed: {exc}"

    if action_name == "Get Counter":
        if sim:
            return _sim_msg("OS Get Counter")
        try:
            resp = drv.get_counter()
            return True, f"OS Counter: {resp}"
        except Exception as exc:
            return False, f"OS Get Counter failed: {exc}"

    if action_name == "Set Cursor Type":
        cursor_type = _text(params, keys=("type", "cursor_type"), default="MANUAL")
        if sim:
            return _sim_msg(f"OS Set Cursor Type {cursor_type}")
        try:
            drv.set_cursor_type(cursor_type)
            return True, f"OS Set Cursor Type {cursor_type}"
        except Exception as exc:
            return False, f"OS Set Cursor Type failed: {exc}"

    if action_name == "Set Cursor Mode":
        mode = _text(params, keys=("mode",), default="TIME")
        if sim:
            return _sim_msg(f"OS Set Cursor Mode {mode}")
        try:
            drv.set_cursor_mode(mode)
            return True, f"OS Set Cursor Mode {mode}"
        except Exception as exc:
            return False, f"OS Set Cursor Mode failed: {exc}"

    if action_name == "Set Cursor Source":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Set Cursor Source C{ch}")
        try:
            drv.set_cursor_source(ch)
            return True, f"OS Set Cursor Source C{ch}"
        except Exception as exc:
            return False, f"OS Set Cursor Source failed: {exc}"

    if action_name == "Set Cursor Positions":
        pos_a = _num(params, keys=("a", "pos_a"), default=None)
        pos_b = _num(params, keys=("b", "pos_b"), default=None)
        if pos_a is None or pos_b is None:
            return False, "Set Cursor Positions requires pos_a and pos_b"
        if sim:
            return _sim_msg("OS Set Cursor Positions")
        try:
            drv.set_cursor_positions(pos_a, pos_b)
            return True, "OS Set Cursor Positions"
        except Exception as exc:
            return False, f"OS Set Cursor Positions failed: {exc}"

    if action_name == "Set Cursor HPos":
        pos_a = _num(params, keys=("a", "pos_a"), default=None, unit_map=_TIME_UNITS)
        pos_b = _num(params, keys=("b", "pos_b"), default=None, unit_map=_TIME_UNITS)
        if pos_a is None or pos_b is None:
            return False, "Set Cursor HPos requires pos_a and pos_b"
        if sim:
            return _sim_msg("OS Set Cursor HPos")
        try:
            drv.set_cursor_hpos(pos_a, pos_b)
            return True, "OS Set Cursor HPos"
        except Exception as exc:
            return False, f"OS Set Cursor HPos failed: {exc}"

    if action_name == "Set Cursor VPos":
        pos_a = _num(params, keys=("a", "pos_a"), default=None, unit_map=_VOLT_UNITS)
        pos_b = _num(params, keys=("b", "pos_b"), default=None, unit_map=_VOLT_UNITS)
        if pos_a is None or pos_b is None:
            return False, "Set Cursor VPos requires pos_a and pos_b"
        if sim:
            return _sim_msg("OS Set Cursor VPos")
        try:
            drv.set_cursor_vpos(pos_a, pos_b)
            return True, "OS Set Cursor VPos"
        except Exception as exc:
            return False, f"OS Set Cursor VPos failed: {exc}"

    if action_name == "Get Cursor Values":
        if sim:
            return _sim_msg("OS Get Cursor Values")
        try:
            resp = drv.get_cursor_values()
            return True, f"OS Cursor Values: {resp}"
        except Exception as exc:
            return False, f"OS Get Cursor Values failed: {exc}"

    if action_name == "Set Math":
        op = _text(params, keys=("operation", "op", "math", "type"), default=None)
        if not op:
            return False, "Set Math requires operation"
        src1 = _channel(params, keys=("src1", "source1", "ch1", "a", "channel1"), default=1)
        src2 = _channel(params, keys=("src2", "source2", "ch2", "b", "channel2"), default=2)
        if sim:
            return _sim_msg(f"OS Set Math {op} C{src1},C{src2}")
        try:
            drv.set_math(op, src1=src1, src2=src2)
            return True, f"OS Set Math {op}"
        except Exception as exc:
            return False, f"OS Set Math failed: {exc}"

    if action_name == "Math ON":
        if sim:
            return _sim_msg("OS Math ON")
        try:
            drv.math_on()
            return True, "OS Math ON"
        except Exception as exc:
            return False, f"OS Math ON failed: {exc}"

    if action_name == "Math OFF":
        if sim:
            return _sim_msg("OS Math OFF")
        try:
            drv.math_off()
            return True, "OS Math OFF"
        except Exception as exc:
            return False, f"OS Math OFF failed: {exc}"

    if action_name == "Set Math Vdiv":
        vdiv = _num(params, keys=("vdiv", "scale", "volts_per_div"), default=None, unit_map=_VOLT_UNITS)
        if vdiv is None:
            return False, "Set Math Vdiv requires vdiv"
        if sim:
            return _sim_msg(f"OS Set Math Vdiv {vdiv}")
        try:
            drv.set_math_vdiv(vdiv)
            return True, f"OS Set Math Vdiv {vdiv}"
        except Exception as exc:
            return False, f"OS Set Math Vdiv failed: {exc}"

    if action_name == "Set Math Offset":
        offset = _num(params, keys=("offset", "ofs"), default=None, unit_map=_VOLT_UNITS)
        if offset is None:
            return False, "Set Math Offset requires offset"
        if sim:
            return _sim_msg(f"OS Set Math Offset {offset}")
        try:
            drv.set_math_offset(offset)
            return True, f"OS Set Math Offset {offset}"
        except Exception as exc:
            return False, f"OS Set Math Offset failed: {exc}"

    if action_name == "Set FFT Window":
        window = _text(params, keys=("window",), default="HANNING")
        if sim:
            return _sim_msg(f"OS Set FFT Window {window}")
        try:
            drv.set_fft_window(window)
            return True, f"OS Set FFT Window {window}"
        except Exception as exc:
            return False, f"OS Set FFT Window failed: {exc}"

    if action_name == "Set FFT Scale":
        scale = _num(params, keys=("scale", "db_per_div", "dbdiv"), default=None)
        if scale is None:
            return False, "Set FFT Scale requires scale"
        if sim:
            return _sim_msg(f"OS Set FFT Scale {scale}")
        try:
            drv.set_fft_scale(scale)
            return True, f"OS Set FFT Scale {scale}"
        except Exception as exc:
            return False, f"OS Set FFT Scale failed: {exc}"

    if action_name == "Set FFT Center":
        center = _num(params, keys=("center", "freq", "frequency"), default=None, unit_map=_FREQ_UNITS)
        if center is None:
            return False, "Set FFT Center requires center"
        if sim:
            return _sim_msg(f"OS Set FFT Center {center}")
        try:
            drv.set_fft_center(center)
            return True, f"OS Set FFT Center {center}"
        except Exception as exc:
            return False, f"OS Set FFT Center failed: {exc}"

    if action_name == "Set FFT Span":
        span = _num(params, keys=("span", "freq", "frequency"), default=None, unit_map=_FREQ_UNITS)
        if span is None:
            return False, "Set FFT Span requires span"
        if sim:
            return _sim_msg(f"OS Set FFT Span {span}")
        try:
            drv.set_fft_span(span)
            return True, f"OS Set FFT Span {span}"
        except Exception as exc:
            return False, f"OS Set FFT Span failed: {exc}"

    if action_name == "Set FFT Source":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Set FFT Source C{ch}")
        try:
            drv.set_fft_source(ch)
            return True, f"OS Set FFT Source C{ch}"
        except Exception as exc:
            return False, f"OS Set FFT Source failed: {exc}"

    if action_name == "FFT ON":
        if sim:
            return _sim_msg("OS FFT ON")
        try:
            drv.fft_on()
            return True, "OS FFT ON"
        except Exception as exc:
            return False, f"OS FFT ON failed: {exc}"

    if action_name == "FFT OFF":
        if sim:
            return _sim_msg("OS FFT OFF")
        try:
            drv.fft_off()
            return True, "OS FFT OFF"
        except Exception as exc:
            return False, f"OS FFT OFF failed: {exc}"

    if action_name == "Set Waveform Source":
        source = _source_str(params, keys=("source", "src", "channel", "ch"), default="C1")
        if sim:
            return _sim_msg(f"OS Set Waveform Source {source}")
        try:
            drv.set_waveform_source(source)
            return True, f"OS Set Waveform Source {source}"
        except Exception as exc:
            return False, f"OS Set Waveform Source failed: {exc}"

    if action_name == "Get Waveform":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Get Waveform C{ch}")
        try:
            t, v = drv.get_waveform(ch)
            return True, f"OS Get Waveform C{ch}: {len(v)} points"
        except Exception as exc:
            return False, f"OS Get Waveform failed: {exc}"

    if action_name == "Get Waveform Raw":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS Get Waveform Raw C{ch}")
        try:
            raw = drv.get_waveform_raw(ch)
            return True, f"OS Get Waveform Raw C{ch}: {len(raw)} bytes"
        except Exception as exc:
            return False, f"OS Get Waveform Raw failed: {exc}"

    if action_name == "Screenshot":
        filename = _text(params, keys=("file", "filename", "path"), default="screenshot.bmp")
        if sim:
            return _sim_msg(f"OS Screenshot {filename}")
        try:
            path = drv.screenshot(filename)
            return True, f"OS Screenshot saved: {path}"
        except Exception as exc:
            return False, f"OS Screenshot failed: {exc}"

    if action_name == "Screenshot PNG":
        filename = _text(params, keys=("file", "filename", "path"), default="screenshot.png")
        if sim:
            return _sim_msg(f"OS Screenshot PNG {filename}")
        try:
            path = drv.screenshot_png(filename)
            return True, f"OS Screenshot PNG saved: {path}"
        except Exception as exc:
            return False, f"OS Screenshot PNG failed: {exc}"

    if action_name == "Save Waveform CSV":
        ch = _channel(params, default=1)
        filename = _text(params, keys=("file", "filename", "path"), default=f"waveform_ch{ch}.csv")
        if sim:
            return _sim_msg(f"OS Save Waveform CSV {filename}")
        try:
            drv.save_waveform_csv(ch, filename)
            return True, f"OS Save Waveform CSV: {filename}"
        except Exception as exc:
            return False, f"OS Save Waveform CSV failed: {exc}"

    if action_name == "Save Waveform NPZ":
        ch = _channel(params, default=1)
        filename = _text(params, keys=("file", "filename", "path"), default=f"waveform_ch{ch}.npz")
        if sim:
            return _sim_msg(f"OS Save Waveform NPZ {filename}")
        try:
            drv.save_waveform_numpy(ch, filename)
            return True, f"OS Save Waveform NPZ: {filename}"
        except Exception as exc:
            return False, f"OS Save Waveform NPZ failed: {exc}"

    if action_name == "Set Grid":
        style = _text(params, keys=("style", "grid"), default="FULL")
        if sim:
            return _sim_msg(f"OS Set Grid {style}")
        try:
            drv.set_grid(style)
            return True, f"OS Set Grid {style}"
        except Exception as exc:
            return False, f"OS Set Grid failed: {exc}"

    if action_name == "Set Intensity":
        grid = parse_int(_num(params, keys=("grid",), default=50), default=50)
        trace = parse_int(_num(params, keys=("trace",), default=50), default=50)
        if sim:
            return _sim_msg(f"OS Set Intensity grid={grid} trace={trace}")
        try:
            drv.set_intensity(grid=grid, trace=trace)
            return True, f"OS Set Intensity grid={grid} trace={trace}"
        except Exception as exc:
            return False, f"OS Set Intensity failed: {exc}"

    if action_name == "Set Persistence":
        mode = _text(params, keys=("mode", "persistence"), default="OFF")
        if sim:
            return _sim_msg(f"OS Set Persistence {mode}")
        try:
            drv.set_persistence(mode)
            return True, f"OS Set Persistence {mode}"
        except Exception as exc:
            return False, f"OS Set Persistence failed: {exc}"

    if action_name == "Clear Sweeps":
        if sim:
            return _sim_msg("OS Clear Sweeps")
        try:
            drv.clear_sweeps()
            return True, "OS Clear Sweeps"
        except Exception as exc:
            return False, f"OS Clear Sweeps failed: {exc}"

    if action_name == "Set Display Type":
        dtype = _text(params, keys=("type", "display", "mode"), default="YT")
        if sim:
            return _sim_msg(f"OS Set Display Type {dtype}")
        try:
            drv.set_display_type(dtype)
            return True, f"OS Set Display Type {dtype}"
        except Exception as exc:
            return False, f"OS Set Display Type failed: {exc}"

    if action_name == "Set Color Display":
        on = _bool(params, keys=("on", "enable", "enabled"), default=True)
        if sim:
            return _sim_msg(f"OS Set Color Display {'ON' if on else 'OFF'}")
        try:
            drv.set_color_display(on)
            return True, f"OS Set Color Display {'ON' if on else 'OFF'}"
        except Exception as exc:
            return False, f"OS Set Color Display failed: {exc}"

    if action_name == "Ref ON":
        ref = _ref_str(params, keys=("ref", "reference"), default="REFA")
        if sim:
            return _sim_msg(f"OS Ref ON {ref}")
        try:
            drv.ref_on(ref=ref)
            return True, f"OS Ref ON {ref}"
        except Exception as exc:
            return False, f"OS Ref ON failed: {exc}"

    if action_name == "Ref OFF":
        ref = _ref_str(params, keys=("ref", "reference"), default="REFA")
        if sim:
            return _sim_msg(f"OS Ref OFF {ref}")
        try:
            drv.ref_off(ref=ref)
            return True, f"OS Ref OFF {ref}"
        except Exception as exc:
            return False, f"OS Ref OFF failed: {exc}"

    if action_name == "Ref Save":
        ch = _channel(params, default=1)
        ref = _ref_str(params, keys=("ref", "reference"), default="REFA")
        if sim:
            return _sim_msg(f"OS Ref Save C{ch} -> {ref}")
        try:
            drv.ref_save(ch, ref=ref)
            return True, f"OS Ref Save C{ch} -> {ref}"
        except Exception as exc:
            return False, f"OS Ref Save failed: {exc}"

    if action_name == "Set Ref Vdiv":
        ref = _ref_str(params, keys=("ref", "reference"), default="REFA")
        vdiv = _num(params, keys=("vdiv", "scale", "volts_per_div"), default=None, unit_map=_VOLT_UNITS)
        if vdiv is None:
            return False, "Set Ref Vdiv requires vdiv"
        if sim:
            return _sim_msg(f"OS Set Ref Vdiv {ref} {vdiv}")
        try:
            drv.set_ref_vdiv(ref, vdiv)
            return True, f"OS Set Ref Vdiv {ref} {vdiv}"
        except Exception as exc:
            return False, f"OS Set Ref Vdiv failed: {exc}"

    if action_name == "Set Ref Offset":
        ref = _ref_str(params, keys=("ref", "reference"), default="REFA")
        offset = _num(params, keys=("offset", "ofs"), default=None, unit_map=_VOLT_UNITS)
        if offset is None:
            return False, "Set Ref Offset requires offset"
        if sim:
            return _sim_msg(f"OS Set Ref Offset {ref} {offset}")
        try:
            drv.set_ref_offset(ref, offset)
            return True, f"OS Set Ref Offset {ref} {offset}"
        except Exception as exc:
            return False, f"OS Set Ref Offset failed: {exc}"

    if action_name == "PassFail ON":
        if sim:
            return _sim_msg("OS PassFail ON")
        try:
            drv.passfail_on()
            return True, "OS PassFail ON"
        except Exception as exc:
            return False, f"OS PassFail ON failed: {exc}"

    if action_name == "PassFail OFF":
        if sim:
            return _sim_msg("OS PassFail OFF")
        try:
            drv.passfail_off()
            return True, "OS PassFail OFF"
        except Exception as exc:
            return False, f"OS PassFail OFF failed: {exc}"

    if action_name == "PassFail Source":
        ch = _channel(params, default=1)
        if sim:
            return _sim_msg(f"OS PassFail Source C{ch}")
        try:
            drv.passfail_source(ch)
            return True, f"OS PassFail Source C{ch}"
        except Exception as exc:
            return False, f"OS PassFail Source failed: {exc}"

    if action_name == "PassFail Create Mask":
        x_tol = _num(params, keys=("x_tolerance", "xtol", "x"), default=0.4)
        y_tol = _num(params, keys=("y_tolerance", "ytol", "y"), default=0.4)
        if sim:
            return _sim_msg(f"OS PassFail Create Mask xtol={x_tol} ytol={y_tol}")
        try:
            drv.passfail_create_mask(x_tolerance=x_tol, y_tolerance=y_tol)
            return True, f"OS PassFail Create Mask xtol={x_tol} ytol={y_tol}"
        except Exception as exc:
            return False, f"OS PassFail Create Mask failed: {exc}"

    if action_name == "PassFail Set Action":
        stop_on_fail = _bool(params, keys=("stop_on_fail", "stop"), default=False)
        buzzer_on_fail = _bool(params, keys=("buzzer_on_fail", "buzzer"), default=True)
        if sim:
            return _sim_msg(f"OS PassFail Set Action stop={stop_on_fail} buzzer={buzzer_on_fail}")
        try:
            drv.passfail_set_action(stop_on_fail=stop_on_fail, buzzer_on_fail=buzzer_on_fail)
            return True, f"OS PassFail Set Action stop={stop_on_fail} buzzer={buzzer_on_fail}"
        except Exception as exc:
            return False, f"OS PassFail Set Action failed: {exc}"

    if action_name == "PassFail Result":
        if sim:
            return _sim_msg("OS PassFail Result")
        try:
            resp = drv.passfail_result()
            return True, f"OS PassFail Result: {resp}"
        except Exception as exc:
            return False, f"OS PassFail Result failed: {exc}"

    if action_name == "Decode ON":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        if sim:
            return _sim_msg(f"OS Decode ON bus {bus}")
        try:
            drv.decode_on(bus=bus)
            return True, f"OS Decode ON bus {bus}"
        except Exception as exc:
            return False, f"OS Decode ON failed: {exc}"

    if action_name == "Decode OFF":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        if sim:
            return _sim_msg(f"OS Decode OFF bus {bus}")
        try:
            drv.decode_off(bus=bus)
            return True, f"OS Decode OFF bus {bus}"
        except Exception as exc:
            return False, f"OS Decode OFF failed: {exc}"

    if action_name == "Setup UART Decode":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        rx = _channel(params, keys=("rx", "rx_ch", "rx_channel"), default=1)
        baud = parse_int(_num(params, keys=("baud", "baudrate"), default=9600), default=9600)
        data_bits = parse_int(_num(params, keys=("data_bits", "bits"), default=8), default=8)
        parity = _text(params, keys=("parity",), default="NONE")
        stop_bits = _num(params, keys=("stop_bits", "stop"), default=1.0)
        polarity = _text(params, keys=("polarity",), default="NORMAL")
        if sim:
            return _sim_msg(f"OS Setup UART Decode bus {bus} rx C{rx}")
        try:
            drv.setup_uart_decode(bus=bus, rx_ch=rx, baud=baud, data_bits=data_bits,
                                  parity=parity, stop_bits=stop_bits, polarity=polarity)
            return True, f"OS Setup UART Decode bus {bus}"
        except Exception as exc:
            return False, f"OS Setup UART Decode failed: {exc}"

    if action_name == "Setup UART Trigger":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        condition = _text(params, keys=("condition", "cond"), default="START")
        data = parse_int(_num(params, keys=("data", "value"), default=0), default=0)
        if sim:
            return _sim_msg(f"OS Setup UART Trigger bus {bus} {condition}")
        try:
            drv.setup_uart_trigger(bus=bus, condition=condition, data=data)
            return True, f"OS Setup UART Trigger bus {bus} {condition}"
        except Exception as exc:
            return False, f"OS Setup UART Trigger failed: {exc}"

    if action_name == "Setup SPI Decode":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        clk = _channel(params, keys=("clk", "clk_ch", "clock"), default=1)
        mosi = _channel(params, keys=("mosi", "mosi_ch"), default=2)
        miso = _channel(params, keys=("miso", "miso_ch"), default=3)
        cs = _channel(params, keys=("cs", "cs_ch"), default=4)
        bit_order = _text(params, keys=("bit_order", "order"), default="MSB")
        word_size = parse_int(_num(params, keys=("word_size", "bits"), default=8), default=8)
        cpol = parse_int(_num(params, keys=("cpol",), default=0), default=0)
        cpha = parse_int(_num(params, keys=("cpha",), default=0), default=0)
        if sim:
            return _sim_msg(f"OS Setup SPI Decode bus {bus}")
        try:
            drv.setup_spi_decode(bus=bus, clk_ch=clk, mosi_ch=mosi, miso_ch=miso,
                                 cs_ch=cs, bit_order=bit_order, word_size=word_size,
                                 cpol=cpol, cpha=cpha)
            return True, f"OS Setup SPI Decode bus {bus}"
        except Exception as exc:
            return False, f"OS Setup SPI Decode failed: {exc}"

    if action_name == "Setup I2C Decode":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        sda = _channel(params, keys=("sda", "sda_ch"), default=1)
        scl = _channel(params, keys=("scl", "scl_ch"), default=2)
        if sim:
            return _sim_msg(f"OS Setup I2C Decode bus {bus}")
        try:
            drv.setup_i2c_decode(bus=bus, sda_ch=sda, scl_ch=scl)
            return True, f"OS Setup I2C Decode bus {bus}"
        except Exception as exc:
            return False, f"OS Setup I2C Decode failed: {exc}"

    if action_name == "Setup I2C Trigger":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        condition = _text(params, keys=("condition", "cond"), default="START")
        address = parse_int(_num(params, keys=("address", "addr"), default=0), default=0)
        data = parse_int(_num(params, keys=("data", "value"), default=0), default=0)
        direction = _text(params, keys=("direction", "dir"), default="WRITE")
        if sim:
            return _sim_msg(f"OS Setup I2C Trigger bus {bus} {condition}")
        try:
            drv.setup_i2c_trigger(bus=bus, condition=condition, address=address,
                                  data=data, direction=direction)
            return True, f"OS Setup I2C Trigger bus {bus} {condition}"
        except Exception as exc:
            return False, f"OS Setup I2C Trigger failed: {exc}"

    if action_name == "Setup CAN Decode":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        src = _channel(params, keys=("source", "src", "ch"), default=1)
        baud = parse_int(_num(params, keys=("baud", "baudrate"), default=500000), default=500000)
        if sim:
            return _sim_msg(f"OS Setup CAN Decode bus {bus}")
        try:
            drv.setup_can_decode(bus=bus, src_ch=src, baud=baud)
            return True, f"OS Setup CAN Decode bus {bus}"
        except Exception as exc:
            return False, f"OS Setup CAN Decode failed: {exc}"

    if action_name == "Setup LIN Decode":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        src = _channel(params, keys=("source", "src", "ch"), default=1)
        baud = parse_int(_num(params, keys=("baud", "baudrate"), default=19200), default=19200)
        version = _text(params, keys=("version",), default="2.0")
        if sim:
            return _sim_msg(f"OS Setup LIN Decode bus {bus}")
        try:
            drv.setup_lin_decode(bus=bus, src_ch=src, baud=baud, version=version)
            return True, f"OS Setup LIN Decode bus {bus}"
        except Exception as exc:
            return False, f"OS Setup LIN Decode failed: {exc}"

    if action_name == "Digital ON":
        dch = parse_int(_num(params, keys=("channel", "ch", "digital", "dch"), default=0), default=0)
        if sim:
            return _sim_msg(f"OS Digital ON D{dch}")
        try:
            drv.digital_on(dch)
            return True, f"OS Digital ON D{dch}"
        except Exception as exc:
            return False, f"OS Digital ON failed: {exc}"

    if action_name == "Digital OFF":
        dch = parse_int(_num(params, keys=("channel", "ch", "digital", "dch"), default=0), default=0)
        if sim:
            return _sim_msg(f"OS Digital OFF D{dch}")
        try:
            drv.digital_off(dch)
            return True, f"OS Digital OFF D{dch}"
        except Exception as exc:
            return False, f"OS Digital OFF failed: {exc}"

    if action_name == "Digital Threshold":
        group = _text(params, keys=("group",), default="D0-D7")
        volts = _num(params, keys=("volts", "voltage", "v"), default=None, unit_map=_VOLT_UNITS)
        if volts is None:
            return False, "Digital Threshold requires volts"
        if sim:
            return _sim_msg(f"OS Digital Threshold {group} {volts}")
        try:
            drv.digital_threshold(group, volts)
            return True, f"OS Digital Threshold {group} {volts}"
        except Exception as exc:
            return False, f"OS Digital Threshold failed: {exc}"

    if action_name == "Digital Bus ON":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        if sim:
            return _sim_msg(f"OS Digital Bus ON {bus}")
        try:
            drv.digital_bus_on(bus)
            return True, f"OS Digital Bus ON {bus}"
        except Exception as exc:
            return False, f"OS Digital Bus ON failed: {exc}"

    if action_name == "Digital Bus OFF":
        bus = parse_int(_num(params, keys=("bus",), default=1), default=1)
        if sim:
            return _sim_msg(f"OS Digital Bus OFF {bus}")
        try:
            drv.digital_bus_off(bus)
            return True, f"OS Digital Bus OFF {bus}"
        except Exception as exc:
            return False, f"OS Digital Bus OFF failed: {exc}"

    if action_name == "Power Analysis ON":
        if sim:
            return _sim_msg("OS Power Analysis ON")
        try:
            drv.power_analysis_on()
            return True, "OS Power Analysis ON"
        except Exception as exc:
            return False, f"OS Power Analysis ON failed: {exc}"

    if action_name == "Power Analysis OFF":
        if sim:
            return _sim_msg("OS Power Analysis OFF")
        try:
            drv.power_analysis_off()
            return True, "OS Power Analysis OFF"
        except Exception as exc:
            return False, f"OS Power Analysis OFF failed: {exc}"

    if action_name == "Set Power Type":
        ptype = _text(params, keys=("type", "analysis"), default="QUALITY")
        if sim:
            return _sim_msg(f"OS Set Power Type {ptype}")
        try:
            drv.set_power_type(ptype)
            return True, f"OS Set Power Type {ptype}"
        except Exception as exc:
            return False, f"OS Set Power Type failed: {exc}"

    if action_name == "Set Power Source":
        vch = _channel(params, keys=("voltage_ch", "vch", "voltage", "ch_v"), default=1)
        ich = _channel(params, keys=("current_ch", "ich", "current", "ch_i"), default=2)
        if sim:
            return _sim_msg(f"OS Set Power Source V=C{vch} I=C{ich}")
        try:
            drv.set_power_source(voltage_ch=vch, current_ch=ich)
            return True, f"OS Set Power Source V=C{vch} I=C{ich}"
        except Exception as exc:
            return False, f"OS Set Power Source failed: {exc}"

    if action_name == "Measure Ripple Noise":
        ch = _channel(params, default=1)
        ac = _bool(params, keys=("ac_coupling", "ac"), default=True)
        bw = _text(params, keys=("bw", "bw_limit", "bandwidth"), default="20M")
        vdiv = _num(params, keys=("vdiv", "scale"), default=None, unit_map=_VOLT_UNITS)
        acquire_mode = _text(params, keys=("acquire_mode", "mode"), default="HIGH_RES")
        avg_count = parse_int(_num(params, keys=("average_count", "avg"), default=16), default=16)
        settle = _num(params, keys=("settle", "settle_s"), default=0.5, unit_map=_TIME_UNITS)
        fallback = _bool(params, keys=("fallback", "fallback_waveform"), default=True)
        if sim:
            return _sim_msg(f"OS Measure Ripple Noise C{ch}")
        try:
            result = drv.measure_ripple_noise(
                ch,
                ac_coupling=ac,
                bw_limit=bw,
                vdiv=vdiv,
                acquire_mode=acquire_mode,
                average_count=avg_count,
                settle=settle,
                fallback_waveform=fallback,
            )
            try:
                from dataclasses import asdict
                payload = asdict(result)
            except Exception:
                payload = getattr(result, "__dict__", str(result))
            return True, f"OS Measure Ripple Noise C{ch}: {payload}"
        except Exception as exc:
            return False, f"OS Measure Ripple Noise failed: {exc}"

    if action_name == "Analyze Power Integrity":
        ch = _channel(params, default=1)
        nominal = _num(params, keys=("nominal_voltage", "nominal", "vnom"), default=3.3, unit_map=_VOLT_UNITS)
        acqs = parse_int(_num(params, keys=("num_acquisitions", "samples"), default=20), default=20)
        output_file = _text(params, keys=("file", "filename", "path"), default=None)
        if sim:
            return _sim_msg(f"OS Analyze Power Integrity C{ch}")
        try:
            result = drv.analyze_power_integrity(ch, nominal_voltage=nominal, num_acquisitions=acqs, output_file=output_file)
            return True, f"OS Analyze Power Integrity C{ch}: {result}"
        except Exception as exc:
            return False, f"OS Analyze Power Integrity failed: {exc}"

    if action_name == "Quick Power Check":
        ch = _channel(params, default=1)
        nominal = _num(params, keys=("nominal_voltage", "nominal", "vnom"), default=3.3, unit_map=_VOLT_UNITS)
        tol = _num(params, keys=("tolerance_pct", "tolerance", "tol"), default=5.0)
        ripple_mv = _num(params, keys=("max_ripple_mv", "ripple_mv"), default=50.0)
        if sim:
            return _sim_msg(f"OS Quick Power Check C{ch}")
        try:
            ok = drv.quick_power_check(ch, nominal_voltage=nominal, tolerance_pct=tol, max_ripple_mv=ripple_mv)
            return True, f"OS Quick Power Check C{ch}: {'PASS' if ok else 'FAIL'}"
        except Exception as exc:
            return False, f"OS Quick Power Check failed: {exc}"

    if action_name == "Bode Plot":
        input_ch = _channel(params, keys=("input_ch", "input", "ch_in"), default=1)
        output_ch = _channel(params, keys=("output_ch", "output", "ch_out"), default=2)
        freq_start = _num(params, keys=("freq_start", "start"), default=None, unit_map=_FREQ_UNITS)
        freq_stop = _num(params, keys=("freq_stop", "stop"), default=None, unit_map=_FREQ_UNITS)
        if freq_start is None or freq_stop is None:
            return False, "Bode Plot requires freq_start and freq_stop"
        ppd = parse_int(_num(params, keys=("points_per_decade", "ppd"), default=10), default=10)
        settle = _num(params, keys=("settle", "settle_time"), default=0.5, unit_map=_TIME_UNITS)
        if sim:
            return _sim_msg("OS Bode Plot")
        try:
            result = drv.bode_plot(
                input_ch=input_ch,
                output_ch=output_ch,
                freq_start=freq_start,
                freq_stop=freq_stop,
                points_per_decade=ppd,
                settle_time=settle,
                siggen_set_freq=None,
            )
            return True, f"OS Bode Plot complete ({len(result.get('freq_hz', []))} points)"
        except Exception as exc:
            return False, f"OS Bode Plot failed: {exc}"

    if action_name == "Capture Eye Diagram":
        ch = _channel(params, default=1)
        bit_rate = _num(params, keys=("bit_rate", "bitrate"), default=None, unit_map=_FREQ_UNITS)
        if bit_rate is None:
            return False, "Capture Eye Diagram requires bit_rate"
        acqs = parse_int(_num(params, keys=("num_acquisitions", "samples"), default=50), default=50)
        bits = parse_int(_num(params, keys=("bits_displayed", "bits"), default=2), default=2)
        if sim:
            return _sim_msg(f"OS Capture Eye Diagram C{ch}")
        try:
            result = drv.capture_eye_diagram(ch, bit_rate=bit_rate, num_acquisitions=acqs, bits_displayed=bits)
            return True, f"OS Capture Eye Diagram C{ch}: {result}"
        except Exception as exc:
            return False, f"OS Capture Eye Diagram failed: {exc}"

    if action_name == "Analyze Jitter":
        ch = _channel(params, default=1)
        acqs = parse_int(_num(params, keys=("num_acquisitions", "samples"), default=100), default=100)
        threshold = _num(params, keys=("threshold", "thresh"), default=None, unit_map=_VOLT_UNITS)
        edge = _text(params, keys=("edge",), default="rising")
        output_file = _text(params, keys=("file", "filename", "path"), default=None)
        if sim:
            return _sim_msg(f"OS Analyze Jitter C{ch}")
        try:
            result = drv.analyze_jitter(ch, num_acquisitions=acqs, threshold=threshold, edge=edge, output_file=output_file)
            return True, f"OS Analyze Jitter C{ch}: {result}"
        except Exception as exc:
            return False, f"OS Analyze Jitter failed: {exc}"

    if action_name == "Limit Monitor":
        ch = _channel(params, default=1)
        param = _text(params, keys=("param", "measure", "type"), default=None)
        low = _num(params, keys=("low", "min"), default=None)
        high = _num(params, keys=("high", "max"), default=None)
        if param is None or low is None or high is None:
            return False, "Limit Monitor requires param, low, high"
        interval = _num(params, keys=("interval", "interval_s"), default=1.0, unit_map=_TIME_UNITS)
        duration = _num(params, keys=("duration", "duration_s"), default=60.0, unit_map=_TIME_UNITS)
        log_file = _text(params, keys=("log_file", "file", "path"), default=None)
        if sim:
            return _sim_msg(f"OS Limit Monitor C{ch} {param}")
        try:
            alarms = drv.limit_monitor(ch, param, low, high, interval=interval, duration=duration, log_file=log_file)
            return True, f"OS Limit Monitor: {len(alarms)} alarms"
        except Exception as exc:
            return False, f"OS Limit Monitor failed: {exc}"

    if action_name == "Limit Monitor Multi":
        data = parse_json_dict(params, default={}, strict=False)
        monitors = data.get("monitors")
        if monitors is None and isinstance(params, list):
            monitors = params
        if not monitors:
            return False, "Limit Monitor Multi requires monitors list"
        interval = _num(data, keys=("interval", "interval_s"), default=1.0, unit_map=_TIME_UNITS)
        duration = _num(data, keys=("duration", "duration_s"), default=60.0, unit_map=_TIME_UNITS)
        log_file = _text(data, keys=("log_file", "file", "path"), default=None)
        if sim:
            return _sim_msg("OS Limit Monitor Multi")
        try:
            alarms = drv.limit_monitor_multi(monitors, interval=interval, duration=duration, log_file=log_file)
            return True, f"OS Limit Monitor Multi: {len(alarms)} alarms"
        except Exception as exc:
            return False, f"OS Limit Monitor Multi failed: {exc}"

    return False, f"OS action '{action_name}' not supported"
