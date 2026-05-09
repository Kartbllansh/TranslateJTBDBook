"""Tests for manual chapter splitting functionality.

This test suite validates task 3.3: Implement manual chapter splitting
Requirements: 4.2, 4.3
"""

import json
import tempfile
from pathlib import Path

import pytest

from book_pipeline.split_chapters import split_chapters_manual, Chapter, ChapterRule


def test_split_chapters_manual_basic():
    """Test basic manual chapter splitting with start patterns only.
    
    Validates:
    - Requirement 4.2: Support manual chapter splitting via rules file
    - Requirement 4.3: Read chapter definitions from JSON configuration
    """
    text = """# Foreword

This is the foreword content.

# Chapter 1: Introduction

This is chapter 1 content.

# Chapter 2: Background

This is chapter 2 content.
"""
    
    rules = {
        "chapters": [
            {
                "id": "00_foreword",
                "title": "Foreword",
                "start_pattern": "^# Foreword"
            },
            {
                "id": "01_chapter",
                "title": "Chapter 1: Introduction",
                "start_pattern": "^# Chapter 1"
            },
            {
                "id": "02_chapter",
                "title": "Chapter 2: Background",
                "start_pattern": "^# Chapter 2"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        assert len(chapters) == 3
        
        # Check first chapter
        assert chapters[0].id == "00_foreword"
        assert chapters[0].title == "Foreword"
        assert "foreword content" in chapters[0].content
        assert "Chapter 1" not in chapters[0].content
        
        # Check second chapter
        assert chapters[1].id == "01_chapter"
        assert chapters[1].title == "Chapter 1: Introduction"
        assert "chapter 1 content" in chapters[1].content
        assert "Chapter 2" not in chapters[1].content
        
        # Check third chapter
        assert chapters[2].id == "02_chapter"
        assert chapters[2].title == "Chapter 2: Background"
        assert "chapter 2 content" in chapters[2].content
    finally:
        rules_file.unlink()


def test_split_chapters_manual_with_end_patterns():
    """Test manual splitting with explicit end patterns.
    
    Validates:
    - Requirement 4.2: Match end_pattern regex to find chapter ends
    - Requirement 4.3: Support optional end_pattern in rules
    """
    text = """# Chapter 1

Content of chapter 1.

More content.

--- END CHAPTER 1 ---

# Chapter 2

Content of chapter 2.

--- END CHAPTER 2 ---

# Appendix

Appendix content.
"""
    
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "title": "Chapter 1",
                "start_pattern": "^# Chapter 1",
                "end_pattern": "^--- END CHAPTER 1 ---"
            },
            {
                "id": "02_chapter",
                "title": "Chapter 2",
                "start_pattern": "^# Chapter 2",
                "end_pattern": "^--- END CHAPTER 2 ---"
            },
            {
                "id": "15_appendix",
                "title": "Appendix",
                "start_pattern": "^# Appendix"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        assert len(chapters) == 3
        
        # Chapter 1 should end at the END marker, not include it
        assert "--- END CHAPTER 1 ---" not in chapters[0].content
        assert "Chapter 2" not in chapters[0].content
        
        # Chapter 2 should end at its END marker
        assert "--- END CHAPTER 2 ---" not in chapters[1].content
        assert "Appendix" not in chapters[1].content
        
        # Appendix extends to end of text
        assert "Appendix content" in chapters[2].content
    finally:
        rules_file.unlink()


def test_split_chapters_manual_line_numbers():
    """Test that line numbers are correctly calculated.
    
    Validates:
    - Requirement 4.2: Track start and end line numbers for each chapter
    """
    text = """# Chapter 1

Content line 1.
Content line 2.

# Chapter 2

Content line 3.
Content line 4.
"""
    
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "title": "Chapter 1",
                "start_pattern": "^# Chapter 1"
            },
            {
                "id": "02_chapter",
                "title": "Chapter 2",
                "start_pattern": "^# Chapter 2"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        # First chapter starts at line 1
        assert chapters[0].start_line == 1
        # First chapter ends before second chapter
        assert chapters[0].end_line < chapters[1].start_line
        
        # Second chapter starts at line 6
        assert chapters[1].start_line == 6
        # Second chapter ends at last line
        assert chapters[1].end_line == len(text.split("\n"))
    finally:
        rules_file.unlink()


def test_split_chapters_manual_regex_patterns():
    """Test that regex patterns work correctly.
    
    Validates:
    - Requirement 4.2: Match patterns using regex
    - Support for complex regex patterns
    """
    text = """PART I: INTRODUCTION

Chapter content here.

PART II: METHODOLOGY

More content here.

PART III: CONCLUSION

Final content.
"""
    
    rules = {
        "chapters": [
            {
                "id": "01_part",
                "title": "Part I: Introduction",
                "start_pattern": r"^PART I:.*$"
            },
            {
                "id": "02_part",
                "title": "Part II: Methodology",
                "start_pattern": r"^PART II:.*$"
            },
            {
                "id": "03_part",
                "title": "Part III: Conclusion",
                "start_pattern": r"^PART III:.*$"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        assert len(chapters) == 3
        assert chapters[0].id == "01_part"
        assert chapters[1].id == "02_part"
        assert chapters[2].id == "03_part"
        
        assert "Chapter content" in chapters[0].content
        assert "More content" in chapters[1].content
        assert "Final content" in chapters[2].content
    finally:
        rules_file.unlink()


def test_split_chapters_manual_missing_file():
    """Test error handling when rules file doesn't exist.
    
    Validates:
    - Requirement 4.3: Raise FileNotFoundError if rules file missing
    """
    text = "# Chapter 1\n\nContent."
    rules_file = Path("/nonexistent/chapter-rules.json")
    
    with pytest.raises(FileNotFoundError) as exc_info:
        split_chapters_manual(text, rules_file)
    
    assert "not found" in str(exc_info.value)


def test_split_chapters_manual_invalid_json():
    """Test error handling for invalid JSON format.
    
    Validates:
    - Requirement 4.3: Raise ValueError for invalid JSON
    """
    text = "# Chapter 1\n\nContent."
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "Failed to parse" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_missing_chapters_key():
    """Test error handling when 'chapters' key is missing.
    
    Validates:
    - Requirement 4.3: Validate rules format
    """
    text = "# Chapter 1\n\nContent."
    
    rules = {
        "invalid_key": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "Invalid chapter rules format" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_missing_required_fields():
    """Test error handling when required fields are missing.
    
    Validates:
    - Requirement 4.3: Validate required fields (id, title, start_pattern)
    """
    text = "# Chapter 1\n\nContent."
    
    # Missing 'title' field
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "start_pattern": "^# Chapter 1"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "Required fields" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_pattern_not_found():
    """Test error handling when pattern doesn't match text.
    
    Validates:
    - Requirement 4.2: Raise ValueError if pattern not found
    """
    text = "# Chapter 1\n\nContent."
    
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "title": "Chapter 1",
                "start_pattern": "^# Nonexistent Chapter"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "Start pattern not found" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_invalid_regex():
    """Test error handling for invalid regex patterns.
    
    Validates:
    - Requirement 4.2: Raise ValueError for invalid regex
    """
    text = "# Chapter 1\n\nContent."
    
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "title": "Chapter 1",
                "start_pattern": "^# Chapter [invalid"  # Invalid regex
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "Invalid regex pattern" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_empty_rules():
    """Test error handling for empty chapter rules.
    
    Validates:
    - Requirement 4.3: Validate that at least one chapter is defined
    """
    text = "# Chapter 1\n\nContent."
    
    rules = {
        "chapters": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            split_chapters_manual(text, rules_file)
        
        assert "No chapter rules defined" in str(exc_info.value)
    finally:
        rules_file.unlink()


def test_split_chapters_manual_preserves_markdown():
    """Test that markdown formatting is preserved in chapter content.
    
    Validates:
    - Requirement 4.2: Preserve markdown structure in extracted content
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
    
    rules = {
        "chapters": [
            {
                "id": "01_chapter",
                "title": "Chapter 1",
                "start_pattern": "^# Chapter 1"
            },
            {
                "id": "02_chapter",
                "title": "Chapter 2",
                "start_pattern": "^# Chapter 2"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        # Check that markdown is preserved
        assert "## Section 1.1" in chapters[0].content
        assert "**bold**" in chapters[0].content
        assert "*italic*" in chapters[0].content
        assert "- List item 1" in chapters[0].content
        assert "```python" in chapters[0].content
        assert "> Quote block" in chapters[0].content
    finally:
        rules_file.unlink()


def test_split_chapters_manual_custom_ids():
    """Test that custom chapter IDs are preserved.
    
    Validates:
    - Requirement 4.2: Use chapter IDs from rules file
    """
    text = """# Introduction

Intro content.

# Main Content

Main content.

# Conclusion

Conclusion content.
"""
    
    rules = {
        "chapters": [
            {
                "id": "intro",
                "title": "Introduction",
                "start_pattern": "^# Introduction"
            },
            {
                "id": "main_section",
                "title": "Main Content",
                "start_pattern": "^# Main Content"
            },
            {
                "id": "conclusion",
                "title": "Conclusion",
                "start_pattern": "^# Conclusion"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rules, f)
        rules_file = Path(f.name)
    
    try:
        chapters = split_chapters_manual(text, rules_file)
        
        assert len(chapters) == 3
        assert chapters[0].id == "intro"
        assert chapters[1].id == "main_section"
        assert chapters[2].id == "conclusion"
    finally:
        rules_file.unlink()


def test_chapter_rule_dataclass():
    """Test ChapterRule dataclass creation and attributes.
    
    Validates:
    - ChapterRule dataclass has all required fields
    """
    rule = ChapterRule(
        id="01_chapter",
        title="Test Chapter",
        start_pattern="^# Test",
        end_pattern="^# End"
    )
    
    assert rule.id == "01_chapter"
    assert rule.title == "Test Chapter"
    assert rule.start_pattern == "^# Test"
    assert rule.end_pattern == "^# End"
    
    # Test with optional end_pattern as None
    rule2 = ChapterRule(
        id="02_chapter",
        title="Another Chapter",
        start_pattern="^# Another"
    )
    
    assert rule2.end_pattern is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
