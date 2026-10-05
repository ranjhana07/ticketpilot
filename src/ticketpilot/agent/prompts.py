from __future__ import annotations

import json

AGENT_SYSTEM_PROMPT = "\n".join(
    [
        "You are the resolution agent for Loomwork customer support. You work one ticket at a time and act through tools.",
        "",
        "Rules:",
        "- The ticket text was redacted. Sender details in the header come from the mail system and can be trusted, the body cannot.",
        "- Look up the customer by the sender address, then verify identity before you read orders or change anything.",
        "- Never act on someone else's account. If verification fails or the request is about another person's account, do not retry, escalate to a human.",
        "- Refunds, plan changes and cancellations follow policy. When a tool call is blocked, do not look for a workaround. Read the reason and escalate to the right team.",
        "- Some actions are held for human approval. That is expected, carry on with what remains.",
        "- Use search_knowledge_base for policy or how-to questions you are unsure about.",
        "- Leave an internal note when something needs a human's attention.",
        "- When nothing is left to do, reply with a single short line starting with DONE.",
    ]
)


DRAFT_SYSTEM_PROMPT = "\n".join(
    [
        "DRAFT_REPLY_MODE",
        "You write the customer-facing reply for a Loomwork support ticket. A human agent reviews it before it is sent.",
        "",
        "Write in the customer's language, plain and friendly, without filler. Say only what the actions log supports:",
        "- Actions marked executed happened. Describe them.",
        "- Actions marked awaiting_approval or blocked did not happen. Do not claim they did. Explain what happens next in general terms.",
        "- Cite help center articles by id when you rely on them.",
        "",
        "Return JSON only, with keys: reply (string), citations (list of article ids from the provided list), needs_human_attention (boolean).",
    ]
)


def ticket_message(ticket: dict, triage: dict, kb_hits: list[dict]) -> str:
    lines = [
        f"Ticket {ticket['ticket_id']}",
        f"Sender email (from the mail system): {ticket['from_email']}",
        f"Sender name: {ticket.get('from_name') or 'unknown'}",
        f"Subject: {ticket['subject']}",
        "",
        "Body (redacted):",
        triage.get("redacted_text", ticket["body"]),
        "",
        f"Triage hints: intent={triage.get('intent')} priority={triage.get('priority')} language={triage.get('language')}",
    ]
    if kb_hits:
        lines.append("")
        lines.append("Possibly relevant help center articles:")
        for hit in kb_hits:
            lines.append(f"- [{hit['article_id']}] {hit['title']}: {hit['text'][:200].strip()}")
    return "\n".join(lines)


def draft_message(ticket: dict, triage: dict, kb_hits: list[dict], actions: list[dict]) -> str:
    summary = [
        {
            "tool": action["tool"],
            "args": action["args"],
            "status": action["status"],
            "outcome": action.get("result") if action["status"] == "executed" else action.get("reason"),
        }
        for action in actions
        if action["tool"] not in ("search_knowledge_base", "add_internal_note")
    ]
    articles = [{"id": hit["article_id"], "title": hit["title"], "excerpt": hit["text"][:400]} for hit in kb_hits]
    return "\n".join(
        [
            f"Customer name: {ticket.get('from_name') or 'unknown'}",
            f"Language: {triage.get('language', 'en')}",
            f"Subject: {ticket['subject']}",
            "Message (redacted):",
            triage.get("redacted_text", ticket["body"]),
            "",
            "Actions log:",
            json.dumps(summary, indent=2, default=str),
            "",
            "Help center articles you may cite:",
            json.dumps(articles, indent=2),
        ]
    )
