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

    # Oscilloscope (OS)
    ActionDef("OS / Run", "OS", description="Run acquisition"),
    ActionDef("OS / Stop", "OS", description="Stop acquisition"),
    ActionDef("OS / Get Waveform", "OS", description="Fetch waveform"),
    ActionDef("OS / Set Timebase", "OS", param_type="str", description="Set timebase"),
    ActionDef("OS / Set Channel Enable", "OS", param_type="str", description="Enable/disable channel"),
    ActionDef("OS / Set Channel Scale", "OS", param_type="str", description="Set vertical scale"),
    ActionDef("OS / Set Channel Offset", "OS", param_type="str", description="Set offset"),
    ActionDef("OS / Set Coupling", "OS", param_type="str", description="Set coupling mode"),
    ActionDef("OS / Set Bandwidth Limit", "OS", param_type="str", description="Set bandwidth limit"),
    ActionDef("OS / Set Probe Attenuation", "OS", param_type="str", description="Set probe attenuation"),
    ActionDef("OS / Set Acquisition Mode", "OS", param_type="str", description="Set acquisition mode"),
    ActionDef("OS / Set Memory Depth", "OS", param_type="str", description="Set memory depth"),
    ActionDef("OS / Set Trigger Source", "OS", param_type="str", description="Trigger source"),
    ActionDef("OS / Set Trigger Type", "OS", param_type="str", description="Trigger type"),
    ActionDef("OS / Set Trigger Level", "OS", param_type="str", description="Trigger level"),
    ActionDef("OS / Set Trigger Slope", "OS", param_type="str", description="Trigger slope/polarity"),
    ActionDef("OS / Force Trigger", "OS", description="Force a trigger"),
    ActionDef("OS / Auto Setup", "OS", description="Auto setup"),
    ActionDef("OS / Measure (single)", "OS", param_type="str", description="Single measurement"),
    ActionDef("OS / Measure (all enabled)", "OS", description="Measure all enabled"),
    ActionDef("OS / Acquire Screenshot", "OS", param_type="str", description="Save screenshot"),
    ActionDef("OS / Save Setup", "OS", param_type="str", description="Save setup"),
    ActionDef("OS / Load Setup", "OS", param_type="str", description="Load setup"),

    # DC Load (LOAD)
    ActionDef("LOAD / Connect", "LOAD", description="Connect DC load"),
    ActionDef("LOAD / Disconnect", "LOAD", description="Disconnect DC load"),
    ActionDef("LOAD / Input ON", "LOAD", description="Enable load input"),
    ActionDef("LOAD / Input OFF", "LOAD", description="Disable load input"),
    ActionDef("LOAD / Set CC (A)", "LOAD", param_type="float", description="Set constant current (A)"),
    ActionDef("LOAD / Set CV (V)", "LOAD", param_type="float", description="Set constant voltage (V)"),
    ActionDef("LOAD / Set CP (W)", "LOAD", param_type="float", description="Set constant power (W)"),
    ActionDef("LOAD / Set CR (Ohm)", "LOAD", param_type="float", description="Set constant resistance (Ohm)"),
    ActionDef("LOAD / Measure VI", "LOAD", description="Measure voltage/current"),
    ActionDef("LOAD / Measure Power", "LOAD", description="Measure power (derived)"),

    # Generic ramp (cross-domain)
    ActionDef("RAMP / Ramp Set & Measure", "RAMP", param_type="str", description="Ramp target (CAN/GS/PS) and measure GS+PS per step (JSON params)"),
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

