from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


@dataclass(frozen=True)
class Settings:
    root: Path = field(default_factory=_project_root)
    data_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_DATA_DIR", _project_root() / "data"))
    models_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_MODELS_DIR", _project_root() / "models"))
    kb_dir: Path = field(default_factory=lambda: _env_path("TICKETPILOT_KB_DIR", _project_root() / "knowledge_base"))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()


def get_settings() -> Settings:
    return Settings.from_env()
