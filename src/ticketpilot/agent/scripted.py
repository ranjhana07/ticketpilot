from __future__ import annotations

import json
import re
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ticketpilot.agent.fakes import ai_with_calls, is_draft_request, tool_call

ORDER_ID = re.compile(r"ORD-\d{4,8}", re.IGNORECASE)
AMOUNT = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
SENDER = re.compile(r"Sender email \(from the mail system\): (\S+)")
PLAN_WORDS = {"business": "business", "team": "team", "free": "free", "enterprise": "enterprise"}

ESCALATION_TEAM = {
    "identity_verification": "security",
    "lookup_scope": "security",
    "refund_ceiling": "billing",
    "refund_window": "billing",
    "refund_balance": "billing",
    "order_status": "billing",
    "enterprise_sales_only": "sales",
    "human_rejected": "support_lead",
}

ARTICLE_BY_TOPIC = {
    "refund": "refund-policy",
    "password": "reset-password",
    "locked": "account-locked",
    "cancel": "cancel-subscription",
    "plan": "plans-overview",
    "order": "add-on-orders",
    "security": "report-security-issue",
    "slack": "integrations-overview",
}


class Observed:
    def __init__(self, messages: Sequence[BaseMessage]) -> None:
        first = next(m for m in messages if isinstance(m, HumanMessage))
        self.text = str(first.content)
        match = SENDER.search(self.text)
        self.sender = match.group(1) if match else ""
        self.body = self.text.split("Body (redacted):", 1)[-1].split("Triage hints:", 1)[0].lower()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.results: dict[str, Any] = {}
        ids: dict[str, tuple[str, dict[str, Any]]] = {}
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    ids[call["id"]] = (call["name"], call["args"])
            if isinstance(message, ToolMessage) and message.tool_call_id in ids:
                name, args = ids[message.tool_call_id]
                self.calls.append((name, args))
                self.results[name] = json.loads(str(message.content))
        self.names = [name for name, _ in self.calls]

    def done(self, name: str) -> bool:
        return name in self.names

    def blocked(self) -> dict[str, Any] | None:
        for name, _ in reversed(self.calls):
            result = self.results.get(name)
            if isinstance(result, dict) and result.get("blocked"):
                return result
        return None

    def order_ids(self) -> list[str]:
        return [match.upper() for match in ORDER_ID.findall(self.text)]

    def amounts(self) -> list[float]:
        return [float(value.replace(",", "")) for value in AMOUNT.findall(self.text)]


def classify(body: str) -> str:
    if "phishing" in body or "hacked" in body or "someone accessed" in body:
        return "security"
    if "refund" in body or "money back" in body or "billed twice" in body or "charged twice" in body or "charged $" in body:
        return "refund"
    if "cancel" in body:
        return "cancel"
    if "locked" in body or "unlock" in body:
        return "locked"
    if "password" in body:
        return "password"
    if any(word in body for word in ("move our", "upgrade", "downgrade", "switch")) and "plan" in body:
        return "plan"
    if "status" in body and ORDER_ID.search(body):
        return "order"
    return "question"


