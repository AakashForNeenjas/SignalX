import re


def detect_req_resp_pairs(messages):
    """
    Heuristic pairing of request/response messages by name.
    Pairs patterns: <Name>_Request / <Name>_Response, <Name>Req / <Name>Resp.
    Returns list of dicts: {"req_name": ..., "resp_name": ...}
    """
    pairs = []
    by_name = {m.name: m for m in messages}
    for m in messages:
        name = m.name
        # _Request -> _Response
        if name.endswith("_Request"):
            base = name[:-8]
            resp_name = f"{base}_Response"
            if resp_name in by_name:
                pairs.append({"req_name": name, "resp_name": resp_name})
        # Req -> Resp
        if name.endswith("Req"):
            base = name[:-3]
            resp_name = f"{base}Resp"
            if resp_name in by_name:
                pairs.append({"req_name": name, "resp_name": resp_name})
    return pairs
