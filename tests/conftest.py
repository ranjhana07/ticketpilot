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
