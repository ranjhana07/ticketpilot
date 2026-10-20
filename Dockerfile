FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu torch

COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge_base ./knowledge_base
COPY eval ./eval

RUN pip install .

ENV TICKETPILOT_DATA_DIR=/app/data \
    TICKETPILOT_MODELS_DIR=/app/models \
    TICKETPILOT_KB_DIR=/app/knowledge_base \
    HELPDESK_DB=/app/data/helpdesk.db

EXPOSE 8000 8001

CMD ["ticketpilot", "serve", "--host", "0.0.0.0"]
