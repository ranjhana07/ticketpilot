# ticketpilot

Customer support automation for a fictional SaaS product (Loomwork, a project management tool). Incoming tickets are triaged, a tool-using agent works on them against a mock helpdesk, and the result is a proposed set of actions plus a drafted reply that a human reviews in an inbox UI before anything is sent.

What is in the repository:

- Triage: intent and priority classifiers (TF-IDF + logistic regression and a fine-tuned MiniLM), sentiment and urgency scoring, language detection, hand-written PII redaction, duplicate detection with embeddings.
- Knowledge base: 32 markdown help articles with hybrid retrieval (BM25 + embeddings fused with reciprocal rank fusion) and an optional cross-encoder reranker.
- Agent: a LangGraph graph that calls helpdesk tools, with policy guardrails (identity verification, refund limits, refund window) and a human approval step implemented with a LangGraph interrupt. The model goes through LangChain and is configurable, the default is Anthropic `claude-sonnet-5-5`.
- Mock helpdesk: a FastAPI service backed by SQLite (customers, orders, subscriptions, refunds, tickets, notes, escalations, audit log).
- Inbox UI: static HTML, CSS and vanilla JS served by the API. It shows the queue with predicted intent and priority, the actions the agent took or wants approval for, and an editable draft reply.
- Evaluation scripts for every component, with raw outputs committed under `results/`.

## Architecture

```
                         +-----------------------------+
   ticket (email/chat)   |        inbox UI (static)    |
          |              |  queue | proposal | draft   |
          v              +--------------+--------------+
 +------------------+                   |  /api/*
 |   ticketpilot    |<------------------+
 |   FastAPI app    |
 +--------+---------+
          |
          v
 +------------------------------ LangGraph ------------------------------+
 |                                                                       |
 |  triage --> retrieve --> agent --+--> draft --> END                   |
 |  (PII,      (BM25 +      (LLM    |      (reply + KB citations)        |
 |  intent,    dense +      with    |                                    |
 |  priority,  RRF +        tools)  +--> guard --+--> tools --> agent     |
 |  language,  rerank)                |          |                       |
 |  duplicates)                       |          +--> approval           |
 |                                    |               (interrupt, human  |
 |                                    |                approve/reject)   |
 +------------------------------------+------------------------------------+
          |                                  |
          v                                  v
 +------------------+              +----------------------+
 | triage models    |              |  helpdesk service    |
 | + knowledge base |              |  FastAPI + SQLite    |
 +------------------+              +----------------------+
```

The guard node evaluates every tool call the model proposes before it runs. A call is allowed, held for human approval, or denied with a reason that is returned to the model as the tool result. Account changes require that the sender of the ticket was verified as the owner of the account, refunds have an automatic limit, a ceiling and a 30 day window, and cancellations always need approval. The limits come from environment variables.

The model never sees raw PII from the ticket body. Emails, phone numbers, card numbers, IBANs, IP addresses, API tokens, names and street addresses are replaced with numbered placeholders before the prompt is built. The sender address comes from the mail system and is passed as trusted metadata.

## Setup

Python 3.11 or newer.

```
python -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev]"
cp .env.example .env
```

Download the public dataset, train the triage models and start the two services:

```
ticketpilot data download
ticketpilot triage train --task synthetic_intent --kind baseline
ticketpilot triage train --task synthetic_priority --kind baseline
ticketpilot helpdesk --reset &
ticketpilot serve --llm scripted
```

The inbox is then at http://127.0.0.1:8000. `--llm scripted` runs a deterministic rule-based stand-in for the model, which is enough to click through the UI without an API key. For the real model export `ANTHROPIC_API_KEY` and drop the flag.

Without trained models the API still works, tickets just have no predicted intent or priority.

Docker is supported through `docker-compose.yml` (a helpdesk container and an inbox container). It has not been run as part of building this repository.

## Configuration

All settings are environment variables, see `.env.example`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | empty | Needed when `TICKETPILOT_LLM=anthropic` |
| `TICKETPILOT_LLM` | `anthropic` | `anthropic` or `scripted` |
| `TICKETPILOT_MODEL` | `claude-sonnet-5-5` | Model name passed to LangChain |
| `TICKETPILOT_EMBEDDER` | `minilm` | `minilm` (all-MiniLM-L6-v2) or `hashing` (offline) |
| `TICKETPILOT_RERANKER` | `cross-encoder` | `cross-encoder` (ms-marco-MiniLM-L-6-v2) or `overlap` |
| `TICKETPILOT_DATA_DIR` | `./data` | Downloaded datasets and the helpdesk database |
| `TICKETPILOT_MODELS_DIR` | `./models` | Trained triage models |
| `TICKETPILOT_KB_DIR` | `./knowledge_base` | Markdown articles |
| `HELPDESK_URL` | `http://127.0.0.1:8001` | Where the agent reaches the helpdesk |
| `HELPDESK_DB` | `./data/helpdesk.db` | SQLite file of the helpdesk |
| `AUTO_REFUND_LIMIT_USD` | `50` | Refunds up to this total per ticket run without approval |
| `MAX_REFUND_USD` | `500` | Refunds above this are denied and escalated |
| `REFUND_WINDOW_DAYS` | `30` | Orders older than this cannot be refunded by support |
| `AGENT_MAX_STEPS` | `8` | Cap on agent turns per ticket |
