from ticketpilot.triage.text import clean_ticket_text


def test_quoted_reply_is_removed():
    text = "Still broken.\n\nOn Mon, 3 Aug 2026 at 10:00, Support <help@loomwork.dev> wrote:\n> try again\n> thanks"
    assert clean_ticket_text(text) == "Still broken."


def test_whitespace_is_collapsed():
    assert clean_ticket_text("hello   there \r\n\r\n\r\n\r\n bye ") == "hello there\n\nbye"
