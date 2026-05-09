"""Tests for split_chapters module.

This test suite validates task 3.2: Implement automatic chapter detection
Requirements: 4.1, 4.6, 4.7
"""

from book_pipeline.split_chapters import split_chapters_auto, Chapter


def test_split_chapters_auto_basic():
    """Test basic automatic chapter splitting.
    
    Validates:
    - Requirement 4.1: Scan for level-1 headings as chapter boundaries
    - Requirement 4.6: Assign sequential IDs (01_chapter, 02_chapter, etc.)
    - Requirement 4.7: Extract chapter titles from heading text
    """
    text = """# Chapter 1: Introduction

This is the first chapter.

# Chapter 2: Background

This is the second chapter.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 2
    assert chapters[0].id == "01_chapter"
    assert chapters[0].title == "Chapter 1: Introduction"
    assert "This is the first chapter." in chapters[0].content
    
    assert chapters[1].id == "02_chapter"
    assert chapters[1].title == "Chapter 2: Background"
    assert "This is the second chapter." in chapters[1].content


def test_split_chapters_auto_special_sections():
    """Test detection of special sections like foreword and appendix.
    
    Validates:
    - Requirement 4.1: Handle special sections (foreword, appendix, notes)
    - Requirement 4.6: Assign special IDs (00_foreword, 15+_appendix, 18+_notes)
    """
    text = """# Foreword

Introduction by the author.

# Chapter 1

Main content.

# Appendix A

Additional material.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 3
    assert chapters[0].id == "00_foreword"
    assert chapters[0].title == "Foreword"
    
    assert chapters[1].id == "01_chapter"
    assert chapters[1].title == "Chapter 1"
    
    # Appendix should have higher number (16 for first appendix)
    assert chapters[2].id == "16_appendix"
    assert chapters[2].title == "Appendix A"


def test_split_chapters_auto_acknowledgments():
    """Test detection of acknowledgments section.
    
    Validates:
    - Requirement 4.1: Handle special sections (acknowledgments)
    - Requirement 4.6: Assign ID 00_acknowledgments
    """
    text = """# Acknowledgments

Thanks to everyone who helped.

# Chapter 1

Main content.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 2
    assert chapters[0].id == "00_acknowledgments"
    assert chapters[0].title == "Acknowledgments"
    assert "Thanks to everyone" in chapters[0].content


def test_split_chapters_auto_notes():
    """Test detection of notes section.
    
    Validates:
    - Requirement 4.1: Handle special sections (notes)
    - Requirement 4.6: Assign ID 19_notes (18 + counter)
    """
    text = """# Chapter 1

Main content.

# Notes

Endnotes and references.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 2
    assert chapters[0].id == "01_chapter"
    assert chapters[1].id == "19_notes"
    assert chapters[1].title == "Notes"


def test_split_chapters_auto_multiple_appendices():
    """Test handling of multiple appendices.
    
    Validates:
    - Requirement 4.6: Sequential numbering for multiple appendices
    """
    text = """# Chapter 1

Content.

# Appendix A

First appendix.

# Appendix B

Second appendix.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 3
    assert chapters[0].id == "01_chapter"
    assert chapters[1].id == "16_appendix"
    assert chapters[1].title == "Appendix A"
    assert chapters[2].id == "17_appendix"
    assert chapters[2].title == "Appendix B"


def test_split_chapters_auto_no_boundaries():
    """Test handling of text with no chapter boundaries.
    
    Validates:
    - Requirement 4.1: Handle edge case of no level-1 headings
    - Should create a single default chapter
    """
    text = """This is a book with no chapter headings.

Just continuous text.
"""
    
    chapters = split_chapters_auto(text)
    
    # Should create a single chapter
    assert len(chapters) == 1
    assert chapters[0].id == "01_chapter"
    assert chapters[0].title == "Chapter 1"
    assert "This is a book" in chapters[0].content


def test_split_chapters_auto_line_numbers():
    """Test that line numbers are correctly tracked.
    
    Validates:
    - Requirement 4.1: Track start and end line numbers for each chapter
    """
    text = """# Chapter 1

First chapter content.
More content.

# Chapter 2

Second chapter content.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 2
    
    # First chapter starts at line 1
    assert chapters[0].start_line == 1
    # First chapter ends before second chapter starts
    assert chapters[0].end_line < chapters[1].start_line
    
    # Second chapter starts at line 6 (after blank line)
    assert chapters[1].start_line == 6
    # Second chapter ends at last line
    assert chapters[1].end_line == len(text.split("\n"))


