"""Tests for project listing."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.common import initial_pipeline_state, write_json
from book_pipeline.list_projects import format_projects_table, list_projects


def test_list_projects_reads_metadata_and_state(tmp_path: Path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "sample"
    project_dir.mkdir(parents=True)
    write_json(
        project_dir / "metadata.json",
        {"book_id": "sample", "title": "Sample Book"},
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())

    projects = list_projects(projects_dir)

    assert len(projects) == 1
    assert projects[0].project_id == "sample"
    assert projects[0].title == "Sample Book"
    assert projects[0].current_stage == "extract"


def test_list_projects_skips_incomplete_directories(tmp_path: Path):
    projects_dir = tmp_path / "projects"
    (projects_dir / "scratch").mkdir(parents=True)

    assert list_projects(projects_dir) == []


def test_format_projects_table():
    projects_dir = Path("projects")
    project_dir = projects_dir / "sample"
    table = format_projects_table(
        [
            type(
                "Project",
                (),
                {
                    "project_id": "sample",
                    "title": "Sample Book",
                    "current_stage": "translate",
                    "path": project_dir,
                },
            )()
        ]
    )

    assert "Project ID" in table
    assert "sample" in table
    assert "translate" in table


def test_format_empty_projects_table():
    assert format_projects_table([]) == "No projects found."
