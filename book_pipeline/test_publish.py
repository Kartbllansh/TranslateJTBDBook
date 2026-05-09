"""Tests for publishing translated projects."""

from __future__ import annotations

import json
from pathlib import Path

from book_pipeline.common import initial_pipeline_state, write_json
from book_pipeline.publish import (
    embed_markdown_images,
    generate_standalone_html,
    json_for_html,
    load_published_chapters,
    publish_project,
)


def create_publish_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    (project_dir / "translated").mkdir(parents=True)
    (project_dir / "source" / "images").mkdir(parents=True)
    (project_dir / "review").mkdir()

    (project_dir / "translated" / "01_chapter.md").write_text(
        "# Глава 1\n\nТекст главы.\n\n![cover](images/pic.png)\n",
        encoding="utf-8",
    )
    (project_dir / "source" / "images" / "pic.png").write_bytes(b"png-data")
    write_json(
        project_dir / "metadata.json",
        {
            "schema_version": 1,
            "book_id": "sample-book",
            "title": "Sample Book",
            "author": "Author",
            "source_language": "en",
            "target_language": "ru",
            "translator": {"contact": "@translator"},
            "chapters": [
                {
                    "id": "01_chapter",
                    "title": "Chapter 1",
                    "translated_path": "translated/01_chapter.md",
                    "status": "translated",
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())
    return project_dir


def test_load_published_chapters_builds_toc_data(tmp_path: Path):
    project_dir = create_publish_project(tmp_path)
    metadata = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))

    chapters = load_published_chapters(project_dir, metadata)

    assert chapters[0]["file"] == "01_chapter.md"
    assert chapters[0]["label"] == "01"
    assert chapters[0]["kind"] == "Глава"
    assert chapters[0]["title"] == "Глава 1"
    assert chapters[0]["words"] > 0


def test_json_for_html_escapes_script_breakout():
    data = [{"raw": "</script><script>alert(1)</script>"}]

    encoded = json_for_html(data)

    assert "</script>" not in encoded
    assert "\\u003c/script>" in encoded


def test_embed_markdown_images_uses_base64_data_uri(tmp_path: Path):
    project_dir = create_publish_project(tmp_path)
    text = "![alt](images/pic.png)"

    embedded = embed_markdown_images(text, project_dir, project_dir / "translated")

    assert "data:image/png;base64," in embedded
    assert "cG5nLWRhdGE=" in embedded


def test_generate_standalone_html_inlines_assets_and_content(tmp_path: Path):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"cover")
    template = """<!doctype html>
<html><head><title>Old</title><link rel="stylesheet" href="./styles.css"></head>
<body><h1>Old</h1><img src="./cover.png"><script src="./app.js"></script></body></html>"""
    chapters = [{"file": "01.md", "raw": "# Текст", "title": "Текст", "words": 1}]
    metadata = {"title": "Книга", "book_id": "book", "translator": {"contact": "@me"}}

    html = generate_standalone_html(
        template_html=template,
        css="body { color: red; }",
        js="console.log('ok');",
        chapters=chapters,
        metadata=metadata,
        cover_image=cover,
    )

    assert '<style>\nbody { color: red; }\n</style>' in html
    assert "window.EMBEDDED_CHAPTERS" in html
    assert "console.log('ok');" in html
    assert "data:image/png;base64,Y292ZXI=" in html
    assert '<script src="./app.js"></script>' not in html


def test_publish_project_writes_reader_and_standalone(tmp_path: Path):
    project_dir = create_publish_project(tmp_path)

    result = publish_project(project_dir, standalone=True)

    assert (result.reader_dir / "index.html").exists()
    assert result.standalone_path is not None
    assert result.standalone_path.exists()
    reader_html = (result.reader_dir / "index.html").read_text(encoding="utf-8")
    assert "window.EMBEDDED_CHAPTERS" in reader_html
    assert "Sample Book" in reader_html
    assert (result.reader_dir / "images" / "pic.png").exists()
