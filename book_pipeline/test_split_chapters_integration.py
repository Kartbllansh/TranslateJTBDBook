"""Integration tests for split_chapters module with real-world data.

This test suite validates task 3.2 with realistic book content.
"""

from book_pipeline.split_chapters import split_chapters_auto


def test_split_chapters_with_realistic_book_structure():
    """Test with a realistic book structure including all special sections."""
    text = """# Foreword

This is the foreword content with multiple paragraphs.

Some more foreword text here.

# Acknowledgments

Thanks to everyone who contributed.

# Chapter 1: Introduction

This is the first chapter with substantial content.

## Section 1.1

Subsection content here.

# Chapter 2: Background

Second chapter content.

# Chapter 3: Methods

Third chapter content.

# Appendix A: Data Tables

First appendix with tables.

# Appendix B: Additional Resources

Second appendix with resources.

# Notes

Endnotes and references.
"""
    
    chapters = split_chapters_auto(text)
    
    # Should have 8 chapters total
    assert len(chapters) == 8
    
    # Verify special sections have correct IDs
    assert chapters[0].id == "00_foreword"
    assert chapters[0].title == "Foreword"
    
    assert chapters[1].id == "00_acknowledgments"
    assert chapters[1].title == "Acknowledgments"
    
    # Regular chapters
    assert chapters[2].id == "01_chapter"
    assert chapters[2].title == "Chapter 1: Introduction"
    
    assert chapters[3].id == "02_chapter"
    assert chapters[3].title == "Chapter 2: Background"
    
    assert chapters[4].id == "03_chapter"
    assert chapters[4].title == "Chapter 3: Methods"
    
    # Appendices
    assert chapters[5].id == "16_appendix"
    assert chapters[5].title == "Appendix A: Data Tables"
    
    assert chapters[6].id == "17_appendix"
    assert chapters[6].title == "Appendix B: Additional Resources"
    
    # Notes
    assert chapters[7].id == "19_notes"
    assert chapters[7].title == "Notes"
    
    # Verify content includes subsections
    assert "## Section 1.1" in chapters[2].content
    assert "Subsection content" in chapters[2].content


def test_split_chapters_preserves_all_content():
    """Test that no content is lost during splitting."""
    text = """# Chapter 1

First chapter with some unique text: MARKER_1

# Chapter 2

Second chapter with unique text: MARKER_2

# Chapter 3

Third chapter with unique text: MARKER_3
"""
    
    chapters = split_chapters_auto(text)
    
    # Verify all markers are present in the appropriate chapters
    assert "MARKER_1" in chapters[0].content
    assert "MARKER_2" in chapters[1].content
    assert "MARKER_3" in chapters[2].content
    
    # Verify markers don't leak into other chapters
    assert "MARKER_2" not in chapters[0].content
    assert "MARKER_3" not in chapters[0].content
    assert "MARKER_1" not in chapters[1].content


def test_split_chapters_handles_empty_chapters():
    """Test handling of chapters with minimal content."""
    text = """# Chapter 1

# Chapter 2

Some content here.

# Chapter 3
"""
    
    chapters = split_chapters_auto(text)
    
    assert len(chapters) == 3
    
    # First chapter has only heading
    assert chapters[0].content.strip() == "# Chapter 1"
    
    # Second chapter has content
    assert "Some content here" in chapters[1].content
    
    # Third chapter has only heading
    assert chapters[2].content.strip() == "# Chapter 3"


if __name__ == "__main__":
    test_split_chapters_with_realistic_book_structure()
    test_split_chapters_preserves_all_content()
    test_split_chapters_handles_empty_chapters()
    print("All integration tests passed!")
