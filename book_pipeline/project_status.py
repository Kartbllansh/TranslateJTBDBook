"""Print a concise project status summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from book_pipeline.common import PIPELINE_STAGES, read_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show book project status.")
    parser.add_argument("project_dir", help="Project directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)
    metadata_path = project_dir / "metadata.json"
    state_path = project_dir / "pipeline-state.json"

    if not metadata_path.exists():
        print(f"Missing metadata.json: {metadata_path}", file=sys.stderr)
        return 2
    if not state_path.exists():
        print(f"Missing pipeline-state.json: {state_path}", file=sys.stderr)
        return 2

    metadata = read_json(metadata_path)
    state = read_json(state_path)
    chapters = metadata.get("chapters", [])
    stages = state.get("stages", {})

    print(f"Project: {metadata.get('book_id', project_dir.name)}")
    print(f"Title: {metadata.get('title', '')}")
    print(f"Author: {metadata.get('author', '')}")
    print(f"Languages: {metadata.get('source_language', '?')} -> {metadata.get('target_language', '?')}")
    print(f"Current stage: {state.get('current_stage', 'unknown')}")
    print(f"Chapters: {len(chapters)}")
    print("")
    print("Stages:")
    for stage in PIPELINE_STAGES:
        print(f"  {stage}: {stages.get(stage, 'unknown')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
