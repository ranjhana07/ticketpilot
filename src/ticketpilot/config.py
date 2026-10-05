from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    root: Path = field(default_factory=_project_root)
    data_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_DATA_DIR", _project_root() / "data"))
    models_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_MODELS_DIR", _project_root() / "models"))
    kb_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_KB_DIR", _project_root() / "knowledge_base"))
    llm_provider: str = field(default_factory=lambda: os.environ.get("TICKETPILOT_LLM", "anthropic"))
    model: str = field(default_factory=lambda: os.environ.get("TICKETPILOT_MODEL", "claude-sonnet-5-5"))
    embedder: str = field(default_factory=lambda: os.environ.get("TICKETPILOT_EMBEDDER", "minilm"))
    reranker: str = field(default_factory=lambda: os.environ.get("TICKETPILOT_RERANKER", "cross-encoder"))
    helpdesk_url: str = field(default_factory=lambda: os.environ.get("HELPDESK_URL", "http://127.0.0.1:8001"))
    helpdesk_db: Path = field(default_factory=lambda: _env_path("HELPDESK_DB", _project_root() / "data" / "helpdesk.db"))
    auto_refund_limit: float = field(default_factory=lambda: _env_float("AUTO_REFUND_LIMIT_USD", 50.0))
    max_refund: float = field(default_factory=lambda: _env_float("MAX_REFUND_USD", 500.0))
    refund_window_days: int = field(default_factory=lambda: _env_int("REFUND_WINDOW_DAYS", 30))
    agent_max_steps: int = field(default_factory=lambda: _env_int("AGENT_MAX_STEPS", 8))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()


def get_settings() -> Settings:
    return Settings.from_env()
