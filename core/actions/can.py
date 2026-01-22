import threading

from core.actions.params import parse_int, parse_json_dict


def handle_can(action_name, params, ctx):
    if not hasattr(ctx, "can_mgr") or ctx.can_mgr is None:
        msg = "CAN action failed: CAN Manager is not initialized"
        print(msg)
        return False, msg

    can_mgr = ctx.can_mgr

    if action_name.lower() in ["connect", "connect can", "connect can bus"]:
        if getattr(can_mgr, "is_connected", False):
            msg = "CAN Connect: already connected, reusing existing session"
            print(msg)
            return True, msg
        success, connect_msg = can_mgr.connect()
        msg = f"CAN Connect: {connect_msg}"
        print(msg)
        return success, msg

    if action_name.lower() in ["disconnect", "disconnect can"]:
        try:
            can_mgr.disconnect()
            msg = "CAN Disconnected"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"CAN Disconnect failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Start Cyclic CAN"):
        started_messages, failed_messages = can_mgr.start_all_cyclic_messages()
        msg = f"CAN Start Cyclic: Started: {', '.join(started_messages)}; Failed: {', '.join(failed_messages)}"
        print(msg)
        return len(started_messages) > 0, msg

    if action_name.startswith("Stop Cyclic CAN"):
        success = can_mgr.stop_all_cyclic_messages()
        msg = "CAN Stop Cyclic: Success" if success else "CAN Stop Cyclic: Some messages may not have stopped"
        print(msg)
        return success, msg

    if action_name.startswith("Start Trace"):
        from datetime import datetime
        try:
            filename_base = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            can_mgr.start_logging(filename_base)
            msg = f"CAN Trace Started: {filename_base}"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"CAN Start Trace failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Stop Trace"):
        try:
            can_mgr.stop_logging()
            msg = "CAN Trace Stopped"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"CAN Stop Trace failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Send Message"):
        try:
            data = {}
            if params:
                try:
                    data = parse_json_dict(params, default={}, strict=True)
                except Exception:
                    parts = [p.strip() for p in params.split(",") if p.strip()]
                    id_raw = parts[0]
                    arbid = parse_int(id_raw)
                    data_list = [
                        int(x, 16) if x.lower().startswith("0x") else int(x)
                        for x in parts[1:]
                    ]
                    data = {"id": arbid, "data": data_list}

            arbid = parse_int(data.get("id"))
            payload = data.get("data", [])
            is_extended = data.get("extended", False)
            if arbid is None:
                msg = "CAN Send Message failed: No message ID provided"
                print(msg)
                return False, msg
            can_mgr.send_message(arbid, payload, is_extended)
            msg = f"CAN Sent: ID=0x{arbid:X}, Data={payload}"
            print(msg)
            return True, msg
        except Exception as e:
            msg = f"CAN Send Message failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Start Cyclic By Name"):
        try:
            details = parse_json_dict(params, default={})
            msg_name = details.get("message_name") or details.get("name")
            cycle_ms = details.get("cycle_time") or details.get("cycle") or 100
            sigs = details.get("signals", {})
            if not msg_name:
                msg = "CAN Start Cyclic By Name failed: no message name provided"
                print(msg)
                return False, msg
            success = can_mgr.start_cyclic_message_by_name(msg_name, sigs, cycle_ms)
            msg = f"CAN Start Cyclic By Name: {msg_name} -> {success}"
            print(msg)
            return success, msg
        except Exception as e:
            msg = f"CAN Start Cyclic By Name failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Stop Cyclic By Name"):
        try:
            details = parse_json_dict(params, default={})
            msg_name = details.get("message_name") or details.get("name")
            if not msg_name:
                msg = "CAN Stop Cyclic By Name failed: no message name provided"
                print(msg)
                return False, msg
            if can_mgr.dbc_parser and can_mgr.dbc_parser.database:
                try:
                    message = can_mgr.dbc_parser.database.get_message_by_name(msg_name)
                    can_mgr.stop_cyclic_message(message.frame_id)
                    msg = f"CAN Stop Cyclic By Name: {msg_name} stopped"
                    print(msg)
                    return True, msg
                except Exception as e:
                    msg = f"CAN Stop Cyclic By Name: failed to stop {msg_name}: {e}"
                    print(msg)
                    return False, msg
            msg = "CAN Stop Cyclic By Name failed: DBC not loaded"
            print(msg)
            return False, msg
        except Exception as e:
            msg = f"CAN Stop Cyclic By Name failed: {e}"
            print(msg)
            return False, msg

    if "Read Signal Value" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal_name = details.get("signal_name", "")
            timeout = float(details.get("timeout", 2.0))
            if not signal_name:
                msg = "CAN Read Signal Value failed: no signal name provided"
                print(msg)
                return False, msg
            ok, value, diag_msg = can_mgr.read_signal_value(signal_name, timeout)
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Read Signal Value failed: {e}"
            print(msg)
            return False, msg

    if "Check Signal (Tolerance)" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal_name = details.get("signal_name", "")
            expected = float(details.get("expected_value", 0))
            tolerance = float(details.get("tolerance", 0.1))
            timeout = float(details.get("timeout", 2.0))
            if not signal_name:
                msg = "CAN Check Signal (Tolerance) failed: no signal name provided"
                print(msg)
                return False, msg
            ok, value, diag_msg = can_mgr.check_signal_tolerance(
                signal_name, expected, tolerance, timeout
            )
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Check Signal (Tolerance) failed: {e}"
            print(msg)
            return False, msg

    if "Conditional Jump" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal_name = details.get("signal_name", "")
            expected = float(details.get("expected_value", 0))
            tolerance = float(details.get("tolerance", 0.1))
            target_step = int(details.get("target_step", 0))
            if not signal_name:
                msg = "CAN Conditional Jump failed: no signal name provided"
                print(msg)
                return False, msg
            ok, diag_msg = can_mgr.conditional_jump_check(signal_name, expected, tolerance)
            print(diag_msg)
            ctx.emit_info(diag_msg)
            if ok:
                ctx.set_current_step(target_step - 1)
                msg = f"CAN Conditional Jump: jumping to step {target_step}"
                print(msg)
                return True, msg
            return True, diag_msg
        except Exception as e:
            msg = f"CAN Conditional Jump failed: {e}"
            print(msg)
            return False, msg

    if "Wait For Signal Change" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal_name = details.get("signal_name", "")
            initial_value = float(details.get("initial_value", 0))
            timeout = float(details.get("timeout", 5.0))
            poll_interval = float(details.get("poll_interval", 0.1))
            if not signal_name:
                msg = "CAN Wait For Signal Change failed: no signal name provided"
                print(msg)
                return False, msg
            ok, new_value, diag_msg = can_mgr.wait_for_signal_change(
                signal_name, initial_value, timeout, poll_interval
            )
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Wait For Signal Change failed: {e}"
            print(msg)
            return False, msg

    if "Monitor Signal Range" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal_name = details.get("signal_name", "")
            min_val = float(details.get("min_val", 0))
            max_val = float(details.get("max_val", 100))
            duration = float(details.get("duration", 5.0))
            poll_interval = float(details.get("poll_interval", 0.1))
            if not signal_name:
                msg = "CAN Monitor Signal Range failed: no signal name provided"
                print(msg)
                return False, msg
            ok, readings, diag_msg = can_mgr.monitor_signal_range(
                signal_name, min_val, max_val, duration, poll_interval
            )
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Monitor Signal Range failed: {e}"
            print(msg)
            return False, msg

    if "Compare Two Signals" in action_name:
        try:
            details = parse_json_dict(params, default={})
            signal1 = details.get("signal1", "")
            signal2 = details.get("signal2", "")
            tolerance = float(details.get("tolerance", 0.1))
            timeout = float(details.get("timeout", 2.0))
            if not signal1 or not signal2:
                msg = "CAN Compare Two Signals failed: signal names not provided"
                print(msg)
                return False, msg
            ok, values, diag_msg = can_mgr.compare_two_signals(
                signal1, signal2, tolerance, timeout
            )
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Compare Two Signals failed: {e}"
            print(msg)
            return False, msg

    if "Set Signal Value" in action_name:
        try:
            details = parse_json_dict(params, default={})
            raw_mid = details.get("message_id", 0)
            message_id = parse_int(raw_mid)
            signal_name = details.get("signal_name", "")
            target_value = float(details.get("target_value", 0))
            tolerance = float(details.get("tolerance", 0.1))
            verify_timeout = float(details.get("verify_timeout", 2.0))
            if not signal_name:
                msg = "CAN Set Signal Value failed: no signal name provided"
                print(msg)
                return False, msg
            db = getattr(can_mgr, "dbc_parser", None)
            if not db or not db.database:
                msg = "CAN Set Signal Value failed: DBC not loaded"
                print(msg)
                return False, msg
            msg_def = db.database.get_message_by_frame_id(message_id)
            can_mgr.send_message_with_overrides(msg_def.name, {signal_name: target_value})
            try:
                if message_id in getattr(can_mgr, "cyclic_tasks", {}):
                    cycle_ms = 100
                    try:
                        import can_messages
                        cfg = can_messages.CYCLIC_CAN_MESSAGES.get(msg_def.name, {})
                        cycle_ms = cfg.get("cycle_time", cycle_ms)
                    except Exception:
                        pass
                    base = {}
                    try:
                        base = dict(getattr(can_mgr, "last_sent_signals", {}).get(msg_def.name, {}))
                    except Exception:
                        base = {}
                    if not base:
                        try:
                            cache = getattr(can_mgr, "signal_cache", {})
                            for sig in msg_def.signals:
                                if sig.name in cache and "value" in cache[sig.name]:
                                    base[sig.name] = cache[sig.name]["value"]
                        except Exception:
                            base = {}
                    can_mgr.start_cyclic_message_by_name(msg_def.name, base, cycle_ms)
            except Exception:
                pass
            ok, detail = can_mgr.verify_signal_value(
                signal_name, target_value, timeout=verify_timeout, tolerance=tolerance
            )
            diag = detail if detail else f"Set {msg_def.name}.{signal_name} to {target_value}"
            print(diag)
            ctx.emit_info(diag)
            return ok, diag
        except Exception as e:
            msg = f"CAN Set Signal Value failed: {e}"
            print(msg)
            return False, msg

    if "Set Signal and Verify" in action_name:
        try:
            details = parse_json_dict(params, default={})
            raw_mid = details.get("message_id", 0)
            message_id = parse_int(raw_mid)
            signal_name = details.get("signal_name", "")
            target_value = float(details.get("target_value", 0))
            tolerance = float(details.get("tolerance", 0.1))
            verify_timeout = float(details.get("verify_timeout", 2.0))
            if not signal_name:
                msg = "CAN Set Signal and Verify failed: no signal name provided"
                print(msg)
                return False, msg
            ok, value, round_trip_time, diag_msg = can_mgr.set_signal_and_verify(
                message_id, signal_name, target_value, verify_timeout, tolerance
            )
            print(diag_msg)
            ctx.emit_info(diag_msg)
            return ok, diag_msg
        except Exception as e:
            msg = f"CAN Set Signal and Verify failed: {e}"
            print(msg)
            return False, msg

    if action_name.startswith("Check Message") or action_name.startswith("Listen For Message"):
        try:
            if params:
                try:
                    details = parse_json_dict(params, default={}, strict=True)
                    search_id = details.get("id") or details.get("message_id")
                    timeout = float(details.get("timeout", 2))
                except Exception:
                    parts = [p.strip() for p in params.split(",")]
                    id_raw = parts[0]
                    search_id = parse_int(id_raw)
                    timeout = float(parts[1]) if len(parts) > 1 else 2.0
            else:
                msg = "CAN Check Message failed: no parameters provided"
                print(msg)
                return False, msg

            found_event = threading.Event()
            found_msg = {"msg": None}

            def _listener(msg):
                if msg.arbitration_id == search_id:
                    found_msg["msg"] = msg
                    found_event.set()

            can_mgr.add_listener(_listener)
            result = found_event.wait(timeout)
            try:
                can_mgr.listeners.remove(_listener)
            except Exception:
                pass

            if result:
                msg = f"CAN Message received: ID=0x{search_id:X}"
                print(msg)
                return True, msg
            msg = f"CAN Message not received within {timeout}s: ID=0x{search_id:X}"
            print(msg)
            return False, msg
        except Exception as e:
            msg = f"CAN Check Message failed: {e}"
            print(msg)
            return False, msg

    msg = f"Unsupported CAN action: {action_name}"
    print(msg)
    return False, msg
