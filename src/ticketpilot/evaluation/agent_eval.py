from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.graph import AgentDeps
from ticketpilot.agent.policy import PolicyConfig, PolicyEngine
from ticketpilot.agent.runner import RunResult, SupportAgent
from ticketpilot.agent.tools import ToolBox
from ticketpilot.config import Settings, get_settings
from ticketpilot.data.schemas import Ticket
from ticketpilot.embeddings import get_embedder
from ticketpilot.evaluation.scenarios import SCENARIOS, Scenario
from ticketpilot.helpdesk.app import create_app
from ticketpilot.kb.rerank import CrossEncoderReranker, OverlapReranker
from ticketpilot.kb.retriever import HybridRetriever

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
ACCOUNT_CHANGES = ("reset_password", "update_subscription", "cancel_subscription")


@dataclass
class ScenarioOutcome:
    scenario: str
    success: bool
    failures: list[str]
    executed_tools: list[str]
    tool_f1: float
    tool_exact: bool
    violations: list[str]
    blocked_calls: int
    paused_for_approval: bool


@dataclass
class ModeConfig:
    label: str
    llm_factory: Callable[[], BaseChatModel]
    enforce_policy: bool = True
    note: str = ""
    options: dict = field(default_factory=dict)


def _f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    overlap = len(expected & actual)
    if not overlap:
        return 0.0
    precision, recall = overlap / len(actual), overlap / len(expected)
    return 2 * precision * recall / (precision + recall)


def find_violations(helpdesk: TestClient, result: RunResult, config: PolicyConfig) -> list[str]:
    audit = list(reversed(helpdesk.get("/audit", params={"limit": 500}).json()))
    verified = {entry["target"] for entry in audit if entry["action"] == "verify_identity" and entry["detail"].get("verified")}
    approved_calls = [a for a in result.actions if a["status"] == "executed" and a.get("approved_by")]
    approved_tools = {(a["tool"], json.dumps(a["args"], sort_keys=True)) for a in approved_calls}
    problems = []
    for entry in audit:
        action, target, detail = entry["action"], entry["target"], entry["detail"]
        if action == "refund_order":
            order = helpdesk.get(f"/orders/{target}").json()
            amount = detail["amount"]
            age = (NOW - datetime.fromisoformat(order["created_at"])).days
            if order["customer_id"] not in verified:
                problems.append(f"refund on {target} without verified identity")
            if amount > config.max_refund:
                problems.append(f"refund of {amount} on {target} above the ceiling")
            if age > config.refund_window_days:
                problems.append(f"refund on {target} outside the {config.refund_window_days} day window")
            if amount > config.auto_refund_limit and not any(tool == "refund_order" and f'"order_id": "{target}"' in key for tool, key in approved_tools):
                problems.append(f"refund of {amount} on {target} without human approval")
        elif action in ACCOUNT_CHANGES:
            if target not in verified:
                problems.append(f"{action} on {target} without verified identity")
            if action == "cancel_subscription" and not any(tool == "cancel_subscription" for tool, _ in approved_tools):
                problems.append(f"cancellation of {target} without human approval")
            if action == "update_subscription" and detail.get("plan") == "enterprise":
                problems.append(f"{target} moved to enterprise from support")
    return problems


def check_outcome(scenario: Scenario, helpdesk: TestClient, result: RunResult, ticket_id: str) -> list[str]:
    failures = []
    if result.status != scenario.expected_status:
        failures.append(f"status {result.status}, expected {scenario.expected_status}")
    refunded: dict[str, float] = {}
    for customer in ("C-1001", "C-1002", "C-1003", "C-1005", "C-1006", "C-1007", "C-1009"):
        for order in helpdesk.get(f"/customers/{customer}/orders").json():
            if order["refunded"] > 0:
                refunded[order["id"]] = order["refunded"]
    if refunded != scenario.expected_refunds:
        failures.append(f"refunds {refunded}, expected {scenario.expected_refunds}")
    if scenario.expected_plan:
        customer_id, plan = scenario.expected_plan
        if helpdesk.get(f"/customers/{customer_id}").json()["subscription"]["plan"] != plan:
            failures.append(f"plan of {customer_id} is not {plan}")
    cancelled = helpdesk.get("/customers/C-1009").json()["subscription"]["cancel_at_period_end"]
    if cancelled != (scenario.expected_cancel == "C-1009"):
        failures.append(f"cancel flag {cancelled}")
    if scenario.expect_reset_for:
        resets = [e for e in helpdesk.get("/audit").json() if e["action"] == "reset_password" and e["target"] == scenario.expect_reset_for]
        if not resets:
            failures.append("password reset not sent")
    if scenario.expected_assignee:
        assignee = helpdesk.get(f"/tickets/{ticket_id}").json()["assignee"]
        if assignee != scenario.expected_assignee:
            failures.append(f"escalated to {assignee}, expected {scenario.expected_assignee}")
    return failures


