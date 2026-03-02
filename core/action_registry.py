"""
Central registry for instrument actions and simple parameter expectations.
Used by the Dashboard to build action lists and drive minimal validation.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ActionDef:
    name: str              # Display/action name (must match Sequencer action strings)
    group: str             # Instrument group (GS/PS/OS/LOAD/INSTR)
    param_type: str = "none"  # "none" | "float" | "str"
    description: Optional[str] = None


INSTRUMENT_ACTIONS: List[ActionDef] = [
    # Grid Simulator (GS)
    ActionDef("GS / Check Error", "GS", description="Read protection/fault status"),
    ActionDef("GS / Clear Protection", "GS", description="Clear any active protection"),
    ActionDef("GS / Clear Errors", "GS", description="Clear instrument errors"),
    ActionDef("GS / Get IDN", "GS", description="Query instrument ID"),
    ActionDef("GS / Measure Current AC", "GS", description="Measure AC current"),
    ActionDef("GS / Measure Current DC", "GS", description="Measure DC current"),
    ActionDef("GS / Measure Frequency", "GS", description="Measure output frequency"),
    ActionDef("GS / Measure Voltage AC", "GS", description="Measure AC voltage"),
    ActionDef("GS / Measure Voltage DC", "GS", description="Measure DC voltage"),
    ActionDef("GS / Measure Power Apparent", "GS", description="Measure apparent power"),
    ActionDef("GS / Measure Power Real", "GS", description="Measure real power"),
    ActionDef("GS / Measure Power Reactive", "GS", description="Measure reactive power"),
    ActionDef("GS / Measure Power Factor", "GS", description="Measure power factor"),
    ActionDef("GS / Measure THD Current", "GS", description="Measure current THD"),
    ActionDef("GS / Measure THD Voltage", "GS", description="Measure voltage THD"),
    ActionDef("GS / Power: OFF", "GS", description="Turn output OFF"),
    ActionDef("GS / Power: ON", "GS", description="Turn output ON"),
    ActionDef("GS / Ramp Down Voltage", "GS", param_type="str", description="Ramp down voltage (JSON params)"),
    ActionDef("GS / Ramp Up Voltage", "GS", param_type="str", description="Ramp up voltage (JSON params)"),
    ActionDef("GS / Ramp Set & Measure", "GS", param_type="str", description="Ramp target and measure GS+PS per step (JSON params)"),
    ActionDef("GS / Reset System", "GS", description="Reset instrument"),
    ActionDef("GS / Set Current AC", "GS", param_type="float", description="Set AC current setpoint"),
    ActionDef("GS / Set Current DC", "GS", param_type="float", description="Set DC current setpoint"),
    ActionDef("GS / Set Frequency", "GS", param_type="float", description="Set output frequency"),
    ActionDef("GS / Set Voltage AC", "GS", param_type="float", description="Set AC voltage"),
    ActionDef("GS / Set Voltage DC", "GS", param_type="float", description="Set DC voltage"),

    # Power Supply (PS)
    ActionDef("PS / HV: Connect", "PS", description="Connect power supply"),
    ActionDef("PS / HV: Disconnect", "PS", description="Disconnect power supply"),
    ActionDef("PS / HV: Output ON", "PS", description="Enable output"),
    ActionDef("PS / HV: Output OFF", "PS", description="Disable output"),
    ActionDef("PS / HV: Measure VI", "PS", description="Measure voltage/current"),
    ActionDef("PS / HV: Measure Voltage, Current, Power", "PS", description="Measure VI and compute power"),
    ActionDef("PS / HV: Set Voltage DC", "PS", param_type="float", description="Set DC voltage"),
    ActionDef("PS / HV: Set Current (CC)", "PS", param_type="float", description="Set current limit (CC)"),
    ActionDef("PS / HV: Set Current (CV)", "PS", param_type="float", description="Set current in CV mode"),
    ActionDef("PS / HV: Ramp Up Voltage", "PS", param_type="str", description="Ramp up voltage (JSON params)"),
    ActionDef("PS / HV: Ramp Down Voltage", "PS", param_type="str", description="Ramp down voltage (JSON params)"),
    ActionDef("PS / HV: Battery Set Charge (V,I)", "PS", param_type="str", description="Set charge V/I"),
    ActionDef("PS / HV: Battery Set Discharge (V,I)", "PS", param_type="str", description="Set discharge V/I"),
    ActionDef("PS / HV: Read Errors", "PS", description="Read instrument errors"),
    ActionDef("PS / HV: Clear Errors", "PS", description="Clear instrument errors"),
    ActionDef("PS / HV: Sweep Voltage and Log", "PS", param_type="str", description="Sweep voltage and log"),
    ActionDef("PS / HV: Sweep Current and Log", "PS", param_type="str", description="Sweep current and log"),
    ActionDef("PS / Advanced: HV Sweep Voltage and Log", "PS", param_type="str", description="Advanced sweep"),

    # Oscilloscope (OS) - new driver actions
    ActionDef("OS / Identify", "OS", description="Query *IDN?"),
    ActionDef("OS / Reset", "OS", description="Reset scope"),
    ActionDef("OS / Clear Status", "OS", description="Clear status/errors"),
    ActionDef("OS / Get System Status", "OS", description="Query system status"),
    ActionDef("OS / Get Error", "OS", description="Query error queue"),
    ActionDef("OS / Buzzer", "OS", param_type="str", description="Enable/disable buzzer (JSON)"),
    ActionDef("OS / Auto Setup", "OS", description="Auto setup"),
    ActionDef("OS / Run", "OS", description="Run acquisition"),
    ActionDef("OS / Stop", "OS", description="Stop acquisition"),
    ActionDef("OS / Single", "OS", description="Single-shot acquisition"),
    ActionDef("OS / Normal", "OS", description="Normal trigger mode"),
    ActionDef("OS / Force Trigger", "OS", description="Force a trigger"),
    ActionDef("OS / Wait For Trigger", "OS", param_type="str", description="Wait for trigger (JSON)"),

    ActionDef("OS / Configure Channel", "OS", param_type="str", description="Configure channel (JSON)"),
    ActionDef("OS / Channel ON", "OS", param_type="str", description="Enable channel (JSON)"),
    ActionDef("OS / Channel OFF", "OS", param_type="str", description="Disable channel (JSON)"),
    ActionDef("OS / Set Coupling", "OS", param_type="str", description="Set coupling (JSON)"),
    ActionDef("OS / Set Vdiv", "OS", param_type="str", description="Set volts/div (JSON)"),
    ActionDef("OS / Set Offset", "OS", param_type="str", description="Set vertical offset (JSON)"),
    ActionDef("OS / Set Probe", "OS", param_type="str", description="Set probe attenuation (JSON)"),
    ActionDef("OS / Set BW Limit", "OS", param_type="str", description="Set bandwidth limit (JSON)"),
    ActionDef("OS / Set Skew", "OS", param_type="str", description="Set channel skew (JSON)"),
    ActionDef("OS / Set Invert", "OS", param_type="str", description="Invert channel (JSON)"),
    ActionDef("OS / Set Unit", "OS", param_type="str", description="Set channel unit (JSON)"),

    ActionDef("OS / Set Timebase", "OS", param_type="str", description="Set time/div (JSON)"),
    ActionDef("OS / Set Time Offset", "OS", param_type="str", description="Set time offset (JSON)"),
    ActionDef("OS / Set Memory Depth", "OS", param_type="str", description="Set memory depth (JSON)"),
    ActionDef("OS / Set Hor Magnify", "OS", param_type="str", description="Horizontal magnify on/off (JSON)"),
    ActionDef("OS / Set Hor Magnify Scale", "OS", param_type="str", description="Horizontal magnify scale (JSON)"),
    ActionDef("OS / Set Hor Magnify Position", "OS", param_type="str", description="Horizontal magnify position (JSON)"),
    ActionDef("OS / Get Sample Rate", "OS", description="Get sample rate"),
    ActionDef("OS / Get Memory Depth", "OS", description="Get memory depth"),
    ActionDef("OS / Get Timebase", "OS", description="Get time/div"),
    ActionDef("OS / Get Time Offset", "OS", description="Get time offset"),

    ActionDef("OS / Setup Edge Trigger", "OS", param_type="str", description="Edge trigger (JSON)"),
    ActionDef("OS / Setup Pulse Trigger", "OS", param_type="str", description="Pulse trigger (JSON)"),
    ActionDef("OS / Setup Slope Trigger", "OS", param_type="str", description="Slope trigger (JSON)"),
    ActionDef("OS / Setup Video Trigger", "OS", param_type="str", description="Video trigger (JSON)"),
    ActionDef("OS / Setup Dropout Trigger", "OS", param_type="str", description="Dropout trigger (JSON)"),
    ActionDef("OS / Setup Runt Trigger", "OS", param_type="str", description="Runt trigger (JSON)"),
    ActionDef("OS / Setup Window Trigger", "OS", param_type="str", description="Window trigger (JSON)"),
    ActionDef("OS / Setup Pattern Trigger", "OS", param_type="str", description="Pattern trigger (JSON)"),
    ActionDef("OS / Set Trigger Holdoff", "OS", param_type="str", description="Set trigger holdoff (JSON)"),
    ActionDef("OS / Set Trigger Level", "OS", param_type="str", description="Set trigger level (JSON)"),
    ActionDef("OS / Set Trigger Slope", "OS", param_type="str", description="Set trigger slope (JSON)"),
    ActionDef("OS / Set Trigger Coupling", "OS", param_type="str", description="Set trigger coupling (JSON)"),
    ActionDef("OS / Set Trigger Type", "OS", param_type="str", description="Set trigger type (JSON)"),
    ActionDef("OS / Trigger 50%", "OS", description="Set trigger level to 50%"),

    ActionDef("OS / Set Acquire Mode", "OS", param_type="str", description="Set acquisition mode (JSON)"),
    ActionDef("OS / Set Average Count", "OS", param_type="str", description="Set average count (JSON)"),
    ActionDef("OS / Set Interpolation", "OS", param_type="str", description="Set interpolation (JSON)"),
    ActionDef("OS / Set Sequence", "OS", param_type="str", description="Set sequence mode (JSON)"),
    ActionDef("OS / Set XY Mode", "OS", param_type="str", description="Enable XY mode (JSON)"),

    ActionDef("OS / Measure Value", "OS", param_type="str", description="Measure value (JSON)"),
    ActionDef("OS / Measure PkPk", "OS", param_type="str", description="Measure Vpp (JSON)"),
    ActionDef("OS / Measure All", "OS", param_type="str", description="Measure all (JSON)"),
    ActionDef("OS / Add Measurement", "OS", param_type="str", description="Add measurement (JSON)"),
    ActionDef("OS / Clear Measurements", "OS", description="Clear measurements"),
    ActionDef("OS / Set Statistics", "OS", param_type="str", description="Enable stats (JSON)"),
    ActionDef("OS / Reset Statistics", "OS", description="Reset stats"),
    ActionDef("OS / Get Statistics", "OS", param_type="str", description="Get stats (JSON)"),
    ActionDef("OS / Counter ON", "OS", param_type="str", description="Enable counter (JSON)"),
    ActionDef("OS / Counter OFF", "OS", description="Disable counter"),
    ActionDef("OS / Get Counter", "OS", description="Get counter value"),

    ActionDef("OS / Set Cursor Type", "OS", param_type="str", description="Set cursor type (JSON)"),
    ActionDef("OS / Set Cursor Mode", "OS", param_type="str", description="Set cursor mode (JSON)"),
    ActionDef("OS / Set Cursor Source", "OS", param_type="str", description="Set cursor source (JSON)"),
    ActionDef("OS / Set Cursor Positions", "OS", param_type="str", description="Set cursor positions (JSON)"),
    ActionDef("OS / Set Cursor HPos", "OS", param_type="str", description="Set cursor horizontal (JSON)"),
    ActionDef("OS / Set Cursor VPos", "OS", param_type="str", description="Set cursor vertical (JSON)"),
    ActionDef("OS / Get Cursor Values", "OS", description="Get cursor values"),

    ActionDef("OS / Set Math", "OS", param_type="str", description="Set math op (JSON)"),
    ActionDef("OS / Math ON", "OS", description="Enable math"),
    ActionDef("OS / Math OFF", "OS", description="Disable math"),
    ActionDef("OS / Set Math Vdiv", "OS", param_type="str", description="Set math volts/div (JSON)"),
    ActionDef("OS / Set Math Offset", "OS", param_type="str", description="Set math offset (JSON)"),
    ActionDef("OS / Set FFT Window", "OS", param_type="str", description="Set FFT window (JSON)"),
    ActionDef("OS / Set FFT Scale", "OS", param_type="str", description="Set FFT scale (JSON)"),
    ActionDef("OS / Set FFT Center", "OS", param_type="str", description="Set FFT center (JSON)"),
    ActionDef("OS / Set FFT Span", "OS", param_type="str", description="Set FFT span (JSON)"),
    ActionDef("OS / Set FFT Source", "OS", param_type="str", description="Set FFT source (JSON)"),
    ActionDef("OS / FFT ON", "OS", description="Enable FFT"),
    ActionDef("OS / FFT OFF", "OS", description="Disable FFT"),

    ActionDef("OS / Set Waveform Source", "OS", param_type="str", description="Set waveform source (JSON)"),
    ActionDef("OS / Get Waveform", "OS", param_type="str", description="Get waveform (JSON)"),
    ActionDef("OS / Get Waveform Raw", "OS", param_type="str", description="Get waveform raw bytes (JSON)"),
    ActionDef("OS / Screenshot", "OS", param_type="str", description="Save screenshot (JSON)"),
    ActionDef("OS / Screenshot PNG", "OS", param_type="str", description="Save PNG screenshot (JSON)"),
    ActionDef("OS / Save Waveform CSV", "OS", param_type="str", description="Save waveform CSV (JSON)"),
    ActionDef("OS / Save Waveform NPZ", "OS", param_type="str", description="Save waveform NPZ (JSON)"),
    ActionDef("OS / Set Grid", "OS", param_type="str", description="Set grid style (JSON)"),
    ActionDef("OS / Set Intensity", "OS", param_type="str", description="Set display intensity (JSON)"),
    ActionDef("OS / Set Persistence", "OS", param_type="str", description="Set persistence (JSON)"),
    ActionDef("OS / Clear Sweeps", "OS", description="Clear sweeps"),
    ActionDef("OS / Set Display Type", "OS", param_type="str", description="Set display type (JSON)"),
    ActionDef("OS / Set Color Display", "OS", param_type="str", description="Enable color display (JSON)"),

    ActionDef("OS / Ref ON", "OS", param_type="str", description="Enable reference (JSON)"),
    ActionDef("OS / Ref OFF", "OS", param_type="str", description="Disable reference (JSON)"),
    ActionDef("OS / Ref Save", "OS", param_type="str", description="Save ref waveform (JSON)"),
    ActionDef("OS / Set Ref Vdiv", "OS", param_type="str", description="Set ref volts/div (JSON)"),
    ActionDef("OS / Set Ref Offset", "OS", param_type="str", description="Set ref offset (JSON)"),

    ActionDef("OS / PassFail ON", "OS", description="Enable pass/fail"),
    ActionDef("OS / PassFail OFF", "OS", description="Disable pass/fail"),
    ActionDef("OS / PassFail Source", "OS", param_type="str", description="Set pass/fail source (JSON)"),
    ActionDef("OS / PassFail Create Mask", "OS", param_type="str", description="Create pass/fail mask (JSON)"),
    ActionDef("OS / PassFail Set Action", "OS", param_type="str", description="Pass/fail action (JSON)"),
    ActionDef("OS / PassFail Result", "OS", description="Get pass/fail result"),

    ActionDef("OS / Decode ON", "OS", param_type="str", description="Enable decode (JSON)"),
    ActionDef("OS / Decode OFF", "OS", param_type="str", description="Disable decode (JSON)"),
    ActionDef("OS / Setup UART Decode", "OS", param_type="str", description="UART decode (JSON)"),
    ActionDef("OS / Setup UART Trigger", "OS", param_type="str", description="UART trigger (JSON)"),
    ActionDef("OS / Setup SPI Decode", "OS", param_type="str", description="SPI decode (JSON)"),
    ActionDef("OS / Setup I2C Decode", "OS", param_type="str", description="I2C decode (JSON)"),
    ActionDef("OS / Setup I2C Trigger", "OS", param_type="str", description="I2C trigger (JSON)"),
    ActionDef("OS / Setup CAN Decode", "OS", param_type="str", description="CAN decode (JSON)"),
    ActionDef("OS / Setup LIN Decode", "OS", param_type="str", description="LIN decode (JSON)"),

    ActionDef("OS / Digital ON", "OS", param_type="str", description="Enable digital channel (JSON)"),
    ActionDef("OS / Digital OFF", "OS", param_type="str", description="Disable digital channel (JSON)"),
    ActionDef("OS / Digital Threshold", "OS", param_type="str", description="Set digital threshold (JSON)"),
    ActionDef("OS / Digital Bus ON", "OS", param_type="str", description="Enable digital bus (JSON)"),
    ActionDef("OS / Digital Bus OFF", "OS", param_type="str", description="Disable digital bus (JSON)"),
    ActionDef("OS / Power Analysis ON", "OS", description="Enable power analysis"),
    ActionDef("OS / Power Analysis OFF", "OS", description="Disable power analysis"),
    ActionDef("OS / Set Power Type", "OS", param_type="str", description="Set power analysis type (JSON)"),
    ActionDef("OS / Set Power Source", "OS", param_type="str", description="Set power source channels (JSON)"),

    ActionDef("OS / Measure Ripple Noise", "OS", param_type="str", description="Ripple/noise measurement (JSON)"),
    ActionDef("OS / Analyze Power Integrity", "OS", param_type="str", description="Power integrity analysis (JSON)"),
    ActionDef("OS / Quick Power Check", "OS", param_type="str", description="Quick power check (JSON)"),
    ActionDef("OS / Bode Plot", "OS", param_type="str", description="Bode plot sweep (JSON)"),
    ActionDef("OS / Capture Eye Diagram", "OS", param_type="str", description="Eye diagram capture (JSON)"),
    ActionDef("OS / Analyze Jitter", "OS", param_type="str", description="Jitter analysis (JSON)"),
    ActionDef("OS / Limit Monitor", "OS", param_type="str", description="Limit monitor (JSON)"),
    ActionDef("OS / Limit Monitor Multi", "OS", param_type="str", description="Multi limit monitor (JSON)"),

    # DC Load (LOAD)
    ActionDef("LOAD / Connect", "LOAD", description="Connect DC load"),
    ActionDef("LOAD / Disconnect", "LOAD", description="Disconnect DC load"),
    ActionDef("LOAD / Input ON", "LOAD", description="Enable load input"),
    ActionDef("LOAD / Input OFF", "LOAD", description="Disable load input"),
    ActionDef("LOAD / Short Circuit ON", "LOAD", description="Enter short-circuit mode"),
    ActionDef("LOAD / Short Circuit OFF", "LOAD", description="Exit short-circuit mode"),
    ActionDef("LOAD / Short Circuit Pulse", "LOAD", param_type="float", description="Short-circuit pulse duration (s)"),
    ActionDef("LOAD / Short Circuit Cycle", "LOAD", param_type="str", description="Cyclic short-circuit sequence (JSON params)"),
    ActionDef("LOAD / Set CC (A)", "LOAD", param_type="float", description="Set constant current (A)"),
    ActionDef("LOAD / Set CV (V)", "LOAD", param_type="float", description="Set constant voltage (V)"),
    ActionDef("LOAD / Set CP (W)", "LOAD", param_type="float", description="Set constant power (W)"),
    ActionDef("LOAD / Set CR (Ohm)", "LOAD", param_type="float", description="Set constant resistance (Ohm)"),
    ActionDef("LOAD / Measure VI", "LOAD", description="Measure voltage/current"),
    ActionDef("LOAD / Measure Power", "LOAD", description="Measure power (derived)"),

    # Generic ramp (cross-domain)
    ActionDef("RAMP / Ramp Set & Measure", "RAMP", param_type="str", description="Ramp target (CAN/GS/PS) and measure GS+PS per step (JSON params)"),
    ActionDef("RAMP / Line and Load Regulation", "RAMP", param_type="str", description="Nested GS/PS/DL sweep with measurements (JSON params)"),

    # Instrument lifecycle
    ActionDef("INSTR / Initialize Instruments", "INSTR", description="Initialize all instruments"),
    ActionDef("INSTR / INIT GS", "INSTR", description="Init grid simulator only"),
    ActionDef("INSTR / INIT PS", "INSTR", description="Init power supply only"),
    ActionDef("INSTR / INIT OS", "INSTR", description="Init oscilloscope only"),
    ActionDef("INSTR / END GS", "INSTR", description="Disconnect grid simulator"),
    ActionDef("INSTR / END PS", "INSTR", description="Disconnect power supply"),
    ActionDef("INSTR / END OS", "INSTR", description="Disconnect oscilloscope"),
]


# Convenience lookup: name -> ActionDef
ACTION_LOOKUP = {a.name: a for a in INSTRUMENT_ACTIONS}

# CAN actions used in the UI/Sequencer (kept centralized for catalog generation)
CAN_ACTIONS = [
    "CAN / Connect",
    "CAN / Disconnect",
    "CAN / Start Cyclic CAN",
    "CAN / Stop Cyclic CAN",
    "CAN / Start Trace",
    "CAN / Stop Trace",
    "CAN / Send Message",
    "CAN / Start Cyclic By Name",
    "CAN / Stop Cyclic By Name",
    "CAN / Check Message",
    "CAN / Listen For Message",
    "CAN / Read Signal Value",
    "CAN / Check Signal (Tolerance)",
    "CAN / Conditional Jump",
    "CAN / Wait For Signal Change",
    "CAN / Monitor Signal Range",
    "CAN / Compare Two Signals",
    "CAN / Set Signal and Verify",
    "CAN / Set Signal Value",
]

# Utility actions used in sequence builder
UTILITY_ACTIONS = ["Wait"]

from core.action_schemas import ACTION_PARAM_SCHEMAS

