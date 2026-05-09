"""Tests for project review checks."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.common import initial_pipeline_state, read_json, write_json
from book_pipeline.review import (
    Issue,
    detect_english_fragments,
    review_project,
    run_completeness_checks,
    run_structural_checks,
    run_terminology_checks,
)
from book_pipeline.translate import Glossary, GlossaryTerm


def create_review_project(
    tmp_path: Path,
    translated_text: str = "# Глава 1\n\n- Пункт\n\n![alt](images/a.png)\n",
    chunk_status: str = "translated",
) -> Path:
    project_dir = tmp_path / "project"
    (project_dir / "chapters").mkdir(parents=True)
    (project_dir / "translated").mkdir()
    (project_dir / "chunks" / "01_chapter").mkdir(parents=True)
    (project_dir / "review").mkdir()

    (project_dir / "chapters" / "01_chapter.md").write_text(
        "# Chapter 1\n\n- Item\n\n![alt](images/a.png)\n",
        encoding="utf-8",
    )
    (project_dir / "translated" / "01_chapter.md").write_text(
        translated_text,
        encoding="utf-8",
    )
    (project_dir / "chunks" / "01_chapter" / "0001.ru.md").write_text(
        translated_text,
        encoding="utf-8",
    )
    write_json(
        project_dir / "chunks" / "01_chapter" / "0001.meta.json",
        {
            "chunk_id": "01_chapter_0001",
            "chapter_id": "01_chapter",
            "sequence": 1,
            "status": chunk_status,
            "translated_path": "chunks/01_chapter/0001.ru.md",
        },
    )
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
                    "status": "translated",
                    "chunk_count": 1,
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())
    return project_dir


def empty_glossary() -> Glossary:
    return Glossary(terms={}, conflicts=[])


def test_review_project_writes_reports_without_modifying_translation(tmp_path: Path, monkeypatch):
    project_dir = create_review_project(tmp_path)
    monkeypatch.setattr("book_pipeline.review.load_glossaries", lambda project_dir: empty_glossary())
    translated_path = project_dir / "translated" / "01_chapter.md"
    before = translated_path.read_text(encoding="utf-8")

    report = review_project(project_dir)

    assert report.quality_score == 100.0
    assert (project_dir / "review" / "quality-report.md").exists()
    assert (project_dir / "review" / "structural-report.md").exists()
    assert translated_path.read_text(encoding="utf-8") == before


def test_structural_check_reports_missing_translation(tmp_path: Path):
    project_dir = create_review_project(tmp_path)
    (project_dir / "translated" / "01_chapter.md").unlink()
    metadata = read_json(project_dir / "metadata.json")

    issues = run_structural_checks(project_dir, metadata)

    assert any("missing" in issue.message for issue in issues)


def test_structural_check_warns_on_heading_mismatch(tmp_path: Path):
    project_dir = create_review_project(tmp_path, translated_text="Текст без заголовка.\n")
    metadata = read_json(project_dir / "metadata.json")

    issues = run_structural_checks(project_dir, metadata)

    assert any("Heading count differs" in issue.message for issue in issues)


def test_completeness_check_reports_pending_chunk(tmp_path: Path):
    project_dir = create_review_project(tmp_path, chunk_status="pending")
    metadata = read_json(project_dir / "metadata.json")

    issues = run_completeness_checks(project_dir, metadata)

    assert any("status=pending" in issue.message for issue in issues)


def test_completeness_check_reports_missing_image_reference(tmp_path: Path):
    project_dir = create_review_project(tmp_path, translated_text="# Глава 1\n\nТекст без картинки.\n")
    metadata = read_json(project_dir / "metadata.json")

    issues = run_completeness_checks(project_dir, metadata)

    assert any("Image reference missing" in issue.message for issue in issues)


def test_terminology_check_reports_missing_russian_term(tmp_path: Path):
    project_dir = create_review_project(tmp_path, translated_text="# Глава 1\n\nТекст.\n")
    metadata = read_json(project_dir / "metadata.json")
    glossary = Glossary(
        terms={
            "job": GlossaryTerm(
                english="Job",
                russian="Работа",
                notes="term",
                source="test",
            )
        },
        conflicts=[],
    )

    issues = run_terminology_checks(project_dir, metadata, glossary)

    assert any("Job -> Работа" in issue.message for issue in issues)


def test_detect_english_fragments(tmp_path: Path):
    path = tmp_path / "translated.md"
    path.write_text(
        "This is clearly untranslated English content left here.\n",
        encoding="utf-8",
    )

    issues = detect_english_fragments(path)

    assert issues
    assert all(isinstance(issue, Issue) for issue in issues)
