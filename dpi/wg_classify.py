WG_TYPES = {
    1: ("HANDSHAKE_INIT",     148),
    2: ("HANDSHAKE_RESPONSE",  92),
    3: ("COOKIE_REPLY",        64),
    4: ("TRANSPORT_DATA",    None),
}


def classify(payload: bytes):
    if len(payload) < 4:
        return None
    msg_type = payload[0]
    if msg_type not in WG_TYPES or payload[1:4] != b"\x00\x00\x00":
        return None
    label, expected_len = WG_TYPES[msg_type]
    if expected_len is not None:
        if len(payload) != expected_len:
            return None
        return label, msg_type, True
    if len(payload) < 24:
        return None
    return label, msg_type, False
