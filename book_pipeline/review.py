"""Run quality checks for translated book projects."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_pipeline.common import now_iso, read_json, update_pipeline_stage
from book_pipeline.translate import Glossary, load_glossaries


@dataclass(frozen=True)
class Issue:
    category: str
    severity: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReviewReport:
    structural_issues: list[Issue]
    terminology_issues: list[Issue]
    completeness_issues: list[Issue]
    quality_score: float

    @property
    def all_issues(self) -> list[Issue]:
        return [
            *self.structural_issues,
            *self.terminology_issues,
            *self.completeness_issues,
        ]


def review_project(project_dir: Path) -> ReviewReport:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")

    metadata = read_json(metadata_path)
    glossary = load_glossaries(project_dir)

    structural = run_structural_checks(project_dir, metadata)
    terminology = run_terminology_checks(project_dir, metadata, glossary)
    completeness = run_completeness_checks(project_dir, metadata)
    report = ReviewReport(
        structural_issues=structural,
        terminology_issues=terminology,
        completeness_issues=completeness,
        quality_score=calculate_quality_score([*structural, *terminology, *completeness]),
    )

    write_quality_report(project_dir, report)
    write_structural_report(project_dir, structural)
    write_terminology_report(project_dir, terminology, glossary)
    update_pipeline_stage(project_dir, "review", "done")
    return report


def run_structural_checks(project_dir: Path, metadata: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id", "<missing id>")
        source_path = project_dir / chapter.get("source_path", f"chapters/{chapter_id}.md")
        translated_path = project_dir / chapter.get(
            "translated_path",
            f"translated/{chapter_id}.md",
        )

        if not translated_path.exists():
            issues.append(
                Issue(
                    category="structure",
                    severity="error",
                    message=f"Translated chapter is missing for {chapter_id}",
                    path=str(translated_path),
                )
            )
            continue

        translated_text = translated_path.read_text(encoding="utf-8")
        if not translated_text.strip():
            issues.append(
                Issue(
                    category="structure",
                    severity="error",
                    message=f"Translated chapter is empty for {chapter_id}",
                    path=str(translated_path),
                )
            )

        if source_path.exists():
            source_text = source_path.read_text(encoding="utf-8")
            issues.extend(compare_markdown_structure(source_text, translated_text, translated_path))
            source_words = word_count(source_text)
            translated_words = word_count(translated_text)
            if source_words > 0 and translated_words > source_words * 3:
                issues.append(
                    Issue(
                        category="structure",
                        severity="warning",
                        message=(
                            f"{chapter_id} translation is suspiciously large "
                            f"({translated_words} words vs {source_words} source words)"
                        ),
                        path=str(translated_path),
                    )
                )

    return issues


def compare_markdown_structure(
    source_text: str,
    translated_text: str,
    translated_path: Path,
) -> list[Issue]:
    issues: list[Issue] = []
    source_headings = heading_levels(source_text)
    translated_headings = heading_levels(translated_text)
    if len(source_headings) != len(translated_headings):
        issues.append(
            Issue(
                category="structure",
                severity="warning",
                message=(
                    "Heading count differs: "
                    f"source={len(source_headings)} translated={len(translated_headings)}"
                ),
                path=str(translated_path),
            )
        )
    elif source_headings != translated_headings:
        issues.append(
            Issue(
                category="structure",
                severity="warning",
                message="Heading levels differ between source and translation",
                path=str(translated_path),
            )
        )

    source_lists = count_pattern(source_text, r"^\s*(?:[-*+]|\d+\.)\s+")
    translated_lists = count_pattern(translated_text, r"^\s*(?:[-*+]|\d+\.)\s+")
    if source_lists and translated_lists == 0:
        issues.append(
            Issue(
                category="structure",
                severity="warning",
                message="Source contains list items, but translation has none",
                path=str(translated_path),
            )
        )

    source_quotes = count_pattern(source_text, r"^\s*>")
    translated_quotes = count_pattern(translated_text, r"^\s*>")
    if source_quotes and translated_quotes == 0:
        issues.append(
            Issue(
                category="structure",
                severity="warning",
                message="Source contains block quotes, but translation has none",
                path=str(translated_path),
            )
        )

    return issues


def run_terminology_checks(
    project_dir: Path,
    metadata: dict[str, Any],
    glossary: Glossary,
) -> list[Issue]:
    issues: list[Issue] = []
    all_translated_text = read_all_translated_text(project_dir, metadata)

    for term in glossary.entries():
        if term.english.lower() in all_translated_text.lower():
            continue
        if term.russian and term.russian not in all_translated_text:
            issues.append(
                Issue(
                    category="terminology",
                    severity="info",
                    message=f"Glossary term not found in translations: {term.english} -> {term.russian}",
                )
            )

    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id", "<missing id>")
        translated_path = project_dir / chapter.get(
            "translated_path",
            f"translated/{chapter_id}.md",
        )
        if translated_path.exists():
            issues.extend(detect_english_fragments(translated_path))

    return issues


def run_completeness_checks(project_dir: Path, metadata: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id", "<missing id>")
        chunk_dir = project_dir / "chunks" / chapter_id
        meta_paths = sorted(chunk_dir.glob("*.meta.json"))
        for meta_path in meta_paths:
            meta = read_json(meta_path)
            sequence = int(meta.get("sequence", 0))
            label = f"{chapter_id}_{sequence:04d}"
            status = meta.get("status", "pending")
            translated_path = project_dir / meta.get(
                "translated_path",
                f"chunks/{chapter_id}/{sequence:04d}.ru.md",
            )
            if status not in {"translated", "approved"}:
                issues.append(
                    Issue(
                        category="completeness",
                        severity="error",
                        message=f"Chunk {label} is not translated (status={status})",
                        path=str(meta_path),
                    )
                )
            if not translated_path.exists() or not translated_path.read_text(encoding="utf-8").strip():
                issues.append(
                    Issue(
                        category="completeness",
                        severity="error",
                        message=f"Chunk {label} has no translated text",
                        path=str(translated_path),
                    )
                )

        source_path = project_dir / chapter.get("source_path", f"chapters/{chapter_id}.md")
        translated_path = project_dir / chapter.get(
            "translated_path",
            f"translated/{chapter_id}.md",
        )
        if source_path.exists() and translated_path.exists():
            issues.extend(check_image_references(source_path, translated_path))

    return issues


def detect_english_fragments(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or stripped.startswith("http"):
            continue
        ascii_words = re.findall(r"\b[A-Za-z]{4,}\b", stripped)
        if len(ascii_words) >= 5:
            issues.append(
                Issue(
                    category="terminology",
                    severity="warning",
                    message=(
                        f"Possible untranslated English text on line {line_number}: "
                        f"{' '.join(ascii_words[:8])}"
                    ),
                    path=str(path),
                )
            )
    return issues


def check_image_references(source_path: Path, translated_path: Path) -> list[Issue]:
    source_refs = set(extract_markdown_images(source_path.read_text(encoding="utf-8")))
    translated_text = translated_path.read_text(encoding="utf-8")
    translated_refs = set(extract_markdown_images(translated_text))

    issues: list[Issue] = []
    for image_ref in sorted(source_refs - translated_refs):
        issues.append(
            Issue(
                category="completeness",
                severity="warning",
                message=f"Image reference missing from translation: {image_ref}",
                path=str(translated_path),
            )
        )
    return issues


def extract_markdown_images(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*]\(([^)]+)\)", text)


def read_all_translated_text(project_dir: Path, metadata: dict[str, Any]) -> str:
    pieces: list[str] = []
    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id", "")
        translated_path = project_dir / chapter.get(
            "translated_path",
            f"translated/{chapter_id}.md",
        )
        if translated_path.exists():
            pieces.append(translated_path.read_text(encoding="utf-8"))
    return "\n".join(pieces)


def heading_levels(text: str) -> list[int]:
    return [len(match) for match in re.findall(r"^(#{1,6})\s+", text, flags=re.MULTILINE)]


def count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text))


def calculate_quality_score(issues: list[Issue]) -> float:
    penalty = 0
    for issue in issues:
        if issue.severity == "error":
            penalty += 10
        elif issue.severity == "warning":
            penalty += 5
        else:
            penalty += 1
    return max(0.0, 100.0 - penalty)


def write_quality_report(project_dir: Path, report: ReviewReport) -> None:
    path = project_dir / "review" / "quality-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Quality Report",
        "",
        f"Generated: {now_iso()}",
        f"Quality score: {report.quality_score:.1f}/100",
        "",
    ]
    append_issue_section(lines, "Structural Issues", report.structural_issues)
    append_issue_section(lines, "Terminology Issues", report.terminology_issues)
    append_issue_section(lines, "Completeness Issues", report.completeness_issues)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_structural_report(project_dir: Path, issues: list[Issue]) -> None:
    path = project_dir / "review" / "structural-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Structural Report", "", f"Generated: {now_iso()}", ""]
    append_issue_section(lines, "Findings", issues)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_terminology_report(
    project_dir: Path,
    issues: list[Issue],
    glossary: Glossary,
) -> None:
    path = project_dir / "review" / "terminology-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Terminology Report",
        "",
        f"Generated: {now_iso()}",
        f"Glossary entries loaded: {len(glossary.terms)}",
        "",
        "## Conflicts",
        "",
    ]
    if glossary.conflicts:
        lines.extend(f"- {conflict}" for conflict in glossary.conflicts)
    else:
        lines.append("No glossary conflicts detected.")
    lines.append("")
    append_issue_section(lines, "Findings", issues)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_issue_section(lines: list[str], title: str, issues: list[Issue]) -> None:
    lines.extend([f"## {title}", ""])
    if not issues:
        lines.extend(["No issues found.", ""])
        return

    for issue in issues:
        location = f" `{issue.path}`" if issue.path else ""
        lines.append(f"- **{issue.severity}**{location}: {issue.message}")
    lines.append("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run translation quality checks.")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing metadata, chunks, and translations.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        report = review_project(project_dir)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    print(
        "Review complete: "
        f"{len(report.all_issues)} issue(s), score {report.quality_score:.1f}/100"
    )
    print(f"Report: {project_dir / 'review' / 'quality-report.md'}")
    print(f"Next: python -m book_pipeline.publish --project-dir {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
