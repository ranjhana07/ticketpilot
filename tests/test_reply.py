from langchain_core.messages import AIMessage

from ticketpilot.agent.reply import message_text, parse_draft


def test_valid_json_with_known_citations():
    text = '{"reply": "Hi Maya, done.", "citations": ["refund-policy", "made-up"], "needs_human_attention": true}'
    draft = parse_draft(text, {"refund-policy", "request-refund"})
    assert draft == {"reply": "Hi Maya, done.", "citations": ["refund-policy"], "needs_human_attention": True}


def test_json_wrapped_in_prose_is_found():
    text = 'Here you go:\n{"reply": "Hello", "citations": []}\nthanks'
    assert parse_draft(text, set())["reply"] == "Hello"


def test_plain_text_becomes_the_reply():
    draft = parse_draft("Just text, no json", {"a"})
    assert draft["reply"] == "Just text, no json" and draft["citations"] == []


def test_duplicate_citations_are_collapsed():
    draft = parse_draft('{"reply": "x", "citations": ["a", "a", "b"]}', {"a", "b"})
    assert draft["citations"] == ["a", "b"]


def test_message_text_joins_text_blocks():
    message = AIMessage(content=[{"type": "text", "text": "one "}, {"type": "tool_use", "id": "1"}, {"type": "text", "text": "two"}])
    assert message_text(message) == "one two"