def test_split_chapters_auto_content_extraction():
    """Test that chapter content is correctly extracted.
    
    Validates:
    - Requirement 4.7: Extract complete chapter content including heading
    """
    text = """# Chapter 1: Introduction

This is the first paragraph.

This is the second paragraph.

# Chapter 2: Background

Different content here.
"""
    
    chapters = split_chapters_auto(text)
    
    # First chapter should include heading and all content until next chapter
    assert chapters[0].content.startswith("# Chapter 1: Introduction")
    assert "first paragraph" in chapters[0].content
    assert "second paragraph" in chapters[0].content
    assert "Different content" not in chapters[0].content
    
    # Second chapter should include its heading and content
    assert chapters[1].content.startswith("# Chapter 2: Background")
    assert "Different content" in chapters[1].content


def test_split_chapters_auto_mixed_special_sections():
    """Test handling of multiple special sections in realistic order.
    
    Validates:
    - Requirement 4.1: Handle complex book structure with multiple special sections
    - Requirement 4.6: Correct ID assignment for mixed section types
    """
    text = """# Foreword

By the editor.

# Acknowledgments

Thanks to all.

# Chapter 1

First chapter.

# Chapter 2

Second chapter.

# Appendix A: Data Tables

Tables here.

# Appendix B: References

References here.

# Notes

Endnotes here.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 7
    
    # Check IDs are assigned correctly
    assert chapters[0].id == "00_foreword"
    assert chapters[1].id == "00_acknowledgments"
    assert chapters[2].id == "01_chapter"
    assert chapters[3].id == "02_chapter"
    assert chapters[4].id == "16_appendix"
    assert chapters[5].id == "17_appendix"
    assert chapters[6].id == "19_notes"
    
    # Check titles are extracted correctly
    assert chapters[0].title == "Foreword"
    assert chapters[1].title == "Acknowledgments"
    assert chapters[4].title == "Appendix A: Data Tables"
    assert chapters[5].title == "Appendix B: References"


def test_split_chapters_auto_case_insensitive_detection():
    """Test that special section detection is case-insensitive.
    
    Validates:
    - Requirement 4.1: Detect special sections regardless of capitalization
    """
    text = """# FOREWORD

Uppercase foreword.

# acknowledgments

Lowercase acknowledgments.

# Appendix

Mixed case appendix.
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 3
    assert chapters[0].id == "00_foreword"
    assert chapters[1].id == "00_acknowledgments"
    assert chapters[2].id == "16_appendix"


def test_chapter_dataclass():
    """Test Chapter dataclass creation and attributes.
    
    Validates:
    - Chapter dataclass has all required fields
    """
    chapter = Chapter(
        id="01_chapter",
        title="Test Chapter",
        content="# Test Chapter\n\nContent here.",
        start_line=1,
        end_line=3
    )
    
    assert chapter.id == "01_chapter"
    assert chapter.title == "Test Chapter"
    assert chapter.start_line == 1
    assert chapter.end_line == 3
    assert "Content here" in chapter.content


def test_split_chapters_auto_preserves_markdown():
    """Test that markdown formatting is preserved in chapter content.
    
    Validates:
    - Requirement 4.7: Preserve markdown structure in extracted content
    """
    text = """# Chapter 1

## Section 1.1

Some content with **bold** and *italic*.

- List item 1
- List item 2

```python
code block
```

> Quote block

# Chapter 2

More content.
"""
    
    chapters = split_chapters_auto(text)
    
    # Check that markdown is preserved
    assert "## Section 1.1" in chapters[0].content
    assert "**bold**" in chapters[0].content
    assert "*italic*" in chapters[0].content
    assert "- List item 1" in chapters[0].content
    assert "```python" in chapters[0].content
    assert "> Quote block" in chapters[0].content


if __name__ == "__main__":
    test_split_chapters_auto_basic()
    test_split_chapters_auto_special_sections()
    test_split_chapters_auto_acknowledgments()
    test_split_chapters_auto_notes()
    test_split_chapters_auto_multiple_appendices()
    test_split_chapters_auto_no_boundaries()
    test_split_chapters_auto_line_numbers()
    test_split_chapters_auto_content_extraction()
    test_split_chapters_auto_mixed_special_sections()
    test_split_chapters_auto_case_insensitive_detection()
    test_chapter_dataclass()
    test_split_chapters_auto_preserves_markdown()
    print("All tests passed!")
