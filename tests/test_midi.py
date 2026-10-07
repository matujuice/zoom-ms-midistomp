from zoomms.midi import parse_identity_reply


def test_parse_identity_reply():
    body = [0x7E, 0x00, 0x06, 0x02, 0x52, 0x5F, 0x00, 0x00, 0x00, ord("2"), ord("."), ord("0"), ord("0")]
    ident = parse_identity_reply(body)
    assert (ident.manufacturer, ident.family, ident.version) == (0x52, 0x5F, "2.00")


def test_ignores_other_sysex():
    assert parse_identity_reply([0x52, 0x00, 0x5F, 0x50]) is None
