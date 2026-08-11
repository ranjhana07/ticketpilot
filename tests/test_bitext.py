import random

from ticketpilot.data import bitext

SAMPLE = (
    "flags,instruction,category,intent,response\n"
    'B,"where is my order {{Order Number}}",ORDER,track_order,"ok"\n'
    'BQ,"i want a refund of {{Currency Symbol}}{{Refund Amount}}",REFUND,get_refund,"ok"\n'
)


def test_fill_placeholders_removes_markers():
    text = bitext.fill_placeholders("order {{Order Number}} for {{Person Name}} {{Unknown Thing}}", random.Random(1))
    assert "{{" not in text
    assert text.startswith("order ")


def test_load_tickets_reads_intent_and_category(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(SAMPLE, encoding="utf-8")
    tickets = bitext.load_tickets(csv_path)
    assert [t.intent for t in tickets] == ["track_order", "get_refund"]
    assert tickets[0].meta["category"] == "ORDER"
    assert "{{" not in tickets[1].body


def test_load_rows_missing_file(tmp_path):
    try:
        bitext.load_rows(tmp_path / "nope.csv")
    except FileNotFoundError as error:
        assert "data download" in str(error)
    else:
        raise AssertionError("expected FileNotFoundError")
