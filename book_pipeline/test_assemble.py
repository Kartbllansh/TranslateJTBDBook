"""Tests for assembling translated chunks."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.assemble import assemble_chapter, assemble_project
from book_pipeline.common import initial_pipeline_state, read_json, write_json


def create_assembly_project(
    tmp_path: Path,
    statuses: list[str],
    translations: list[str],
    sequences: list[int] | None = None,
) -> Path:
    project_dir = tmp_path / "project"
    chunk_dir = project_dir / "chunks" / "01_chapter"
    chunk_dir.mkdir(parents=True)
    (project_dir / "review").mkdir()

    sequences = sequences or list(range(1, len(statuses) + 1))
    write_json(
        project_dir / "metadata.json",
        {
            "schema_version": 1,
            "book_id": "sample",
            "title": "Sample",
            "chapters": [
                {
                    "id": "01_chapter",
                    "title": "Chapter 1",
                    "source_path": "chapters/01_chapter.md",
                    "translated_path": "translated/01_chapter.md",
                    "status": "chunked",
                    "chunk_count": len(statuses),
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())

    for sequence, status, translation in zip(sequences, statuses, translations, strict=True):
        sequence_name = f"{sequence:04d}"
        (chunk_dir / f"{sequence_name}.ru.md").write_text(translation, encoding="utf-8")
        write_json(
            chunk_dir / f"{sequence_name}.meta.json",
            {
                "chunk_id": f"01_chapter_{sequence_name}",
                "chapter_id": "01_chapter",
                "sequence": sequence,
                "status": status,
                "translated_path": f"chunks/01_chapter/{sequence_name}.ru.md",
            },
        )

    return project_dir


def test_assemble_chapter_concatenates_in_sequence(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated", "translated"],
        translations=["Первый.", "Второй."],
    )

    result = assemble_chapter("01_chapter", project_dir)

    assert result.success is True
    assert result.output_path.read_text(encoding="utf-8") == "Первый.\n\nВторой.\n"


def test_assemble_chapter_detects_sequence_gap(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated", "translated"],
        translations=["Первый.", "Третий."],
        sequences=[1, 3],
    )

    result = assemble_chapter("01_chapter", project_dir)

    assert result.success is False
    assert "missing sequence 0002" in result.missing_chunks


def test_assemble_chapter_detects_pending_chunk(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated", "pending"],
        translations=["Первый.", ""],
    )

    result = assemble_chapter("01_chapter", project_dir)

    assert result.success is False
    assert any("status is pending" in item for item in result.missing_chunks)
    assert any("empty translation" in item for item in result.missing_chunks)


def test_assemble_project_updates_metadata_and_report(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated"],
        translations=["Глава готова."],
    )

    results = assemble_project(project_dir)

    assert results[0].success is True
    metadata = read_json(project_dir / "metadata.json")
    assert metadata["chapters"][0]["status"] == "translated"
    report = project_dir / "review" / "missing-sections.md"
    assert "All chapters assembled successfully" in report.read_text(encoding="utf-8")


def test_assemble_refuses_existing_output_without_force(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated"],
        translations=["Глава готова."],
    )
    translated_dir = project_dir / "translated"
    translated_dir.mkdir()
    (translated_dir / "01_chapter.md").write_text("manual", encoding="utf-8")

    result = assemble_chapter("01_chapter", project_dir, force=False)

    assert result.success is False
    assert "already exists" in result.warnings[0]
    assert (translated_dir / "01_chapter.md").read_text(encoding="utf-8") == "manual"


def test_assemble_overwrites_existing_output_with_force(tmp_path: Path):
    project_dir = create_assembly_project(
        tmp_path,
        statuses=["translated"],
        translations=["Глава готова."],
    )
    translated_dir = project_dir / "translated"
    translated_dir.mkdir()
    (translated_dir / "01_chapter.md").write_text("manual", encoding="utf-8")

    result = assemble_chapter("01_chapter", project_dir, force=True)

    assert result.success is True
    assert (translated_dir / "01_chapter.md").read_text(encoding="utf-8") == "Глава готова.\n"
