"""Shared helpers for the book translation pipeline."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PIPELINE_STAGES = [
    "init",
    "extract",
    "normalize",
    "split",
    "chunk",
    "translate",
    "assemble",
    "review",
    "publish",
]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[^a-z0-9а-яё]+", "-", slug)
    slug = slug.strip("-")
    return slug or "book"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_empty_or_force(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists. Re-run with --force to reuse it."
        )


def initial_pipeline_state() -> dict[str, Any]:
    stages = {stage: "pending" for stage in PIPELINE_STAGES}
    stages["init"] = "done"
    return {
        "current_stage": "extract",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "stages": stages,
    }


def update_pipeline_stage(project_dir: Path, stage: str, status: str) -> None:
    state_path = project_dir / "pipeline-state.json"
    if not state_path.exists():
        return

    state = read_json(state_path)
    stages = state.setdefault("stages", {})
    stages[stage] = status
    state["updated_at"] = now_iso()

    if status == "done":
        next_stage = next_pending_stage(stages)
        if next_stage:
            state["current_stage"] = next_stage

    write_json(state_path, state)


def next_pending_stage(stages: dict[str, str]) -> str | None:
    for stage in PIPELINE_STAGES:
        if stages.get(stage) == "pending":
            return stage
    return None
