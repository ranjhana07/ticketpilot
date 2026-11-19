# Results

Raw outputs of the evaluation scripts. The README at the repository root explains how to read them and lists the hardware.

| File | Produced by | Contents |
| --- | --- | --- |
| `triage.json`, `triage.csv` | `ticketpilot eval triage` | Accuracy and macro F1 of the TF-IDF baseline and the fine-tuned MiniLM on three tasks, with per-class precision, recall and F1 in the JSON |
| `retrieval.json`, `retrieval.csv` | `ticketpilot eval retrieval` | hit@1, hit@3, hit@5 and MRR for BM25, dense, hybrid and hybrid with reranking |
| `duplicates.json`, `duplicates.csv` | `ticketpilot eval duplicates` | Precision and recall of duplicate detection with and without the entity guard |
| `preprocessing.json`, `preprocessing.csv` | `ticketpilot eval preprocessing` | PII redaction recall and language detection accuracy |
| `agent_harness.json`, `agent_harness.csv` | `ticketpilot eval agent` | Task success, tool accuracy and policy violations, with per-scenario outcomes in the JSON |

The agent files come from a scripted stand-in for the model and are a check of the harness, not a model result.

The `ms_per_query`, `train_seconds` and `inference_ms_per_ticket` columns were measured on a machine that was busy with other work and should not be used as benchmarks. The triage run used `TICKETPILOT_TORCH_THREADS=4`.
