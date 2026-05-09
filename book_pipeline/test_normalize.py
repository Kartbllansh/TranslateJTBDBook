"""Unit tests for text normalization module."""

from __future__ import annotations

import pytest

from book_pipeline.normalize import (
    ChapterBoundary,
    NormalizationConfig,
    detect_chapter_boundaries,
    detect_headers_footers,
    generate_normalization_report,
    join_hyphenated_words,
    normalize_text,
    remove_page_numbers,
)


class TestRemovePageNumbers:
    """Test page number removal patterns."""
    
    def test_removes_page_n_format(self):
        text = "Content here\nPage 42\nMore content"
        result = remove_page_numbers(text)
        assert "Page 42" not in result
        assert "Content here" in result
        assert "More content" in result
    
    def test_removes_lowercase_page_n(self):
        text = "Content\npage 123\nMore"
        result = remove_page_numbers(text)
        assert "page 123" not in result
    
    def test_removes_n_pipe_format(self):
        text = "Text here\n42 |\nMore text"
        result = remove_page_numbers(text)
        assert "42 |" not in result
        assert "Text here" in result
    
    def test_removes_pipe_n_format(self):
        text = "Text\n| 99\nMore"
        result = remove_page_numbers(text)
        assert "| 99" not in result
    
    def test_removes_centered_page_numbers(self):
        text = "Content\n- 42 -\nMore"
        result = remove_page_numbers(text)
        assert "- 42 -" not in result
    
    def test_removes_standalone_numbers(self):
        text = "Content\n42\nMore content"
        result = remove_page_numbers(text)
        assert "\n42\n" not in result
    
    def test_preserves_numbers_in_content(self):
        text = "There are 42 reasons why this works"
        result = remove_page_numbers(text)
        assert "42" in result
    
    def test_preserves_empty_lines(self):
        text = "Line 1\n\nLine 2"
        result = remove_page_numbers(text)
        assert "\n\n" in result
    
    def test_handles_large_page_numbers(self):
        text = "Content\n9999\nMore"
        result = remove_page_numbers(text)
        assert "9999" not in result
    
    def test_preserves_five_digit_numbers(self):
        # Five-digit numbers are not page numbers
        text = "The year 12345 was significant\n12345\nMore text"
        result = remove_page_numbers(text)
        # The standalone 12345 should be preserved (5 digits)
        assert "12345" in result


class TestJoinHyphenatedWords:
    """Test hyphenated word joining."""
    
    def test_joins_hyphenated_line_break(self):
        text = "This is a long-\nword that was split."
        result = join_hyphenated_words(text)
        assert "longword" in result
        assert "long-\n" not in result
    
    def test_preserves_intentional_hyphens(self):
        text = "This is a well-known phrase"
        result = join_hyphenated_words(text)
        assert "well-known" in result
    
    def test_handles_multiple_splits(self):
        text = "First-\nword and second-\nword here"
        result = join_hyphenated_words(text)
        assert "Firstword" in result
        assert "secondword" in result
    
    def test_handles_whitespace_after_break(self):
        text = "Split-\n  word with spaces"
        result = join_hyphenated_words(text)
        assert "Splitword" in result
    
    def test_preserves_non_word_hyphens(self):
        text = "List item:\n- Item 1\n- Item 2"
        result = join_hyphenated_words(text)
        assert "- Item 1" in result
        assert "- Item 2" in result


class TestDetectHeadersFooters:
    """Test header and footer detection."""
    
    def test_detects_repeated_lines(self):
        text = "Header\nContent 1\nHeader\nContent 2\nHeader\nContent 3"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "Header" in patterns
    
    def test_ignores_single_occurrence(self):
        text = "Unique line\nContent\nOther content"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "Unique line" not in patterns
    
    def test_ignores_empty_lines(self):
        text = "\n\n\nContent\n\n\n"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "" not in patterns
    
    def test_ignores_very_long_lines(self):
        long_line = "x" * 150
        text = f"{long_line}\nContent\n{long_line}\nMore\n{long_line}"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert long_line not in patterns
    
    def test_ignores_markdown_headings(self):
        text = "# Chapter 1\nContent\n# Chapter 1\nMore\n# Chapter 1"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "# Chapter 1" not in patterns
    
    def test_detects_copyright_notices(self):
        text = "© 2024 Publisher\nContent\n© 2024 Publisher\nMore\n© 2024 Publisher"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "© 2024 Publisher" in patterns
    
    def test_custom_min_repetitions(self):
        text = "Header\nContent\nHeader\nMore"
        patterns = detect_headers_footers(text, min_repetitions=2)
        assert "Header" in patterns


