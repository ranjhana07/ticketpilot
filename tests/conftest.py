from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ticketpilot.helpdesk.app import create_app

FIXED_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def helpdesk_app():
    return create_app(clock=lambda: FIXED_NOW)


@pytest.fixture()
def helpdesk(helpdesk_app):
    with TestClient(helpdesk_app) as client:
        yield client


@pytest.fixture(scope="session")
def triage_pipeline():
    from ticketpilot.data.synthetic import generate_tickets
    from ticketpilot.triage.baseline import TfidfLogRegClassifier
    from ticketpilot.triage.pipeline import TriagePipeline

    tickets = generate_tickets(1500, seed=77)
    texts = [t.text for t in tickets]
    intent = TfidfLogRegClassifier().fit(texts, [t.intent for t in tickets])
    priority = TfidfLogRegClassifier().fit(texts, [t.priority for t in tickets])
    return TriagePipeline(intent, priority)


@pytest.fixture()
def inbox(helpdesk, triage_pipeline):
    from dataclasses import replace

    from ticketpilot.agent.scripted import ScriptedSupportModel
    from ticketpilot.api.app import create_api
    from ticketpilot.api.container import build_container
    from ticketpilot.config import Settings
    from ticketpilot.embeddings import HashingEmbedder
    from ticketpilot.kb.rerank import OverlapReranker

    settings = replace(Settings(), llm_provider="scripted", embedder="hashing", reranker="overlap")
    container = build_container(
        settings,
        http=helpdesk,
        llm=ScriptedSupportModel(),
        embedder=HashingEmbedder(),
        reranker=OverlapReranker(),
        triage=triage_pipeline,
    )
    with TestClient(create_api(container)) as client:
        yield client