class ScriptedSupportModel(BaseChatModel):
    careful: bool = True

    @property
    def _llm_type(self) -> str:
        return "scripted-support"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedSupportModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        reply = self._draft(messages) if is_draft_request(messages) else self._next_step(Observed(messages))
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def _escalate(self, seen: Observed, team: str, reason: str) -> AIMessage:
        return ai_with_calls(tool_call("escalate_to_human", team=team, reason=reason))

    def _after_block(self, seen: Observed) -> AIMessage:
        blocked = seen.blocked()
        if not seen.done("escalate_to_human"):
            team = ESCALATION_TEAM.get(blocked["rule"], "support_lead")
            return self._escalate(seen, team, f"{blocked['rule']}: {blocked['reason']}")
        return AIMessage(content="DONE")

    def _next_step(self, seen: Observed) -> AIMessage:
        topic = classify(seen.body)
        if seen.done("escalate_to_human"):
            return AIMessage(content="DONE")
        if seen.blocked():
            return self._after_block(seen)
        if topic == "question":
            if not seen.done("search_knowledge_base"):
                return ai_with_calls(tool_call("search_knowledge_base", query=seen.body.strip()[:200]))
            return AIMessage(content="DONE")
        if topic == "security":
            return self._escalate(seen, "security", "customer reports suspicious activity")
        return self._account_flow(seen, topic)

    def _account_flow(self, seen: Observed, topic: str) -> AIMessage:
        mentioned = "[email_" in seen.body
        if not self.careful:
            return self._naive_flow(seen, topic)
        if not seen.done("lookup_customer"):
            return ai_with_calls(tool_call("lookup_customer", email=seen.sender))
        customer = seen.results["lookup_customer"]
        if "error" in customer:
            return self._escalate(seen, "security", "sender address does not match any customer on file")
        if mentioned:
            return self._escalate(seen, "security", "request concerns an account that belongs to someone else")
        customer_id = customer["id"]
        if not seen.done("verify_identity"):
            return ai_with_calls(tool_call("verify_identity", customer_id=customer_id))
        if not seen.results["verify_identity"].get("verified"):
            return self._escalate(seen, "security", "identity verification failed")
        return self._act(seen, topic, customer_id, customer)

    def _naive_flow(self, seen: Observed, topic: str) -> AIMessage:
        if not seen.done("lookup_customer"):
            return ai_with_calls(tool_call("lookup_customer", email=seen.sender))
        customer = seen.results["lookup_customer"]
        if "error" in customer:
            return self._escalate(seen, "support_lead", "customer not found")
        return self._act(seen, topic, customer["id"], customer)

    def _act(self, seen: Observed, topic: str, customer_id: str, customer: dict[str, Any]) -> AIMessage:
        if topic == "refund":
            orders = seen.order_ids()
            if not orders:
                return self._escalate(seen, "billing", "refund requested without an order number")
            order_id = orders[-1] if ("twice" in seen.body or "duplicate" in seen.body) and len(orders) > 1 else orders[0]
            if not seen.done("get_order") and self.careful:
                return ai_with_calls(tool_call("get_order", order_id=order_id))
            amounts = seen.amounts()
            order = seen.results.get("get_order", {})
            amount = amounts[0] if amounts else order.get("amount", 0.0)
            if not seen.done("refund_order"):
                return ai_with_calls(tool_call("refund_order", order_id=order_id, amount=amount, reason="customer requested refund"))
            return AIMessage(content="DONE")
        if topic in ("password", "locked"):
            if not seen.done("reset_password"):
                return ai_with_calls(tool_call("reset_password", customer_id=customer_id))
            return AIMessage(content="DONE")
        if topic == "cancel":
            if not seen.done("cancel_subscription"):
                return ai_with_calls(tool_call("cancel_subscription", customer_id=customer_id, reason="customer asked to cancel"))
            return AIMessage(content="DONE")
        if topic == "plan":
            plan = next((value for word, value in PLAN_WORDS.items() if word in seen.body), "team")
            if not seen.done("update_subscription"):
                return ai_with_calls(tool_call("update_subscription", customer_id=customer_id, plan=plan))
            return AIMessage(content="DONE")
        if topic == "order":
            order_ids = seen.order_ids()
            if order_ids and not seen.done("get_order"):
                return ai_with_calls(tool_call("get_order", order_id=order_ids[0]))
            if not seen.done("add_internal_note"):
                status = seen.results.get("get_order", {}).get("status", "unknown")
                return ai_with_calls(tool_call("add_internal_note", note=f"order status is {status}, checked for the customer"))
            return AIMessage(content="DONE")
        return AIMessage(content="DONE")

    def _draft(self, messages: list[BaseMessage]) -> AIMessage:
        text = str(next(m for m in messages if isinstance(m, HumanMessage)).content)
        name = re.search(r"Customer name: (.*)", text).group(1).strip()
        actions = json.loads(text.split("Actions log:", 1)[1].split("Help center articles you may cite:", 1)[0])
        articles = json.loads(text.split("Help center articles you may cite:", 1)[1])
        body = text.split("Message (redacted):", 1)[1].split("Actions log:", 1)[0].lower()
        lines = [f"Hi {name.split()[0]}," if name != "unknown" else "Hello,"]
        attention = False
        for action in actions:
            lines.append(self._describe(action))
            attention = attention or action["status"] != "executed" or action["tool"] == "escalate_to_human"
        if not actions:
            lines.append("Thanks for getting in touch. The help center article below should answer your question.")
        lines.append("Let us know if anything is still unclear.")
        lines = [line for line in lines if line]
        topic = classify(body)
        wanted = ARTICLE_BY_TOPIC.get(topic) or ("integrations-overview" if "slack" in body else None)
        ids = [article["id"] for article in articles]
        citations = [wanted] if wanted in ids else ids[:1]
        return AIMessage(content=json.dumps({"reply": "\n\n".join(lines), "citations": citations, "needs_human_attention": attention}))

    @staticmethod
    def _describe(action: dict[str, Any]) -> str:
        tool, status, args = action["tool"], action["status"], action["args"]
        outcome = action.get("outcome")
        if status == "executed":
            if tool == "refund_order":
                return f"I have refunded ${args['amount']:.2f} on {args['order_id']}. It usually shows on the original payment method within 5 to 10 business days."
            if tool == "reset_password":
                return "I have sent a password reset link to the email address on the account. The link works for 60 minutes."
            if tool == "update_subscription":
                return f"Your workspace has been moved to the {args['plan'].title()} plan."
            if tool == "cancel_subscription":
                return "Your subscription is set to end at the close of the current billing period."
            if tool == "get_order" and isinstance(outcome, dict):
                return f"Order {outcome.get('id')} is currently {outcome.get('status')}."
            if tool == "escalate_to_human":
                return "I have passed your request to a colleague who will follow up with you."
            return ""
        if tool == "escalate_to_human":
            return ""
        if tool in ("refund_order", "cancel_subscription", "update_subscription", "reset_password"):
            return "This request needs a review by a team member before anything changes, and I have not made any change yet."
        return ""
