"""Split normalized text into logical chapters."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.common import (
    calculate_word_count,
    now_iso,
    read_json,
    slugify,
    update_chapter_metadata,
    update_pipeline_stage,
    write_json,
)
from book_pipeline.normalize import ChapterBoundary, detect_chapter_boundaries


@dataclass
class Chapter:
    """Represents a chapter with content and metadata.
    
    Attributes:
        id: Chapter identifier (e.g., "01_chapter", "00_foreword")
        title: Chapter title extracted from heading
        content: Full chapter markdown content
        start_line: Starting line number in source (1-indexed)
        end_line: Ending line number in source (1-indexed)
    """
    id: str
    title: str
    content: str
    start_line: int
    end_line: int


@dataclass
class ChapterRule:
    """Manual chapter splitting rule.
    
    Attributes:
        id: Chapter identifier
        title: Chapter title
        start_pattern: Regex pattern to match chapter start
        end_pattern: Regex pattern to match chapter end (optional)
    """
    id: str
    title: str
    start_pattern: str
    end_pattern: str | None = None


def split_chapters_auto(text: str) -> list[Chapter]:
    """
    Split text into chapters using automatic boundary detection.
    
    Uses detect_chapter_boundaries to find level-1 headings and creates
    chapters from the detected boundaries. Assigns sequential IDs based
    on chapter type (foreword, chapter, appendix, notes).
    
    Args:
        text: Normalized markdown text
    
    Returns:
        List of Chapter objects
    
    Examples:
        >>> text = "# Chapter 1\\n\\nContent\\n\\n# Chapter 2\\n\\nMore"
        >>> chapters = split_chapters_auto(text)
        >>> len(chapters)
        2
        >>> chapters[0].id
        '01_chapter'
    """
    boundaries = detect_chapter_boundaries(text)
    
    if not boundaries:
        # No boundaries detected - treat entire text as single chapter
        return [Chapter(
            id="01_chapter",
            title="Chapter 1",
            content=text,
            start_line=1,
            end_line=len(text.split("\n"))
        )]
    
    lines = text.split("\n")
    chapters: list[Chapter] = []
    
    # Track chapter numbers by type
    chapter_counters = {
        "foreword": 0,
        "acknowledgments": 0,
        "chapter": 0,
        "appendix": 0,
        "notes": 0,
    }
    
    for i, boundary in enumerate(boundaries):
        # Determine start and end lines
        start_line = boundary.line_number
        
        # End line is either the start of next chapter or end of text
        if i + 1 < len(boundaries):
            end_line = boundaries[i + 1].line_number - 1
        else:
            end_line = len(lines)
        
        # Extract content (lines are 1-indexed, list is 0-indexed)
        chapter_lines = lines[start_line - 1:end_line]
        content = "\n".join(chapter_lines)
        
        # Generate chapter ID based on type
        chapter_type = boundary.chapter_type
        chapter_counters[chapter_type] += 1
        
        if chapter_type == "chapter":
            chapter_id = f"{chapter_counters[chapter_type]:02d}_chapter"
        elif chapter_type == "foreword":
            # Foreword is typically numbered 00
            chapter_id = "00_foreword"
        elif chapter_type == "acknowledgments":
            # Acknowledgments is typically numbered 00
            chapter_id = "00_acknowledgments"
        elif chapter_type == "appendix":
            # Appendices are numbered sequentially
            chapter_id = f"{15 + chapter_counters[chapter_type]:02d}_appendix"
        elif chapter_type == "notes":
            # Notes are numbered at the end
            chapter_id = f"{18 + chapter_counters[chapter_type]:02d}_notes"
        else:
            # Fallback for unknown types
            chapter_id = f"{len(chapters) + 1:02d}_chapter"
        
        chapters.append(Chapter(
            id=chapter_id,
            title=boundary.title,
            content=content,
            start_line=start_line,
            end_line=end_line
        ))
    
    return chapters


def split_chapters_manual(text: str, rules_file: Path) -> list[Chapter]:
    """
    Split text into chapters using manual rules from JSON file.
    
    Reads chapter definitions from a JSON file with start/end patterns
    and splits the text at specified boundaries. Patterns are matched
    as regular expressions against the normalized text.
    
    Args:
        text: Normalized markdown text
        rules_file: Path to chapter-rules.json
    
    Returns:
        List of Chapter objects in the order defined in rules file
    
    Raises:
        FileNotFoundError: If rules_file doesn't exist
        ValueError: If rules format is invalid or patterns don't match
    
    Examples:
        >>> rules = Path("chapter-rules.json")
        >>> chapters = split_chapters_manual(text, rules)
    
    Notes:
        - If end_pattern is not provided, the chapter extends to the start
          of the next chapter or end of text
        - Patterns are matched using re.search() with re.MULTILINE flag
        - Line numbers are 1-indexed to match editor conventions
    """
    import re
    
    if not rules_file.exists():
        raise FileNotFoundError(
            f"Chapter rules file not found: {rules_file}\n"
            f"Create a chapter-rules.json file with manual chapter definitions."
        )
    
    try:
        rules_data = read_json(rules_file)
    except Exception as error:
        raise ValueError(f"Failed to parse chapter rules: {error}") from error
    
    # Validate rules format
    if "chapters" not in rules_data:
        raise ValueError(
            "Invalid chapter rules format. Expected JSON with 'chapters' array."
        )
    
    rules: list[ChapterRule] = []
    for rule_dict in rules_data["chapters"]:
        if "id" not in rule_dict or "title" not in rule_dict or "start_pattern" not in rule_dict:
            raise ValueError(
                f"Invalid chapter rule: {rule_dict}. "
                f"Required fields: id, title, start_pattern"
            )
        
        rules.append(ChapterRule(
            id=rule_dict["id"],
            title=rule_dict["title"],
            start_pattern=rule_dict["start_pattern"],
            end_pattern=rule_dict.get("end_pattern")
        ))
    
    if not rules:
        raise ValueError("No chapter rules defined in rules file")
    
    lines = text.split("\n")
    chapters: list[Chapter] = []
    
    # Find chapter boundaries by matching patterns
    for i, rule in enumerate(rules):
        # Find start position
        try:
            start_match = re.search(rule.start_pattern, text, re.MULTILINE)
        except re.error as error:
            raise ValueError(
                f"Invalid regex pattern in start_pattern for chapter '{rule.id}': {error}"
            ) from error
        
        if not start_match:
            raise ValueError(
                f"Start pattern not found for chapter '{rule.id}': {rule.start_pattern}"
            )
        
        # Calculate start line number (1-indexed)
        start_pos = start_match.start()
        start_line = text[:start_pos].count("\n") + 1
        
        # Find end position
        if rule.end_pattern:
            # Use explicit end pattern
            try:
                end_match = re.search(rule.end_pattern, text[start_pos:], re.MULTILINE)
            except re.error as error:
                raise ValueError(
                    f"Invalid regex pattern in end_pattern for chapter '{rule.id}': {error}"
                ) from error
            
            if not end_match:
                raise ValueError(
                    f"End pattern not found for chapter '{rule.id}': {rule.end_pattern}"
                )
            
            # End position is relative to start_pos
            end_pos = start_pos + end_match.start()
            end_line = text[:end_pos].count("\n")
        else:
            # Use start of next chapter as end, or end of text
            if i + 1 < len(rules):
                # Find next chapter's start
                next_rule = rules[i + 1]
                try:
                    next_match = re.search(next_rule.start_pattern, text[start_pos:], re.MULTILINE)
                except re.error as error:
                    raise ValueError(
                        f"Invalid regex pattern in start_pattern for chapter '{next_rule.id}': {error}"
                    ) from error
                
                if not next_match:
                    raise ValueError(
                        f"Start pattern not found for chapter '{next_rule.id}': {next_rule.start_pattern}"
                    )
                
                end_pos = start_pos + next_match.start()
                end_line = text[:end_pos].count("\n")
            else:
                # Last chapter extends to end of text
                end_pos = len(text)
                end_line = len(lines)
        
        # Extract content
        chapter_lines = lines[start_line - 1:end_line]
        content = "\n".join(chapter_lines)
        
        chapters.append(Chapter(
            id=rule.id,
            title=rule.title,
            content=content,
            start_line=start_line,
            end_line=end_line
        ))
    
    return chapters


def log_ambiguous_boundaries(
    chapters: list[Chapter],
    project_dir: Path,
    mode: str
) -> None:
    """
    Log ambiguous chapter boundaries to review/notes.md.
    
    Identifies potential issues with chapter splitting such as:
    - Very short chapters (< 100 words)
    - Very long chapters (> 10000 words)
    - Chapters with generic titles
    - Overlapping line ranges
    
    Args:
        chapters: List of Chapter objects
        project_dir: Project root directory
        mode: Splitting mode ('auto' or 'manual')
    """
    notes_path = project_dir / "review" / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    
    warnings: list[str] = []
    
    # Check for very short chapters
    for chapter in chapters:
        word_count = calculate_word_count(chapter.content)
        if word_count < 100:
            warnings.append(
                f"- **{chapter.id}** ({chapter.title}): Very short chapter ({word_count} words). "
                f"Consider merging with adjacent chapter."
            )
    
    # Check for very long chapters
    for chapter in chapters:
        word_count = calculate_word_count(chapter.content)
        if word_count > 10000:
            warnings.append(
                f"- **{chapter.id}** ({chapter.title}): Very long chapter ({word_count} words). "
                f"Consider splitting into multiple chapters."
            )
    
    # Check for generic titles (only in auto mode)
    if mode == "auto":
        generic_patterns = [
            r"^Chapter \d+$",
            r"^Section \d+$",
            r"^Part \d+$",
            r"^Untitled$",
        ]
        
        for chapter in chapters:
            for pattern in generic_patterns:
                if re.match(pattern, chapter.title, re.IGNORECASE):
                    warnings.append(
                        f"- **{chapter.id}** ({chapter.title}): Generic title detected. "
                        f"Consider adding descriptive title."
                    )
                    break
    
    # Check for overlapping line ranges
    sorted_chapters = sorted(chapters, key=lambda c: c.start_line)
    for i in range(len(sorted_chapters) - 1):
        current = sorted_chapters[i]
        next_chapter = sorted_chapters[i + 1]
        
        if current.end_line >= next_chapter.start_line:
            warnings.append(
                f"- **{current.id}** and **{next_chapter.id}**: Overlapping line ranges "
                f"({current.start_line}-{current.end_line} and {next_chapter.start_line}-{next_chapter.end_line}). "
                f"Check chapter boundaries."
            )
    
    # Write warnings to notes.md if any exist
    if warnings:
        notes_content = [
            "# Chapter Splitting Notes",
            "",
            f"**Mode**: {mode}",
            f"**Date**: {now_iso()}",
            "",
            "## Ambiguous Boundaries",
            "",
            "The following potential issues were detected during chapter splitting:",
            "",
        ]
        notes_content.extend(warnings)
        notes_content.extend([
            "",
            "## Recommendations",
            "",
            "Review the flagged chapters and consider:",
            "",
            "1. Adjusting chapter boundaries manually using chapter-rules.json",
            "2. Merging very short chapters with adjacent content",
            "3. Splitting very long chapters for better translation workflow",
            "4. Adding descriptive titles to generic chapter headings",
            "",
        ])
        
        # Append to existing notes.md if it exists
        if notes_path.exists():
            existing_content = notes_path.read_text(encoding="utf-8")
            notes_content.insert(0, existing_content)
            notes_content.insert(1, "")
            notes_content.insert(2, "---")
            notes_content.insert(3, "")
        
        notes_path.write_text("\n".join(notes_content), encoding="utf-8")
        print(f"Logged {len(warnings)} warnings to {notes_path}")


def write_chapters(
    chapters: list[Chapter],
    project_dir: Path,
    mode: str = "auto",
    force: bool = False
) -> None:
    """
    Write chapters to individual markdown files.
    
    Creates one file per chapter in the chapters/ directory and updates
    metadata.json with chapter information. Also logs any ambiguous
    boundaries to review/notes.md.
    
    Args:
        chapters: List of Chapter objects to write
        project_dir: Project root directory
        mode: Splitting mode ('auto' or 'manual')
        force: Overwrite existing chapter files if True
    
    Raises:
        FileExistsError: If chapter files exist and force is False
    """
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for existing files if not force
    if not force:
        existing_files = []
        for chapter in chapters:
            chapter_path = chapters_dir / f"{chapter.id}.md"
            if chapter_path.exists():
                existing_files.append(chapter_path)
        
        if existing_files:
            raise FileExistsError(
                f"Chapter files already exist: {', '.join(str(f) for f in existing_files)}\n"
                f"Re-run with --force to overwrite."
            )
    
    # Write chapter files
    for chapter in chapters:
        chapter_path = chapters_dir / f"{chapter.id}.md"
        chapter_path.write_text(chapter.content, encoding="utf-8")
        print(f"Wrote chapter: {chapter_path}")
    
    # Update metadata.json with chapter list
    metadata_path = project_dir / "metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json not found at {metadata_path}. "
            "Ensure the project is initialized."
        )
    
    metadata = read_json(metadata_path)
    
    # Build chapter metadata list
    chapter_metadata_list = []
    for chapter in chapters:
        word_count = calculate_word_count(chapter.content)
        
        chapter_metadata_list.append({
            "id": chapter.id,
            "title": chapter.title,
            "source_path": f"chapters/{chapter.id}.md",
            "translated_path": f"translated/{chapter.id}.md",
            "status": "chunked",  # Ready for chunking
            "word_count": word_count,
            "chunk_count": 0,  # Will be updated during chunking
        })
    
    # Update metadata
    metadata["chapters"] = chapter_metadata_list
    metadata["updated_at"] = now_iso()
    
    write_json(metadata_path, metadata)
    print(f"Updated metadata with {len(chapters)} chapters")
    
    # Log ambiguous boundaries
    log_ambiguous_boundaries(chapters, project_dir, mode)


def split_project_chapters(
    project_dir: Path,
    mode: str = "auto",
    rules_file: Path | None = None,
    force: bool = False,
) -> list[Chapter]:
    """Split normalized project text and update project chapter metadata."""

    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    normalized_path = project_dir / "source" / "normalized.md"
    if not normalized_path.exists():
        raise FileNotFoundError(
            f"Normalized markdown not found: {normalized_path}. "
            "Run normalization first."
        )

    normalized_text = normalized_path.read_text(encoding="utf-8")
    if mode == "auto":
        chapters = split_chapters_auto(normalized_text)
    elif mode == "manual":
        if rules_file is None:
            raise ValueError("Manual mode requires rules_file")
        chapters = split_chapters_manual(normalized_text, rules_file)
    else:
        raise ValueError("mode must be 'auto' or 'manual'")

    write_chapters(chapters, project_dir, mode=mode, force=force)
    update_pipeline_stage(project_dir, "split", "done")
    return chapters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split normalized text into logical chapters."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing source/normalized.md",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "manual"],
        default="auto",
        help="Chapter splitting mode: auto (detect headings) or manual (use rules file)",
    )
    parser.add_argument(
        "--rules-file",
        help="Path to chapter-rules.json (required for manual mode)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing chapter files if they exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)
    
    # Validate project directory exists
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2
    
    # Validate normalized.md exists
    normalized_path = project_dir / "source" / "normalized.md"
    if not normalized_path.exists():
        print(
            f"Normalized markdown not found: {normalized_path}\n"
            f"Run normalization first:\n"
            f"  python -m book_pipeline.normalize --project-dir {project_dir}",
            file=sys.stderr,
        )
        return 2
    
    # Validate manual mode requirements
    if args.mode == "manual":
        if not args.rules_file:
            print(
                "Manual mode requires --rules-file parameter",
                file=sys.stderr,
            )
            return 2
        
        rules_file = Path(args.rules_file)
        if not rules_file.exists():
            print(
                f"Chapter rules file not found: {rules_file}",
                file=sys.stderr,
            )
            return 2
    
    # Read normalized text
    try:
        normalized_text = normalized_path.read_text(encoding="utf-8")
    except Exception as error:
        print(f"Failed to read {normalized_path}: {error}", file=sys.stderr)
        return 2
    
    print(f"Read {len(normalized_text)} characters from {normalized_path}")
    
    # Split chapters based on mode
    try:
        if args.mode == "auto":
            print("Using automatic chapter detection...")
            chapters = split_chapters_auto(normalized_text)
        else:
            print(f"Using manual chapter rules from {args.rules_file}...")
            rules_file = Path(args.rules_file)
            chapters = split_chapters_manual(normalized_text, rules_file)
    except Exception as error:
        print(f"Chapter splitting failed: {error}", file=sys.stderr)
        return 2
    
    print(f"Detected {len(chapters)} chapters")
    
    # Write chapters to files
    try:
        write_chapters(chapters, project_dir, mode=args.mode, force=args.force)
    except FileExistsError as error:
        print(error, file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Failed to write chapters: {error}", file=sys.stderr)
        return 2
    
    # Update pipeline state
    update_pipeline_stage(project_dir, "split", "done")
    
    print(f"Chapter splitting complete!")
    print(f"Next: python -m book_pipeline.chunk --project-dir {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
