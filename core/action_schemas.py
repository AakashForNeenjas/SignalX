"""
Centralized action parameter schemas used for catalog/docs generation.
Separated from action_registry to keep the registry focused on action lists.
"""

ACTION_PARAM_SCHEMAS = {
    # GS/PS ramp actions
    "GS / Ramp Up Voltage": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "tolerance": {"type": "number", "default": 0.5},
            "retries": {"type": "integer", "default": 3},
        },
    },
    "GS / Ramp Down Voltage": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "tolerance": {"type": "number", "default": 0.5},
            "retries": {"type": "integer", "default": 3},
        },
    },
    "PS / HV: Ramp Up Voltage": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "tolerance": {"type": "number", "default": 0.5},
            "retries": {"type": "integer", "default": 3},
        },
    },
    "PS / HV: Ramp Down Voltage": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "tolerance": {"type": "number", "default": 0.5},
            "retries": {"type": "integer", "default": 3},
        },
    },
    "PS / HV: Battery Set Charge (V,I)": {
        "type": "json",
        "required": ["voltage", "current"],
        "fields": {
            "voltage": {"type": "number"},
            "current": {"type": "number"},
        },
    },
    "PS / HV: Battery Set Discharge (V,I)": {
        "type": "json",
        "required": ["voltage", "current"],
        "fields": {
            "voltage": {"type": "number"},
            "current": {"type": "number"},
        },
    },
    "PS / HV: Sweep Voltage and Log": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "log_file": {"type": "string", "optional": True},
        },
    },
    "PS / HV: Sweep Current and Log": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "log_file": {"type": "string", "optional": True},
        },
    },
    "PS / Advanced: HV Sweep Voltage and Log": {
        "type": "json",
        "required": ["start", "end", "step"],
        "fields": {
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "delay": {"type": "number", "default": 0.5},
            "log_file": {"type": "string", "optional": True},
        },
    },
    "LOAD / Short Circuit Pulse": {
        "type": "float",
        "required": True,
        "note": "Short-circuit pulse duration in seconds",
    },
    "LOAD / Short Circuit Cycle": {
        "type": "json",
        "required": ["cycles", "pulse_s"],
        "fields": {
            "cycles": {"type": "integer"},
            "pulse_s": {"type": "number"},
            "input_on_delay_s": {"type": "number", "default": 0.0},
            "dwell_s": {"type": "number", "default": 0.0},
            "precharge_s": {"type": "number", "default": 0.0},
            "cc_a": {"type": "number", "optional": True},
            "ps_output": {"type": "boolean", "default": True},
            "ps_toggle_each_cycle": {"type": "boolean", "default": False},
            "gs_telemetry": {"type": "boolean", "default": False},
            "input_on_each_cycle": {"type": "boolean", "default": True},
            "stop_on_fail": {"type": "boolean", "default": True},
        },
    },
    # Generic ramp
    "RAMP / Ramp Set & Measure": {
        "type": "json",
        "required": ["target", "start", "end", "step", "dwell"],
        "fields": {
            "target": {
                "type": "object",
                "required": ["type"],
                "fields": {
                    "type": {"enum": ["GS_VOLT", "GS_FREQUENCY", "PS_VOLT", "PS_CURRENT", "CAN_SIGNAL"]},
                    "message": {"type": "string", "optional": True},
                    "signal": {"type": "string", "optional": True},
                },
            },
            "start": {"type": "number"},
            "end": {"type": "number"},
            "step": {"type": "number"},
            "dwell": {"type": "number"},
            "tolerance": {"type": "number", "default": 0.5},
            "retries": {"type": "integer", "default": 2},
            "verify": {"type": "boolean", "default": False},
            "gs_voltage": {"type": "number", "note": "Required when target.type is GS_FREQUENCY"},
            "ps_voltage": {"type": "number", "note": "Optional safe voltage limit for PS_CURRENT"},
            "measure": {
                "type": "object",
                "fields": {
                    "gs": {"type": "boolean", "default": True},
                    "ps": {"type": "boolean", "default": True},
                    "load": {"type": "boolean", "default": True},
                },
            },
        },
    },
    "RAMP / Line and Load Regulation": {
        "type": "json",
        "required": ["gs", "ps", "dl"],
        "fields": {
            "gs": {
                "type": "object",
                "required": ["start", "end", "step"],
                "fields": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "step": {"type": "number"},
                    "dwell": {"type": "number", "default": 0.5},
                    "tolerance": {"type": "number", "default": 0.5},
                },
            },
            "ps": {
                "type": "object",
                "required": ["start", "end", "step"],
                "fields": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "step": {"type": "number"},
                    "dwell": {"type": "number", "default": 0.5},
                    "tolerance": {"type": "number", "default": 0.5},
                },
            },
            "dl": {
                "type": "object",
                "required": ["start", "end", "step"],
                "fields": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "step": {"type": "number"},
                    "dwell": {"type": "number", "default": 0.5},
                    "tolerance": {"type": "number", "default": 0.1},
                },
            },
            "verify": {
                "type": "object",
                "fields": {
                    "gs": {"type": "boolean", "default": True},
                    "ps": {"type": "boolean", "default": True},
                    "dl": {"type": "boolean", "default": True},
                },
            },
            "retries": {"type": "integer", "default": 2},
            "dl_reset": {"type": "boolean", "default": True},
            "abort_on_fail": {"type": "boolean", "default": True},
            "plot_efficiency": {"type": "boolean", "default": False},
        },
    },
    # CAN actions
    "CAN / Send Message": {
        "type": "json",
        "required": ["id", "data"],
        "fields": {
            "id": {"type": "integer", "note": "Can be int or hex string (e.g. 0x123)"},
            "data": {"type": "array", "items": {"type": "integer"}},
            "extended": {"type": "boolean", "default": False},
        },
    },
    "CAN / Start Cyclic By Name": {
        "type": "json",
        "required": ["message_name"],
        "fields": {
            "message_name": {"type": "string"},
            "cycle_time": {"type": "integer", "default": 100},
            "signals": {"type": "object", "default": {}},
        },
    },
    "CAN / Stop Cyclic By Name": {
        "type": "json",
        "required": ["message_name"],
        "fields": {
            "message_name": {"type": "string"},
        },
    },
    "CAN / Check Message": {
        "type": "json",
        "required": ["id"],
        "fields": {
            "id": {"type": "integer", "note": "Can be int or hex string"},
            "timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Listen For Message": {
        "type": "json",
        "required": ["id"],
        "fields": {
            "id": {"type": "integer", "note": "Can be int or hex string"},
            "timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Read Signal Value": {
        "type": "json",
        "required": ["signal_name"],
        "fields": {
            "signal_name": {"type": "string"},
            "timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Check Signal (Tolerance)": {
        "type": "json",
        "required": ["signal_name", "expected_value"],
        "fields": {
            "signal_name": {"type": "string"},
            "expected_value": {"type": "number"},
            "tolerance": {"type": "number", "default": 0.1},
            "timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Conditional Jump": {
        "type": "json",
        "required": ["signal_name", "expected_value", "target_step"],
        "fields": {
            "signal_name": {"type": "string"},
            "expected_value": {"type": "number"},
            "tolerance": {"type": "number", "default": 0.1},
            "target_step": {"type": "integer"},
        },
    },
    "CAN / Wait For Signal Change": {
        "type": "json",
        "required": ["signal_name", "initial_value"],
        "fields": {
            "signal_name": {"type": "string"},
            "initial_value": {"type": "number"},
            "timeout": {"type": "number", "default": 5.0},
            "poll_interval": {"type": "number", "default": 0.1},
        },
    },
    "CAN / Monitor Signal Range": {
        "type": "json",
        "required": ["signal_name", "min_val", "max_val"],
        "fields": {
            "signal_name": {"type": "string"},
            "min_val": {"type": "number"},
            "max_val": {"type": "number"},
            "duration": {"type": "number", "default": 5.0},
            "poll_interval": {"type": "number", "default": 0.1},
        },
    },
    "CAN / Compare Two Signals": {
        "type": "json",
        "required": ["signal1", "signal2"],
        "fields": {
            "signal1": {"type": "string"},
            "signal2": {"type": "string"},
            "tolerance": {"type": "number", "default": 0.1},
            "timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Set Signal Value": {
        "type": "json",
        "required": ["message_id", "signal_name", "target_value"],
        "fields": {
            "message_id": {"type": "integer", "note": "Can be int or hex string"},
            "signal_name": {"type": "string"},
            "target_value": {"type": "number"},
            "tolerance": {"type": "number", "default": 0.1},
            "verify_timeout": {"type": "number", "default": 2.0},
        },
    },
    "CAN / Set Signal and Verify": {
        "type": "json",
        "required": ["message_id", "signal_name", "target_value"],
        "fields": {
            "message_id": {"type": "integer", "note": "Can be int or hex string"},
            "signal_name": {"type": "string"},
            "target_value": {"type": "number"},
            "tolerance": {"type": "number", "default": 0.1},
            "verify_timeout": {"type": "number", "default": 2.0},
        },
    },
    "Wait": {
        "type": "float",
        "required": True,
        "note": "Seconds to wait",
    },
}