class TestNormalizeText:
    """Test complete normalization pipeline."""
    
    def test_removes_page_numbers_when_enabled(self):
        config = NormalizationConfig(remove_page_numbers=True)
        text = "Content\nPage 42\nMore"
        result = normalize_text(text, config)
        assert "Page 42" not in result
    
    def test_skips_page_numbers_when_disabled(self):
        config = NormalizationConfig(remove_page_numbers=False)
        text = "Content\nPage 42\nMore"
        result = normalize_text(text, config)
        assert "Page 42" in result
    
    def test_joins_hyphens_when_enabled(self):
        config = NormalizationConfig(join_hyphenated_words=True)
        text = "Split-\nword here"
        result = normalize_text(text, config)
        assert "Splitword" in result
    
    def test_skips_hyphens_when_disabled(self):
        config = NormalizationConfig(join_hyphenated_words=False)
        text = "Split-\nword here"
        result = normalize_text(text, config)
        assert "Split-\nword" in result
    
    def test_removes_headers_when_enabled(self):
        config = NormalizationConfig(detect_headers_footers=True)
        text = "Header\nContent\nHeader\nMore\nHeader\nEnd"
        result = normalize_text(text, config)
        assert result.count("Header") == 0
    
    def test_skips_headers_when_disabled(self):
        config = NormalizationConfig(detect_headers_footers=False)
        text = "Header\nContent\nHeader\nMore\nHeader\nEnd"
        result = normalize_text(text, config)
        assert "Header" in result
    
    def test_cleans_excessive_blank_lines(self):
        config = NormalizationConfig()
        text = "Line 1\n\n\n\n\nLine 2"
        result = normalize_text(text, config)
        # Should reduce to max 3 newlines (2 blank lines)
        assert "\n\n\n\n" not in result
    
    def test_preserves_markdown_lists(self):
        config = NormalizationConfig()
        text = "- Item 1\n- Item 2\n- Item 3"
        result = normalize_text(text, config)
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result
    
    def test_preserves_markdown_code_blocks(self):
        config = NormalizationConfig()
        text = "```python\ncode here\n```"
        result = normalize_text(text, config)
        assert "```python" in result
        assert "code here" in result
    
    def test_full_pipeline_integration(self):
        config = NormalizationConfig()
        text = """Header Line
Content paragraph with hyphen-
ated word here.

Page 42

Header Line

More content.

Header Line"""
        
        result = normalize_text(text, config)
        
        # Should remove page numbers
        assert "Page 42" not in result
        
        # Should join hyphenated words
        assert "hyphenated" in result
        
        # Should remove repeated headers
        assert result.count("Header Line") == 0


class TestNormalizationConfig:
    """Test configuration dataclass."""
    
    def test_default_values(self):
        config = NormalizationConfig()
        assert config.remove_page_numbers is True
        assert config.join_hyphenated_words is True
        assert config.detect_headers_footers is True
        assert config.preserve_code_blocks is True
        assert config.preserve_lists is True
    
    def test_custom_values(self):
        config = NormalizationConfig(
            remove_page_numbers=False,
            join_hyphenated_words=False,
        )
        assert config.remove_page_numbers is False
        assert config.join_hyphenated_words is False
        assert config.detect_headers_footers is True  # Still default


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_text(self):
        config = NormalizationConfig()
        result = normalize_text("", config)
        assert result == ""
    
    def test_whitespace_only(self):
        config = NormalizationConfig()
        result = normalize_text("   \n\n   ", config)
        assert result.strip() == ""
    
    def test_no_normalization_needed(self):
        config = NormalizationConfig()
        text = "Clean paragraph with no artifacts."
        result = normalize_text(text, config)
        assert "Clean paragraph with no artifacts." in result
    
    def test_unicode_content(self):
        config = NormalizationConfig()
        text = "Текст на русском языке\nPage 42\nЕщё текст"
        result = normalize_text(text, config)
        assert "Текст на русском языке" in result
        assert "Ещё текст" in result
        assert "Page 42" not in result
    
    def test_special_characters_in_headers(self):
        text = "© Copyright 2024\nContent\n© Copyright 2024\nMore\n© Copyright 2024"
        patterns = detect_headers_footers(text, min_repetitions=3)
        assert "© Copyright 2024" in patterns
    
    def test_mixed_line_endings(self):
        # Test with different line ending styles
        config = NormalizationConfig()
        text = "Line 1\nLine 2\rLine 3\r\nLine 4"
        result = normalize_text(text, config)
        # Should handle gracefully
        assert "Line 1" in result


