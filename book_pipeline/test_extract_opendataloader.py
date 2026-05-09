"""Tests for extraction post-processing helpers."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.common import read_json, write_json
from book_pipeline.extract_opendataloader import record_extracted_images


def test_record_extracted_images_updates_extracted_json(tmp_path: Path):
    output_dir = tmp_path / "source"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "figure-1.png").write_bytes(b"png")
    write_json(output_dir / "extracted.json", {"pages": []})

    count = record_extracted_images(output_dir)

    metadata = read_json(output_dir / "extracted.json")
    assert count == 1
    assert metadata["book_pipeline"]["image_count"] == 1
    assert metadata["book_pipeline"]["images"][0] == {
        "filename": "figure-1.png",
        "path": "images/figure-1.png",
    }


def test_record_extracted_images_creates_metadata_when_missing(tmp_path: Path):
    output_dir = tmp_path / "source"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "nested").mkdir()
    (images_dir / "nested" / "figure-2.jpg").write_bytes(b"jpg")

    count = record_extracted_images(output_dir)

    metadata = read_json(output_dir / "extracted.json")
    assert count == 1
    assert metadata["book_pipeline"]["images"][0]["path"] == "images/nested/figure-2.jpg"


def test_record_extracted_images_returns_zero_without_images(tmp_path: Path):
    output_dir = tmp_path / "source"
    output_dir.mkdir()

    assert record_extracted_images(output_dir) == 0
