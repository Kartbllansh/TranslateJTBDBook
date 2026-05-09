"""Assemble translated chunks into chapter markdown files."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_pipeline.common import now_iso, read_json, update_pipeline_stage, write_json


@dataclass(frozen=True)
class AssemblyResult:
    success: bool
    output_path: Path
    missing_chunks: list[str]
    warnings: list[str]


def assemble_project(project_dir: Path, force: bool = False) -> list[AssemblyResult]:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")

    metadata = read_json(metadata_path)
    chapters = metadata.get("chapters", [])
    if not chapters:
        raise ValueError("No chapters found in metadata.json. Run split and chunk first.")

    results = [
        assemble_chapter(chapter.get("id", ""), project_dir, force=force)
        for chapter in chapters
    ]

    update_metadata_statuses(project_dir, metadata, results)
    write_missing_sections_report(project_dir, results)

    if all(result.success for result in results):
        update_pipeline_stage(project_dir, "assemble", "done")
    else:
        update_pipeline_stage(project_dir, "assemble", "error")

    return results


def assemble_chapter(
    chapter_id: str,
    project_dir: Path,
    force: bool = False,
) -> AssemblyResult:
    if not chapter_id:
        return AssemblyResult(
            success=False,
            output_path=project_dir / "translated" / "unknown.md",
            missing_chunks=["missing chapter id in metadata"],
            warnings=[],
        )

    translated_dir = project_dir / "translated"
    translated_dir.mkdir(parents=True, exist_ok=True)
    output_path = translated_dir / f"{chapter_id}.md"

    if output_path.exists() and not force:
        return AssemblyResult(
            success=False,
            output_path=output_path,
            missing_chunks=[],
            warnings=[
                f"{output_path} already exists. Re-run with --force to overwrite assembled chapter."
            ],
        )

    chunk_records = load_chunk_records(project_dir, chapter_id)
    missing_chunks = find_missing_sequences(chunk_records)
    warnings: list[str] = []

    if not chunk_records:
        missing_chunks.append(f"{chapter_id}: no chunk metadata found")

    translated_parts: list[str] = []
    for record in chunk_records:
        meta = record["metadata"]
        sequence = int(meta.get("sequence", 0))
        chunk_label = f"{chapter_id}_{sequence:04d}"
        status = meta.get("status", "pending")
        translated_path = project_dir / meta.get(
            "translated_path",
            f"chunks/{chapter_id}/{sequence:04d}.ru.md",
        )

        if status in {"pending", "chunked", "error"}:
            missing_chunks.append(f"{chunk_label}: status is {status}")

        if not translated_path.exists():
            missing_chunks.append(f"{chunk_label}: missing {translated_path}")
            continue

        content = translated_path.read_text(encoding="utf-8").strip()
        if not content:
            missing_chunks.append(f"{chunk_label}: empty translation")
            continue

        translated_parts.append(content)

    if translated_parts:
        output_path.write_text("\n\n".join(translated_parts) + "\n", encoding="utf-8")
    else:
        warnings.append(f"{chapter_id}: no translated content was assembled")

    return AssemblyResult(
        success=not missing_chunks and bool(translated_parts),
        output_path=output_path,
        missing_chunks=deduplicate(missing_chunks),
        warnings=warnings,
    )


def load_chunk_records(project_dir: Path, chapter_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for meta_path in sorted((project_dir / "chunks" / chapter_id).glob("*.meta.json")):
        metadata = read_json(meta_path)
        records.append({"meta_path": meta_path, "metadata": metadata})
    return sorted(records, key=lambda record: int(record["metadata"].get("sequence", 0)))


def find_missing_sequences(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return []

    sequences = sorted(int(record["metadata"].get("sequence", 0)) for record in records)
    missing: list[str] = []
    for expected in range(1, sequences[-1] + 1):
        if expected not in sequences:
            missing.append(f"missing sequence {expected:04d}")
    return missing


def update_metadata_statuses(
    project_dir: Path,
    metadata: dict[str, Any],
    results: list[AssemblyResult],
) -> None:
    results_by_id = {result.output_path.stem: result for result in results}
    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id")
        result = results_by_id.get(chapter_id)
        if not result:
            continue
        if result.success:
            chapter["status"] = "translated"
        elif chapter.get("status") != "error":
            chapter["status"] = "chunked"

    metadata["updated_at"] = now_iso()
    write_json(project_dir / "metadata.json", metadata)


def write_missing_sections_report(
    project_dir: Path,
    results: list[AssemblyResult],
) -> None:
    report_path = project_dir / "review" / "missing-sections.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Missing Sections Report",
        "",
        f"Generated: {now_iso()}",
        "",
    ]

    incomplete = [result for result in results if not result.success]
    if not incomplete:
        lines.append("All chapters assembled successfully.")
    else:
        for result in incomplete:
            lines.extend(
                [
                    f"## {result.output_path.stem}",
                    "",
                    f"Output: `{result.output_path}`",
                    "",
                ]
            )
            if result.missing_chunks:
                lines.append("Missing or incomplete chunks:")
                lines.extend(f"- {item}" for item in result.missing_chunks)
                lines.append("")
            if result.warnings:
                lines.append("Warnings:")
                lines.extend(f"- {item}" for item in result.warnings)
                lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble translated chunks into complete chapter files."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing chunks/ and metadata.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in translated/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        results = assemble_project(project_dir, force=args.force)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    complete = sum(1 for result in results if result.success)
    incomplete = len(results) - complete
    print(f"Assembly complete: {complete} complete, {incomplete} incomplete")
    print(f"Report: {project_dir / 'review' / 'missing-sections.md'}")
    print(f"Next: python -m book_pipeline.review --project-dir {project_dir}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
