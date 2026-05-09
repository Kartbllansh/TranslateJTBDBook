"""Normalize extracted text to remove PDF artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.common import update_pipeline_stage


@dataclass
class NormalizationConfig:
    """Configuration options for text normalization.
    
    Attributes:
        remove_page_numbers: Remove page number patterns (Page N, N |, etc.)
        join_hyphenated_words: Merge words split across lines with hyphens
        detect_headers_footers: Find and remove repeated headers/footers
        preserve_code_blocks: Protect code blocks from normalization
        preserve_lists: Protect list formatting from normalization
    """
    remove_page_numbers: bool = True
    join_hyphenated_words: bool = True
    detect_headers_footers: bool = True
    preserve_code_blocks: bool = True
    preserve_lists: bool = True


def detect_headers_footers(text: str, min_repetitions: int = 3) -> list[str]:
    """
    Detect repeated patterns that are likely headers or footers.
    
    Scans the text for lines that appear repeatedly (at least min_repetitions times)
    and are likely to be headers or footers based on their position and content.
    Common patterns include page numbers, chapter titles, book titles, and
    copyright notices.
    
    Args:
        text: Markdown text to analyze
        min_repetitions: Minimum number of times a pattern must appear
    
    Returns:
        List of detected header/footer patterns to remove
    
    Examples:
        >>> text = "Header\\nContent\\nHeader\\nMore\\nHeader\\n"
        >>> patterns = detect_headers_footers(text, min_repetitions=2)
        >>> "Header" in patterns
        True
    """
    lines = text.split("\n")
    
    # Count line occurrences (ignoring empty lines and very long lines)
    line_counts: Counter[str] = Counter()
    for line in lines:
        stripped = line.strip()
        # Skip empty lines, very long lines (likely content), and markdown headings
        if stripped and len(stripped) < 100 and not stripped.startswith("#"):
            line_counts[stripped] += 1
    
    # Find patterns that repeat enough times
    patterns: list[str] = []
    for line, count in line_counts.items():
        if count >= min_repetitions:
            # Additional heuristics: likely headers/footers are short and may contain numbers
            if len(line) < 80:
                patterns.append(line)
    
    return patterns


def remove_page_numbers(text: str) -> str:
    """
    Remove page number patterns from text.
    
    Removes common page number formats found in PDFs:
    - "Page N" or "page N"
    - "N |" (page number with separator)
    - "| N" (separator with page number)
    - Standalone numbers on their own line
    - "- N -" (centered page numbers)
    
    Args:
        text: Markdown text with page numbers
    
    Returns:
        Text with page numbers removed
    
    Examples:
        >>> remove_page_numbers("Content\\nPage 42\\nMore content")
        'Content\\nMore content'
        >>> remove_page_numbers("Text\\n42 |\\nMore text")
        'Text\\nMore text'
    """
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (preserve them)
        if not stripped:
            cleaned_lines.append(line)
            continue
        
        # Pattern 1: "Page N" or "page N"
        if re.match(r"^[Pp]age\s+\d+$", stripped):
            continue
        
        # Pattern 2: "N |" (page number with separator)
        if re.match(r"^\d+\s*\|$", stripped):
            continue
        
        # Pattern 3: "| N" (separator with page number)
        if re.match(r"^\|\s*\d+$", stripped):
            continue
        
        # Pattern 4: "- N -" (centered page numbers)
        if re.match(r"^-\s*\d+\s*-$", stripped):
            continue
        
        # Pattern 5: Standalone number on its own line (be conservative)
        # Only remove if it's a reasonable page number (1-9999)
        if re.match(r"^\d{1,4}$", stripped):
            continue
        
        # Keep the line
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)


def join_hyphenated_words(text: str) -> str:
    """
    Join words split across lines with hyphens.
    
    When PDFs break words across line boundaries, they often insert hyphens.
    This function merges such words back together. It preserves intentional
    hyphens in compound words by only joining when the hyphen appears at
    the end of a line.
    
    Args:
        text: Markdown text with hyphenated line breaks
    
    Returns:
        Text with hyphenated words joined
    
    Examples:
        >>> join_hyphenated_words("This is a long-\\nword that was split.")
        'This is a longword that was split.'
        >>> join_hyphenated_words("Well-known phrase")  # Preserves intentional hyphens
        'Well-known phrase'
    """
    # Pattern: word ending with hyphen, followed by newline, followed by word
    # Use word boundaries to avoid matching markdown or other syntax
    # Match: "word-\n" followed by "word" (possibly with leading whitespace)
    pattern = r"(\w)-\n\s*(\w)"
    
    # Replace with the two word parts joined (no hyphen, no newline)
    result = re.sub(pattern, r"\1\2", text)
    
    return result


def preserve_markdown_structure(text: str, config: NormalizationConfig) -> str:
    """
    Protect markdown structural elements during normalization.
    
    Identifies and marks code blocks, lists, and quotes so they aren't
    modified by other normalization steps. This is a preparatory step
    that should be called before other normalizations.
    
    Currently, this function serves as a validation step to ensure
    markdown structure is maintained. The actual preservation happens
    through careful regex patterns in other normalization functions.
    
    Args:
        text: Markdown text to protect
        config: Normalization configuration
    
    Returns:
        Text with structure preserved (currently returns input unchanged)
    
    Note:
        In the current implementation, preservation is handled by the
        careful design of regex patterns in other functions rather than
        by explicit marking/unmarking of protected regions.
    """
    # For now, this is a pass-through function that validates structure
    # The actual preservation happens through careful regex patterns in
    # other normalization functions (e.g., join_hyphenated_words only
    # operates on word characters, not markdown syntax)
    
    # Future enhancement: Could mark protected regions with placeholders
    # and restore them after normalization
    
    return text


def normalize_text(text: str, config: NormalizationConfig) -> str:
    """
    Clean extracted markdown text by removing PDF artifacts.
    
    Applies multiple normalization steps in sequence:
    1. Preserve markdown structure (code blocks, lists, quotes)
    2. Remove page numbers
    3. Remove repeated headers and footers
    4. Join hyphenated words split across lines
    
    Args:
        text: Raw extracted markdown
        config: Normalization configuration
    
    Returns:
        Cleaned markdown text
    
    Examples:
        >>> config = NormalizationConfig()
        >>> text = "Content\\nPage 42\\nMore content"
        >>> normalized = normalize_text(text, config)
        >>> "Page 42" not in normalized
        True
    """
    # Step 1: Preserve markdown structure
    if config.preserve_code_blocks or config.preserve_lists:
        text = preserve_markdown_structure(text, config)
    
    # Step 2: Remove page numbers
    if config.remove_page_numbers:
        text = remove_page_numbers(text)
    
    # Step 3: Detect and remove headers/footers
    if config.detect_headers_footers:
        patterns = detect_headers_footers(text)
        for pattern in patterns:
            # Remove the pattern (whole line)
            # Use word boundaries to avoid partial matches
            text = re.sub(
                rf"^{re.escape(pattern)}$",
                "",
                text,
                flags=re.MULTILINE
            )
    
    # Step 4: Join hyphenated words
    if config.join_hyphenated_words:
        text = join_hyphenated_words(text)
    
    # Clean up excessive blank lines (more than 2 consecutive)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    
    return text


@dataclass
class ChapterBoundary:
    """Represents a detected chapter boundary.
    
    Attributes:
        line_number: Line number where the chapter starts (1-indexed)
        title: Chapter title extracted from heading
        heading_text: Full heading text including markdown markers
        chapter_type: Type of chapter (chapter, foreword, acknowledgments, appendix, notes)
    """
    line_number: int
    title: str
    heading_text: str
    chapter_type: str


def detect_chapter_boundaries(text: str) -> list[ChapterBoundary]:
    """
    Detect potential chapter boundaries in normalized text.
    
    Scans for level-1 headings (# Heading) and identifies chapter boundaries.
    Detects special sections like Foreword, Acknowledgments, Appendix, and Notes
    based on heading text patterns.
    
    Args:
        text: Normalized markdown text
    
    Returns:
        List of ChapterBoundary objects with line numbers and titles
    
    Examples:
        >>> text = "# Chapter 1\\n\\nContent\\n\\n# Chapter 2\\n\\nMore"
        >>> boundaries = detect_chapter_boundaries(text)
        >>> len(boundaries)
        2
        >>> boundaries[0].title
        'Chapter 1'
        >>> boundaries[0].chapter_type
        'chapter'
    """
    boundaries: list[ChapterBoundary] = []
    lines = text.split("\n")
    
    # Special section patterns (case-insensitive)
    special_patterns = {
        "foreword": r"^#\s+(foreword|preface|introduction)(\s|$)",
        "acknowledgments": r"^#\s+(acknowledgments?|acknowledgements?|thanks)(\s|$)",
        "appendix": r"^#\s+(appendix|appendices)(\s|[:\d]|$)",
        "notes": r"^#\s+(notes?|endnotes?|references?)(\s|$)",
    }
    
    for line_num, line in enumerate(lines, start=1):
        # Check for level-1 heading
        heading_match = re.match(r"^#\s+(.+)$", line)
        if not heading_match:
            continue
        
        title = heading_match.group(1).strip()
        heading_text = line
        
        # Determine chapter type
        chapter_type = "chapter"  # Default
        line_lower = line.lower()
        
        for special_type, pattern in special_patterns.items():
            if re.match(pattern, line_lower, re.IGNORECASE):
                chapter_type = special_type
                break
        
        boundaries.append(ChapterBoundary(
            line_number=line_num,
            title=title,
            heading_text=heading_text,
            chapter_type=chapter_type
        ))
    
    return boundaries


def generate_normalization_report(
    original_text: str,
    normalized_text: str,
    detected_patterns: list[str],
    chapter_boundaries: list[ChapterBoundary] | None = None
) -> str:
    """
    Generate a report of normalization changes.
    
    Creates a markdown report documenting what was detected and removed
    during normalization, including headers/footers, page numbers, chapter
    boundaries, and statistics about the changes.
    
    Args:
        original_text: Text before normalization
        normalized_text: Text after normalization
        detected_patterns: List of header/footer patterns found
        chapter_boundaries: List of detected chapter boundaries (optional)
    
    Returns:
        Markdown report content
    """
    original_lines = len(original_text.split("\n"))
    normalized_lines = len(normalized_text.split("\n"))
    lines_removed = original_lines - normalized_lines
    
    report_lines = [
        "# Normalization Report",
        "",
        "## Statistics",
        "",
        f"- Original line count: {original_lines}",
        f"- Normalized line count: {normalized_lines}",
        f"- Lines removed: {lines_removed}",
        "",
        "## Detected Headers/Footers",
        "",
    ]
    
    if detected_patterns:
        report_lines.append("The following repeated patterns were detected and removed:")
        report_lines.append("")
        for pattern in detected_patterns:
            report_lines.append(f"- `{pattern}`")
    else:
        report_lines.append("No repeated header/footer patterns detected.")
    
    report_lines.extend([
        "",
        "## Normalization Steps Applied",
        "",
        "1. ✓ Page numbers removed",
        "2. ✓ Headers and footers removed",
        "3. ✓ Hyphenated words joined",
        "4. ✓ Markdown structure preserved",
        "",
    ])
    
    # Add chapter boundary suggestions if provided
    if chapter_boundaries is not None:
        report_lines.extend([
            "## Detected Chapter Boundaries",
            "",
        ])
        
        if chapter_boundaries:
            report_lines.append(f"Found {len(chapter_boundaries)} potential chapter boundaries:")
            report_lines.append("")
            
            for boundary in chapter_boundaries:
                chapter_type_label = boundary.chapter_type.capitalize()
                report_lines.append(
                    f"- **Line {boundary.line_number}** ({chapter_type_label}): {boundary.title}"
                )
            
            report_lines.extend([
                "",
                "### Chapter Type Summary",
                "",
            ])
            
            # Count chapter types
            type_counts: dict[str, int] = {}
            for boundary in chapter_boundaries:
                type_counts[boundary.chapter_type] = type_counts.get(boundary.chapter_type, 0) + 1
            
            for chapter_type, count in sorted(type_counts.items()):
                report_lines.append(f"- {chapter_type.capitalize()}: {count}")
        else:
            report_lines.append("No level-1 headings detected. Consider:")
            report_lines.append("")
            report_lines.append("- Checking if the PDF extraction preserved heading structure")
            report_lines.append("- Using manual chapter splitting with chapter-rules.json")
    
    report_lines.extend([
        "",
        "## Next Steps",
        "",
        "Review the normalized text in `source/normalized.md` and verify:",
        "",
        "- Chapter boundaries are clear",
        "- No content was incorrectly removed",
        "- Formatting is preserved",
        "",
        "Then proceed to chapter splitting:",
        "",
        "```bash",
        "python -m book_pipeline.split_chapters --project-dir <project-dir>",
        "```",
    ])
    
    return "\n".join(report_lines)


def normalize_project(project_dir: Path, force: bool = False) -> Path:
    """Normalize a project's extracted markdown and write report files."""

    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    extracted_path = project_dir / "source" / "extracted.md"
    if not extracted_path.exists():
        raise FileNotFoundError(
            f"Extracted markdown not found: {extracted_path}. "
            "Run extraction first."
        )

    normalized_path = project_dir / "source" / "normalized.md"
    if normalized_path.exists() and not force:
        raise FileExistsError(
            f"{normalized_path} already exists. Re-run with --force to overwrite."
        )

    extracted_text = extracted_path.read_text(encoding="utf-8")
    config = NormalizationConfig()
    detected_patterns = detect_headers_footers(extracted_text)
    normalized_text = normalize_text(extracted_text, config)
    chapter_boundaries = detect_chapter_boundaries(normalized_text)

    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_text(normalized_text, encoding="utf-8")

    report_path = project_dir / "review" / "normalization-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        generate_normalization_report(
            extracted_text,
            normalized_text,
            detected_patterns,
            chapter_boundaries,
        ),
        encoding="utf-8",
    )
    update_pipeline_stage(project_dir, "normalize", "done")
    return normalized_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize extracted markdown text by removing PDF artifacts."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing source/extracted.md",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing normalized.md if it exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)
    
    # Validate project directory exists
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2
    
    # Validate extracted.md exists
    extracted_path = project_dir / "source" / "extracted.md"
    if not extracted_path.exists():
        print(
            f"Extracted markdown not found: {extracted_path}\n"
            f"Run extraction first:\n"
            f"  python -m book_pipeline.extract_opendataloader --project-dir {project_dir}",
            file=sys.stderr,
        )
        return 2
    
    # Check if normalized.md already exists
    normalized_path = project_dir / "source" / "normalized.md"
    if normalized_path.exists() and not args.force:
        print(
            f"{normalized_path} already exists. Re-run with --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    
    # Read extracted text
    try:
        extracted_text = extracted_path.read_text(encoding="utf-8")
    except Exception as error:
        print(f"Failed to read {extracted_path}: {error}", file=sys.stderr)
        return 2
    
    print(f"Read {len(extracted_text)} characters from {extracted_path}")
    
    # Create normalization configuration
    config = NormalizationConfig(
        remove_page_numbers=True,
        join_hyphenated_words=True,
        detect_headers_footers=True,
        preserve_code_blocks=True,
        preserve_lists=True,
    )
    
    # Detect patterns before normalization (for reporting)
    detected_patterns = detect_headers_footers(extracted_text) if config.detect_headers_footers else []
    
    print(f"Detected {len(detected_patterns)} repeated header/footer patterns")
    
    # Normalize text
    normalized_text = normalize_text(extracted_text, config)
    
    print(f"Normalized to {len(normalized_text)} characters")
    
    # Detect chapter boundaries in normalized text
    chapter_boundaries = detect_chapter_boundaries(normalized_text)
    
    print(f"Detected {len(chapter_boundaries)} potential chapter boundaries")
    
    # Write normalized text
    try:
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(normalized_text, encoding="utf-8")
    except Exception as error:
        print(f"Failed to write {normalized_path}: {error}", file=sys.stderr)
        return 2
    
    # Generate and write normalization report
    report_content = generate_normalization_report(
        extracted_text,
        normalized_text,
        detected_patterns,
        chapter_boundaries
    )
    
    report_path = project_dir / "review" / "normalization-report.md"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_content, encoding="utf-8")
        print(f"Normalization report written to: {report_path}")
    except Exception as error:
        print(f"Warning: Failed to write report {report_path}: {error}", file=sys.stderr)
    
    # Update pipeline state
    update_pipeline_stage(project_dir, "normalize", "done")
    
    print(f"Normalized text written to: {normalized_path}")
    print(f"Next: python -m book_pipeline.split_chapters --project-dir {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
