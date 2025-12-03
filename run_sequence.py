import argparse
import json
import os
import sys
import logging
from typing import List, Dict, Any

from PyQt6.QtCore import QCoreApplication

from logging_setup import setup_logging
from config_loader import load_profiles, get_profile
from core.DBCParser import DBCParser
from core.InstrumentManager import InstrumentManager
from core.CANManager import CANManager
from core.Sequencer import Sequencer


def load_sequence_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "steps" in data:
        return data["steps"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported sequence format")


def run_sequence(steps: List[Dict[str, Any]], sequencer: Sequencer, logger: logging.Logger):
    sequencer.running = True
    for i, step in enumerate(steps):
        action = step.get("action")
        params = step.get("params")
        logger.info("Running step %s: %s", i + 1, action)
        success, message = sequencer._execute_action(action, params, i)
        if message:
            print(f"Step {i+1}: {message}")
            logger.info("Step %s: %s", i + 1, message)
        if not success:
            logger.error("Step %s failed, stopping.", i + 1)
            break
    sequencer.running = False


def main():
    parser = argparse.ArgumentParser(description="Headless AtomX sequence runner")
    parser.add_argument("--sequence", "-s", required=True, help="Path to sequence JSON file")
    parser.add_argument("--profile", "-p", default="sim", help="Profile name (sim/dev/hw)")
    parser.add_argument("--dbc", default="RE", help="DBC file name without extension (default: RE)")
    parser.add_argument("--init-instruments", action="store_true", help="Initialize instruments before running")
    parser.add_argument("--log-level", default="INFO", help="Logging level (INFO/DEBUG/WARNING/ERROR)")
    args = parser.parse_args()

    logger, log_path = setup_logging(level=args.log_level)
    logger.info("Starting headless runner")

    # Minimal Qt core application to satisfy QObject requirements
    app = QCoreApplication([])

    profiles = load_profiles()
    profile = get_profile(args.profile, profiles)
    sim_mode = profile.get("simulation_mode", False)
    can_cfg = profile.get("can", {})
    instruments_cfg = profile.get("instruments", {})

    inst_mgr = InstrumentManager(simulation_mode=sim_mode, config=instruments_cfg)
    dbc_parser = DBCParser(dbc_folder="DBC")
    success, msg = dbc_parser.load_dbc_file(args.dbc)
    if not success:
        logger.error("Failed to load DBC: %s", msg)
        sys.exit(1)
    can_mgr = CANManager(simulation_mode=sim_mode, dbc_parser=dbc_parser, logger=logger)
    can_mgr.interface = can_cfg.get("interface")
    can_mgr.channel = can_cfg.get("channel")
    can_mgr.bitrate = can_cfg.get("bitrate")

    if args.init_instruments:
        ok, m = inst_mgr.initialize_instruments()
        logger.info("Initialize instruments: %s", m)
        if not ok:
            logger.warning("Instrument initialization reported failures")

    sequencer = Sequencer(inst_mgr, can_mgr, logger=logger)

    steps = load_sequence_file(args.sequence)
    logger.info("Loaded %s steps from %s", len(steps), args.sequence)
    run_sequence(steps, sequencer, logger)

    # Clean up
    try:
        can_mgr.disconnect()
    except Exception:
        pass
    try:
        inst_mgr.close_instruments()
    except Exception:
        pass

    logger.info("Headless runner complete. Log: %s", log_path)


if __name__ == "__main__":
    main()