class TestDetectChapterBoundaries:
    """Test chapter boundary detection."""
    
    def test_detects_basic_chapter_heading(self):
        text = "# Chapter 1\n\nContent here"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].title == "Chapter 1"
        assert boundaries[0].line_number == 1
        assert boundaries[0].chapter_type == "chapter"
    
    def test_detects_multiple_chapters(self):
        text = "# Chapter 1\n\nContent\n\n# Chapter 2\n\nMore content"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 2
        assert boundaries[0].title == "Chapter 1"
        assert boundaries[1].title == "Chapter 2"
    
    def test_detects_foreword(self):
        text = "# Foreword\n\nIntroductory text"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "foreword"
        assert boundaries[0].title == "Foreword"
    
    def test_detects_preface_as_foreword(self):
        text = "# Preface\n\nPreface content"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "foreword"
    
    def test_detects_introduction_as_foreword(self):
        text = "# Introduction\n\nIntro content"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "foreword"
    
    def test_detects_acknowledgments(self):
        text = "# Acknowledgments\n\nThanks to everyone"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "acknowledgments"
    
    def test_detects_acknowledgements_british_spelling(self):
        text = "# Acknowledgements\n\nThanks"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "acknowledgments"
    
    def test_detects_thanks_as_acknowledgments(self):
        text = "# Thanks\n\nGratitude section"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "acknowledgments"
    
    def test_detects_appendix(self):
        text = "# Appendix A\n\nSupplementary material"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "appendix"
        assert boundaries[0].title == "Appendix A"
    
    def test_detects_appendix_with_colon(self):
        text = "# Appendix: Additional Resources\n\nResources here"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "appendix"
    
    def test_detects_appendices(self):
        text = "# Appendices\n\nMultiple appendices"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "appendix"
    
    def test_detects_notes(self):
        text = "# Notes\n\nEndnotes section"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "notes"
    
    def test_detects_endnotes(self):
        text = "# Endnotes\n\nNotes content"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "notes"
    
    def test_detects_references(self):
        text = "# References\n\nBibliography"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].chapter_type == "notes"
    
    def test_ignores_level_2_headings(self):
        text = "# Chapter 1\n\n## Section 1.1\n\nContent"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].title == "Chapter 1"
    
    def test_ignores_level_3_headings(self):
        text = "### Subsection\n\nContent"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 0
    
    def test_case_insensitive_detection(self):
        text = "# FOREWORD\n\nContent\n\n# acknowledgments\n\nMore"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 2
        assert boundaries[0].chapter_type == "foreword"
        assert boundaries[1].chapter_type == "acknowledgments"
    
    def test_preserves_heading_text(self):
        text = "# Chapter 1: The Beginning\n\nContent"
        boundaries = detect_chapter_boundaries(text)
        assert boundaries[0].heading_text == "# Chapter 1: The Beginning"
    
    def test_correct_line_numbers(self):
        text = "Some intro\n\n# Chapter 1\n\nContent\n\n# Chapter 2\n\nMore"
        boundaries = detect_chapter_boundaries(text)
        assert boundaries[0].line_number == 3
        assert boundaries[1].line_number == 7
    
    def test_empty_text(self):
        boundaries = detect_chapter_boundaries("")
        assert len(boundaries) == 0
    
    def test_no_headings(self):
        text = "Just plain text\nwith no headings\nat all"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 0
    
    def test_mixed_chapter_types(self):
        text = """# Foreword

Intro text

# Chapter 1

Content

# Chapter 2

More content

# Appendix A

Extra material

# Notes

References"""
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 5
        assert boundaries[0].chapter_type == "foreword"
        assert boundaries[1].chapter_type == "chapter"
        assert boundaries[2].chapter_type == "chapter"
        assert boundaries[3].chapter_type == "appendix"
        assert boundaries[4].chapter_type == "notes"
    
    def test_chapter_with_number_in_title(self):
        text = "# Chapter 1. Challenges, Hope, and Progress\n\nContent"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].title == "Chapter 1. Challenges, Hope, and Progress"
        assert boundaries[0].chapter_type == "chapter"
    
    def test_unicode_in_chapter_titles(self):
        text = "# Глава 1: Введение\n\nРусский текст"
        boundaries = detect_chapter_boundaries(text)
        assert len(boundaries) == 1
        assert boundaries[0].title == "Глава 1: Введение"


