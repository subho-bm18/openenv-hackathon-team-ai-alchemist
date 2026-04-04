from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TOKEN_RE = re.compile(r"[a-z0-9_]+")


class MultinomialNB:
    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.class_token_totals: Counter[str] = Counter()
        self.vocabulary: set[str] = set()

    def fit(self, texts: Iterable[str], labels: Iterable[str]) -> None:
        for text, label in zip(texts, labels):
            self.class_counts[label] += 1
            for token in tokenize(text):
                self.feature_counts[label][token] += 1
                self.class_token_totals[label] += 1
                self.vocabulary.add(token)

    def predict(self, text: str) -> str:
        scores = self.predict_log_proba(text)
        return max(scores.items(), key=lambda item: item[1])[0]

    def predict_log_proba(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        total_docs = sum(self.class_counts.values())
        vocab_size = max(len(self.vocabulary), 1)
        scores: dict[str, float] = {}

        for label, count in self.class_counts.items():
            log_prob = math.log(count / total_docs)
            token_total = self.class_token_totals[label]
            for token in tokens:
                numerator = self.feature_counts[label][token] + 1
                denominator = token_total + vocab_size
                log_prob += math.log(numerator / denominator)
            scores[label] = log_prob

        return scores

    def to_dict(self) -> dict:
        return {
            "class_counts": dict(self.class_counts),
            "feature_counts": {label: dict(counter) for label, counter in self.feature_counts.items()},
            "class_token_totals": dict(self.class_token_totals),
            "vocabulary": sorted(self.vocabulary),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train lightweight baseline classifiers on exported step-level records.")
    parser.add_argument(
        "--input",
        default="artifacts/training_steps.jsonl",
        help="Path to step-level JSONL training records.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/models",
        help="Directory to store trained model artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = ROOT / args.input
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(input_path)
    step_records = [record for record in records if record.get("record_type") == "step"]
    train_records, test_records = split_records(step_records)

    category_model = MultinomialNB()
    action_model = MultinomialNB()

    category_model.fit((feature_text(record) for record in train_records), (record["target"]["category"] for record in train_records))
    action_model.fit((feature_text(record) for record in train_records), (record["target"]["action_type"] for record in train_records))

    category_accuracy = accuracy(category_model, test_records, "category")
    action_accuracy = accuracy(action_model, test_records, "action_type")

    (output_dir / "category_model.json").write_text(json.dumps(category_model.to_dict(), indent=2), encoding="utf-8")
    (output_dir / "action_model.json").write_text(json.dumps(action_model.to_dict(), indent=2), encoding="utf-8")

    metrics = {
        "train_records": len(train_records),
        "test_records": len(test_records),
        "category_accuracy": round(category_accuracy, 4),
        "next_action_accuracy": round(action_accuracy, 4),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2), flush=True)


def load_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def split_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    train_records: list[dict] = []
    test_records: list[dict] = []
    for index, record in enumerate(records):
        if index % 5 == 0:
            test_records.append(record)
        else:
            train_records.append(record)
    return train_records, test_records


def feature_text(record: dict) -> str:
    observation = record["input"]["observation"]
    opportunity = observation["active_opportunity"]
    parts = [
        record["input"].get("inquiry", ""),
        f"segment_{opportunity.get('segment')}",
        f"location_{opportunity.get('location')}",
        f"property_{opportunity.get('property_type')}",
        f"business_{opportunity.get('business_type')}",
        f"stage_{opportunity.get('stage')}",
        f"step_{record.get('step')}",
        f"priority_{opportunity.get('priority')}",
    ]

    for field in opportunity.get("missing_fields", []):
        parts.append(f"missing_{field}")
    for rule in observation.get("business_rules", []):
        parts.append(rule)

    return " ".join(part for part in parts if part and part != "None")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def accuracy(model: MultinomialNB, records: list[dict], target_key: str) -> float:
    if not records:
        return 0.0
    correct = 0
    for record in records:
        prediction = model.predict(feature_text(record))
        if prediction == record["target"][target_key]:
            correct += 1
    return correct / len(records)


if __name__ == "__main__":
    main()
