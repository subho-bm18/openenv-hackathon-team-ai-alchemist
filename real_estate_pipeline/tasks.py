from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EVAL_FIXTURES_DIR = Path(__file__).resolve().parent / "eval_fixtures"


def load_task(task_id: str) -> dict[str, Any]:
    fixture_path = FIXTURES_DIR / f"{task_id}.json"
    if not fixture_path.exists():
        raise ValueError(f"Unknown task_id: {task_id}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def list_task_ids() -> list[str]:
    return sorted(path.stem for path in FIXTURES_DIR.glob("*.json"))


def load_eval_task(task_id: str) -> dict[str, Any]:
    fixture_path = EVAL_FIXTURES_DIR / f"{task_id}.json"
    if not fixture_path.exists():
        raise ValueError(f"Unknown eval task_id: {task_id}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def list_eval_task_ids() -> list[str]:
    if not EVAL_FIXTURES_DIR.exists():
        return []
    return sorted(path.stem for path in EVAL_FIXTURES_DIR.glob("*.json"))
