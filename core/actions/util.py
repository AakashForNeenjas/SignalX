import time


def handle_utility(action, params, ctx):
    # Utility Actions
    if action == "Wait":
        duration = float(params)
        print(f"Wait: {duration}s (starting)")
        start_time = time.time()
        while time.time() - start_time < duration:
            if not ctx.running:
                msg = "Wait: Interrupted"
                print(msg)
                return False, msg
            time.sleep(0.1)
        msg = f"Wait: {duration}s (completed)"
        print(msg)
        return True, msg

    # Button Actions
    if action == "Initialize Instruments":
        success, msg = ctx.inst_mgr.initialize_instruments()
        print(f"Initialize Instruments: {msg}")
        return success, msg

    msg = f"Unknown action: {action}"
    print(msg)
    return False, msg
