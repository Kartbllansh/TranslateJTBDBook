"""List available book translation projects."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.common import read_json


@dataclass(frozen=True)
class ProjectSummary:
    project_id: str
    title: str
    current_stage: str
    path: Path


def list_projects(projects_dir: Path) -> list[ProjectSummary]:
    if not projects_dir.exists():
        return []

    summaries: list[ProjectSummary] = []
    for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir()):
        metadata_path = project_dir / "metadata.json"
        state_path = project_dir / "pipeline-state.json"
        if not metadata_path.exists() or not state_path.exists():
            continue

        metadata = read_json(metadata_path)
        state = read_json(state_path)
        summaries.append(
            ProjectSummary(
                project_id=metadata.get("book_id", project_dir.name),
                title=metadata.get("title", ""),
                current_stage=state.get("current_stage", "unknown"),
                path=project_dir,
            )
        )

    return summaries


def format_projects_table(projects: list[ProjectSummary]) -> str:
    if not projects:
        return "No projects found."

    rows = [("Project ID", "Title", "Current Stage", "Path")]
    rows.extend(
        (
            project.project_id,
            project.title,
            project.current_stage,
            str(project.path),
        )
        for project in projects
    )
    widths = [
        max(len(row[column]) for row in rows)
        for column in range(len(rows[0]))
    ]

    lines = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(rows[0])),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows[1:]:
        lines.append("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List book translation projects.")
    parser.add_argument(
        "--projects-dir",
        default="projects",
        help="Parent directory containing project folders. Default: projects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projects_dir = Path(args.projects_dir)

    try:
        print(format_projects_table(list_projects(projects_dir)))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