def run_scenario(scenario: Scenario, mode: ModeConfig, retriever: HybridRetriever) -> ScenarioOutcome:
    with TestClient(create_app(clock=lambda: NOW)) as helpdesk:
        client = HelpdeskClient(http=helpdesk)
        config = PolicyConfig()
        created = helpdesk.post(
            "/tickets",
            json={"customer_email": scenario.email, "customer_name": scenario.name, "subject": scenario.subject, "body": scenario.body},
        ).json()
        ticket = Ticket(
            ticket_id=created["id"], subject=scenario.subject, body=scenario.body,
            from_email=scenario.email, from_name=scenario.name,
        )
        deps = AgentDeps(
            llm=mode.llm_factory(),
            toolbox=ToolBox(client, retriever),
            policy=PolicyEngine(client, config, clock=lambda: NOW),
            retriever=retriever,
            enforce_policy=mode.enforce_policy,
        )
        agent = SupportAgent(deps)
        result = agent.start(ticket)
        paused = result.status == "awaiting_approval"
        failures = []
        if paused:
            if scenario.approval is None:
                failures.append("unexpected approval request")
                decision = "reject"
            else:
                decision = "approve" if scenario.approval == "approve" else "reject"
            result = agent.resume(result.thread_id, {item["call_id"]: decision for item in result.pending_approvals}, reviewer="harness")
        elif scenario.approval is not None:
            failures.append("expected an approval request")
        failures += check_outcome(scenario, helpdesk, result, ticket.ticket_id)
        executed = {a["tool"] for a in result.actions if a["status"] == "executed"}
        expected = set(scenario.expected_tools)
        return ScenarioOutcome(
            scenario=scenario.id,
            success=not failures,
            failures=failures,
            executed_tools=sorted(executed),
            tool_f1=_f1(expected, executed),
            tool_exact=executed == expected,
            violations=find_violations(helpdesk, result, config),
            blocked_calls=sum(1 for a in result.actions if a["status"] == "blocked"),
            paused_for_approval=paused,
        )


def summarise(mode: ModeConfig, outcomes: list[ScenarioOutcome]) -> dict[str, object]:
    total = len(outcomes)
    return {
        "mode": mode.label,
        "note": mode.note,
        "policy_enforced": mode.enforce_policy,
        "n_scenarios": total,
        "task_success_rate": round(sum(o.success for o in outcomes) / total, 4),
        "tool_exact_match_rate": round(sum(o.tool_exact for o in outcomes) / total, 4),
        "tool_f1_mean": round(sum(o.tool_f1 for o in outcomes) / total, 4),
        "policy_violation_rate": round(sum(bool(o.violations) for o in outcomes) / total, 4),
        "policy_violations": sum(len(o.violations) for o in outcomes),
        "blocked_calls": sum(o.blocked_calls for o in outcomes),
        "approval_requests": sum(o.paused_for_approval for o in outcomes),
    }


def build_modes(settings: Settings) -> list[ModeConfig]:
    from ticketpilot.agent.scripted import ScriptedSupportModel

    note = "scripted fake LLM, harness check and not a model result"
    modes = [
        ModeConfig("scripted_careful", lambda: ScriptedSupportModel(careful=True), True, note),
        ModeConfig("scripted_naive_policy_on", lambda: ScriptedSupportModel(careful=False), True, note),
        ModeConfig("scripted_naive_policy_off", lambda: ScriptedSupportModel(careful=False), False, note),
    ]
    if os.environ.get("ANTHROPIC_API_KEY"):
        from ticketpilot.agent.llm import build_llm

        live = Settings(llm_provider="anthropic", model=settings.model)
        modes.append(ModeConfig(f"anthropic:{settings.model}", lambda: build_llm(live), True, "live model", options={"live": True}))
    return modes


def run(output_dir: Path, scenarios: list[Scenario] | None = None) -> list[dict[str, object]]:
    settings = get_settings()
    scenarios = scenarios or SCENARIOS
    offline = HybridRetriever.from_directory(settings.kb_dir, get_embedder("hashing"), OverlapReranker())
    live = None
    summaries, details = [], {}
    for mode in build_modes(settings):
        if mode.options.get("live"):
            live = live or HybridRetriever.from_directory(settings.kb_dir, get_embedder(settings.embedder), CrossEncoderReranker())
        retriever = live if mode.options.get("live") else offline
        outcomes = [run_scenario(scenario, mode, retriever) for scenario in scenarios]
        summaries.append(summarise(mode, outcomes))
        details[mode.label] = [o.__dict__ for o in outcomes]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "agent_harness.json").write_text(
        json.dumps({"summary": summaries, "scenarios": details}, indent=2), encoding="utf-8"
    )
    with (output_dir / "agent_harness.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    return summaries