class TestGenerateNormalizationReport:
    """Test normalization report generation."""
    
    def test_report_includes_statistics(self):
        original = "Line 1\nLine 2\nLine 3"
        normalized = "Line 1\nLine 3"
        report = generate_normalization_report(original, normalized, [])
        
        assert "Statistics" in report
        assert "Original line count: 3" in report
        assert "Normalized line count: 2" in report
        assert "Lines removed: 1" in report
    
    def test_report_includes_detected_patterns(self):
        original = "Text"
        normalized = "Text"
        patterns = ["Header Line", "Footer Text"]
        report = generate_normalization_report(original, normalized, patterns)
        
        assert "Detected Headers/Footers" in report
        assert "`Header Line`" in report
        assert "`Footer Text`" in report
    
    def test_report_with_no_patterns(self):
        original = "Text"
        normalized = "Text"
        report = generate_normalization_report(original, normalized, [])
        
        assert "No repeated header/footer patterns detected" in report
    
    def test_report_includes_chapter_boundaries(self):
        original = "Text"
        normalized = "Text"
        boundaries = [
            ChapterBoundary(1, "Chapter 1", "# Chapter 1", "chapter"),
            ChapterBoundary(10, "Chapter 2", "# Chapter 2", "chapter"),
        ]
        report = generate_normalization_report(original, normalized, [], boundaries)
        
        assert "Detected Chapter Boundaries" in report
        assert "Found 2 potential chapter boundaries" in report
        assert "Line 1" in report
        assert "Chapter 1" in report
        assert "Line 10" in report
        assert "Chapter 2" in report
    
    def test_report_includes_chapter_type_summary(self):
        original = "Text"
        normalized = "Text"
        boundaries = [
            ChapterBoundary(1, "Foreword", "# Foreword", "foreword"),
            ChapterBoundary(5, "Chapter 1", "# Chapter 1", "chapter"),
            ChapterBoundary(10, "Chapter 2", "# Chapter 2", "chapter"),
            ChapterBoundary(15, "Appendix", "# Appendix", "appendix"),
        ]
        report = generate_normalization_report(original, normalized, [], boundaries)
        
        assert "Chapter Type Summary" in report
        assert "Foreword: 1" in report
        assert "Chapter: 2" in report
        assert "Appendix: 1" in report
    
    def test_report_with_no_chapter_boundaries(self):
        original = "Text"
        normalized = "Text"
        boundaries = []
        report = generate_normalization_report(original, normalized, [], boundaries)
        
        assert "No level-1 headings detected" in report
        assert "manual chapter splitting" in report
    
    def test_report_includes_next_steps(self):
        original = "Text"
        normalized = "Text"
        report = generate_normalization_report(original, normalized, [])
        
        assert "Next Steps" in report
        assert "split_chapters" in report
    
    def test_report_without_chapter_boundaries_parameter(self):
        # Test backward compatibility when chapter_boundaries is None
        original = "Text"
        normalized = "Text"
        report = generate_normalization_report(original, normalized, [], None)
        
        # Should not include chapter boundaries section
        assert "Detected Chapter Boundaries" not in report
        assert "Statistics" in report
