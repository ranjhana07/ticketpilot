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
| `DUPLICATE_THRESHOLD` | `0.8` | Cosine similarity above which two tickets are flagged as duplicates |
| `AGENT_MAX_STEPS` | `8` | Cap on agent turns per ticket |

## Usage

```
ticketpilot data download                 fetch the Bitext customer support dataset
ticketpilot data generate --count 2000    write synthetic Loomwork tickets as jsonl
ticketpilot triage train --task T --kind K
ticketpilot triage predict "text of a ticket"
ticketpilot kb search "how do I cancel"
ticketpilot helpdesk --reset              mock helpdesk on :8001, seeded with demo data
ticketpilot serve [--llm scripted]        inbox API and UI on :8000
ticketpilot eval triage|retrieval|duplicates|agent|all
```

Tasks for `triage train` are `bitext_intent`, `synthetic_intent` and `synthetic_priority`. Kinds are `baseline` (TF-IDF with logistic regression) and `transformer` (fine-tuned MiniLM). The pipeline prefers a transformer model when one is present and falls back to the baseline.

A typical session in the inbox: open a ticket, press **Run agent**, read the action timeline, approve or reject anything held for approval, edit the draft reply and press **Approve and send**. Sending only marks the ticket as replied and leaves a note, no email leaves the machine. Keyboard shortcuts: `j` and `k` move through the queue, `r` runs the agent, `/` focuses the search box.

Pending approvals live in the memory of the API process (LangGraph `InMemorySaver`). If the API restarts while a ticket is waiting, run the agent on that ticket again.

## API reference

Inbox API (port 8000, also serves the UI at `/`):

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Liveness |
| `GET /api/config` | Provider, model, refund limits, whether triage models are loaded |
| `GET /api/tickets?status=` | Queue, triaged on first read, sorted by predicted priority |
| `GET /api/tickets/{id}` | Ticket with triage, proposal, draft and internal notes |
| `POST /api/tickets/{id}/run` | Run the agent, store actions and draft, may pause for approval |
| `POST /api/tickets/{id}/approve` | Body `{"decisions": {"<call_id>": "approve"\|"reject"}, "reviewer": "name"}`, resumes the graph |
| `PUT /api/tickets/{id}/draft` | Body `{"reply": "..."}`, saves an edited draft |
| `POST /api/tickets/{id}/send` | Body `{"reviewer": "name"}`, marks the ticket as replied |
| `GET /api/audit` | Latest helpdesk audit entries |

Mock helpdesk (port 8001):

| Method and path | Purpose |
| --- | --- |
| `GET /customers/lookup?email=` | Customer with subscription |
| `GET /customers/{id}` and `/customers/{id}/orders` | Customer and orders |
| `POST /customers/{id}/verify` | Check that `requester_email` owns the account |
| `POST /customers/{id}/reset-password` | Record a reset link, unlocks a locked account |
| `PUT /customers/{id}/subscription` | Change plan or billing cycle, enterprise is refused |
| `POST /customers/{id}/subscription/cancel` | Cancel at period end |
| `GET /orders/{id}` | Order with refunded balance |
| `POST /orders/{id}/refund` | Refund up to the remaining balance |
| `GET/POST /tickets`, `GET/PATCH /tickets/{id}` | Tickets |
| `GET/POST /tickets/{id}/notes` | Internal notes |
| `POST /tickets/{id}/escalate` | Hand over to billing, security, support_lead, engineering or sales |
| `GET /audit` | Audit log of every state change |

Agent tools (LangChain `StructuredTool`): `lookup_customer`, `verify_identity`, `get_order`, `list_customer_orders`, `refund_order`, `reset_password`, `update_subscription`, `cancel_subscription`, `escalate_to_human`, `add_internal_note`, `search_knowledge_base`. The ticket id and the requester address are bound by the runtime and are not part of the schema the model sees.

## Project layout

```
src/ticketpilot/
  config.py              settings from environment variables
  cli.py                 Typer entry point
  embeddings.py          hashing and sentence-transformer embedders, cache
  data/                  Bitext loader, synthetic ticket generator, splits
  triage/                pii, language, sentiment, classifiers, duplicates, pipeline
  kb/                    loader, chunking, bm25, dense index, rrf, reranker, retriever
  helpdesk/              mock helpdesk: schema, service, FastAPI app, seed data
  agent/                 tools, policy engine, LangGraph graph, runner, LLM factory, fakes
  api/                   inbox API, container wiring, static UI (html, css, js)
  evaluation/            triage, retrieval, duplicate, preprocessing and agent evaluations
knowledge_base/          32 help center articles (markdown)
eval/                    labelled retrieval queries
results/                 raw outputs of the evaluation scripts
tests/                   pytest suite
```

## Testing

```
pytest
```

The suite needs no network, API keys or running services. It uses FastAPI's test client for the helpdesk and the inbox API, a hashing embedder instead of MiniLM, and fake chat models (a queued model that replays tool calls, and the scripted support model) instead of Anthropic. It covers the PII rules, language and sentiment scoring, BM25 and fusion, duplicate detection, the helpdesk endpoints, tool schemas, every policy rule, graph routing including the approval interrupt and resume, the inbox API and the evaluation helpers.

`python -m compileall src tests` and `node --check src/ticketpilot/api/static/app.js` are also clean.
