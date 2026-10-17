import pytest

from ticketpilot.agent.scripted import ScriptedSupportModel
from ticketpilot.embeddings import HashingEmbedder
from ticketpilot.evaluation.agent_eval import ModeConfig, _f1, run_scenario, summarise
from ticketpilot.evaluation.scenarios import SCENARIOS
from ticketpilot.config import get_settings
from ticketpilot.kb.rerank import OverlapReranker
from ticketpilot.kb.retriever import HybridRetriever


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever.from_directory(get_settings().kb_dir, HashingEmbedder(), OverlapReranker())


def outcomes(mode, retriever):
    return [run_scenario(scenario, mode, retriever) for scenario in SCENARIOS]


def test_f1_helper():
    assert _f1({"a", "b"}, {"a", "b"}) == 1.0
    assert _f1({"a"}, {"b"}) == 0.0
    assert _f1(set(), set()) == 1.0


def test_scenario_ids_are_unique():
    assert len({s.id for s in SCENARIOS}) == len(SCENARIOS)


def test_careful_model_has_no_violations_and_passes(retriever):
    mode = ModeConfig("careful", lambda: ScriptedSupportModel(careful=True))
    summary = summarise(mode, outcomes(mode, retriever))
    assert summary["policy_violation_rate"] == 0.0
    assert summary["task_success_rate"] == 1.0
    assert summary["approval_requests"] == 4


def test_guard_blocks_every_unsafe_action_of_the_naive_model(retriever):
    mode = ModeConfig("naive_on", lambda: ScriptedSupportModel(careful=False))
    summary = summarise(mode, outcomes(mode, retriever))
    assert summary["policy_violation_rate"] == 0.0
    assert summary["blocked_calls"] > 0


def test_audit_catches_violations_when_the_guard_is_off(retriever):
    mode = ModeConfig("naive_off", lambda: ScriptedSupportModel(careful=False), enforce_policy=False)
    summary = summarise(mode, outcomes(mode, retriever))
    assert summary["policy_violation_rate"] > 0.3
