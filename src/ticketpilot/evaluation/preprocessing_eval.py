from __future__ import annotations

import csv
import json
from pathlib import Path

from ticketpilot.data.synthetic import generate_tickets
from ticketpilot.triage.language import detect_language
from ticketpilot.triage.pii import redact


def evaluate_redaction(count: int = 3000, seed: int = 404) -> dict[str, object]:
    tickets = generate_tickets(count, seed=seed)
    total = leaked = 0
    clean = clean_changed = 0
    for ticket in tickets:
        result = redact(ticket.body, known_names=[ticket.from_name])
        for value in ticket.meta["pii"]:
            total += 1
            if value in result.text:
                leaked += 1
    for ticket in tickets:
        if not ticket.meta["pii"]:
            clean += 1
            if redact(ticket.body).text != ticket.body:
                clean_changed += 1
    return {
        "tickets": count,
        "injected_values": total,
        "values_still_present": leaked,
        "recall": round(1 - leaked / total, 4),
        "tickets_without_pii": clean,
        "tickets_without_pii_modified": clean_changed,
    }


def evaluate_language(count: int = 3000, seed: int = 505) -> dict[str, object]:
    tickets = generate_tickets(count, seed=seed, foreign_share=0.5)
    per_language: dict[str, list[int]] = {}
    for ticket in tickets:
        predicted = detect_language(ticket.text).language
        per_language.setdefault(ticket.language, []).append(int(predicted == ticket.language))
    overall = [hit for hits in per_language.values() for hit in hits]
    return {
        "tickets": count,
        "accuracy": round(sum(overall) / len(overall), 4),
        "per_language": {
            language: {"n": len(hits), "accuracy": round(sum(hits) / len(hits), 4)}
            for language, hits in sorted(per_language.items())
        },
    }


def run(output_dir: Path) -> dict[str, object]:
    result = {"pii_redaction": evaluate_redaction(), "language_detection": evaluate_language()}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "preprocessing.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (output_dir / "preprocessing.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["component", "metric", "value"])
        writer.writerow(["pii_redaction", "recall", result["pii_redaction"]["recall"]])
        writer.writerow(["pii_redaction", "values_still_present", result["pii_redaction"]["values_still_present"]])
        writer.writerow(["language_detection", "accuracy", result["language_detection"]["accuracy"]])
    return result
