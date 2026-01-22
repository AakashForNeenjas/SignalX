def handle_instr(action_name, params, ctx):
    name = action_name.strip().upper()
    if name == "INITIALIZE INSTRUMENTS":
        s, m = ctx.inst_mgr.initialize_instruments()
        msg = f"INSTR Init All: {m}"
        print(msg)
        return s, msg
    if name == "INIT PS":
        s, m = ctx.inst_mgr.init_ps()
        msg = f"INSTR Init PS: {m}"
        print(msg)
        return s, msg
    if name == "INIT GS":
        s, m = ctx.inst_mgr.init_gs()
        msg = f"INSTR Init GS: {m}"
        print(msg)
        return s, msg
    if name == "INIT OS":
        s, m = ctx.inst_mgr.init_os()
        msg = f"INSTR Init OS: {m}"
        print(msg)
        return s, msg
    if name == "END PS":
        s, m = ctx.inst_mgr.end_ps()
        msg = f"INSTR End PS: {m}"
        print(msg)
        return s, msg
    if name == "END GS":
        s, m = ctx.inst_mgr.end_gs()
        msg = f"INSTR End GS: {m}"
        print(msg)
        return s, msg
    if name == "END OS":
        s, m = ctx.inst_mgr.end_os()
        msg = f"INSTR End OS: {m}"
        print(msg)
        return s, msg

    msg = f"Unsupported INSTR action: {action_name}"
    print(msg)
    return False, msg
