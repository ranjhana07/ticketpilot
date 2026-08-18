from ticketpilot.triage.pii import redact, restore


def test_email_is_redacted():
    result = redact("write to maya.reed@brightfield.io please")
    assert result.text == "write to [EMAIL_1] please"
    assert result.mapping["[EMAIL_1]"] == "maya.reed@brightfield.io"


def test_phone_formats():
    for number in ("+1 415 555 0132", "(415) 555-0132", "+44 7539 774786", "415-555-0132"):
        result = redact(f"call me on {number} tomorrow")
        assert "[PHONE_1]" in result.text, number


def test_order_ids_are_not_phones():
    result = redact("order ORD-68342 is late, invoice 20240315")
    assert result.spans == []


def test_numbering_per_label():
    result = redact("a@x.io and b@y.io")
    assert result.text == "[EMAIL_1] and [EMAIL_2]"


def test_restore_roundtrip():
    original = "ping a@x.io or +1 415 555 0132"
    result = redact(original)
    assert restore(result.text, result.mapping) == original
