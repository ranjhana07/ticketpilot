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


def test_card_numbers_need_a_valid_checksum():
    assert "[CARD_1]" in redact("card 4111 1111 1111 1111 expired").text
    assert "[CARD_1]" in redact("card 4111-1111-1111-1111").text
    assert redact("tracking 1234 5678 9012 3456").spans == []


def test_ssn_and_ip_and_secret():
    text = "ssn 123-45-6789 from 203.0.113.42 token sk_live_abcdefghijklmnop1234"
    result = redact(text)
    assert result.labels == {"SSN", "IP", "SECRET"}


def test_iban_checksum():
    assert redact("pay to DE89 3704 0044 0532 0130 00 now").labels == {"IBAN"}
    assert redact("code DE00 1234 5678 9012 3456 78").spans == []


def test_version_numbers_are_not_ips():
    assert redact("running build 2.4.1.7.9").spans == []
