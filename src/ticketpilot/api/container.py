from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import httpx
from langchain_core.language_models import BaseChatModel

from ticketpilot.agent.client import HelpdeskClient
from ticketpilot.agent.graph import AgentDeps
from ticketpilot.agent.llm import build_llm
from ticketpilot.agent.policy import PolicyConfig, PolicyEngine
from ticketpilot.agent.runner import SupportAgent
from ticketpilot.agent.tools import ToolBox
from ticketpilot.config import Settings
from ticketpilot.embeddings import Embedder, get_embedder
from ticketpilot.kb.rerank import CrossEncoderReranker, OverlapReranker, Reranker
from ticketpilot.kb.retriever import HybridRetriever
from ticketpilot.triage.pipeline import TriagePipeline, load_pipeline

log = logging.getLogger("ticketpilot")


@dataclass
class Container:
    settings: Settings
    helpdesk: HelpdeskClient
    agent: SupportAgent
    triage: TriagePipeline | None
    retriever: HybridRetriever
    lock: threading.Lock = field(default_factory=threading.Lock)


def build_container(
    settings: Settings,
    http: httpx.Client | None = None,
    llm: BaseChatModel | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    triage: TriagePipeline | None = None,
) -> Container:
    helpdesk = HelpdeskClient(settings.helpdesk_url, http=http)
    embedder = embedder or get_embedder(settings.embedder)
    if reranker is None:
        reranker = CrossEncoderReranker() if settings.reranker == "cross-encoder" else OverlapReranker()
    retriever = HybridRetriever.from_directory(settings.kb_dir, embedder, reranker)
    if triage is None:
        try:
            triage = load_pipeline(settings.models_dir)
        except FileNotFoundError:
            log.warning("no trained triage models in %s, running without intent and priority predictions", settings.models_dir)
    deps = AgentDeps(
        llm=llm or build_llm(settings),
        toolbox=ToolBox(helpdesk, retriever),
        policy=PolicyEngine(helpdesk, PolicyConfig.from_settings(settings)),
        triage=triage,
        retriever=retriever,
        max_steps=settings.agent_max_steps,
    )
    return Container(settings, helpdesk, SupportAgent(deps), triage, retriever)
