# Chapter Rules Format

This document describes the format for `chapter-rules.json`, which is used for manual chapter splitting in the book translation pipeline.

## Overview

Manual chapter splitting allows you to define custom chapter boundaries using regular expression patterns. This is useful when:

- Automatic chapter detection fails or produces incorrect results
- Your book has non-standard chapter formatting
- You need precise control over chapter boundaries
- You want to split chapters at specific markers or patterns

## File Format

The `chapter-rules.json` file must be a valid JSON file with the following structure:

```json
{
  "chapters": [
    {
      "id": "chapter_identifier",
      "title": "Chapter Title",
      "start_pattern": "regex_pattern",
      "end_pattern": "optional_regex_pattern"
    }
  ]
}
```

## Field Descriptions

### Required Fields

- **`chapters`** (array): Array of chapter rule objects. Must contain at least one chapter.

For each chapter rule object:

- **`id`** (string): Unique identifier for the chapter. Used as the filename (e.g., `01_chapter.md`).
  - Can be any valid filename (without extension)
  - Common conventions: `00_foreword`, `01_chapter`, `15_appendix`, `19_notes`
  - Must be unique within the rules file

- **`title`** (string): Human-readable chapter title.
  - Used in metadata and table of contents
  - Can contain any characters
  - Example: `"Chapter 1: Introduction"`

- **`start_pattern`** (string): Regular expression pattern to match the start of the chapter.
  - Matched using Python's `re.search()` with `re.MULTILINE` flag
  - Pattern is matched against the entire normalized text
  - Use `^` to match start of line
  - Example: `"^# Chapter 1"` matches a level-1 heading

### Optional Fields

- **`end_pattern`** (string or null): Regular expression pattern to match the end of the chapter.
  - If provided, the chapter ends where this pattern is found
  - If omitted or null, the chapter extends to the start of the next chapter (or end of text for the last chapter)
  - The matched text is NOT included in the chapter content
  - Example: `"^--- END CHAPTER ---"` matches a custom end marker

## Pattern Matching Rules

1. **Patterns are regular expressions**: Use standard Python regex syntax
2. **Multiline mode**: The `^` and `$` anchors match line boundaries
3. **Case-sensitive**: Patterns are case-sensitive by default
4. **First match wins**: Only the first occurrence of each pattern is used
5. **Sequential processing**: Chapters are processed in the order defined in the rules file

## Examples

### Example 1: Basic Chapter Splitting

Split chapters based on level-1 headings:

```json
{
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
```

### Example 2: Using End Patterns

Define explicit chapter boundaries:

```json
{
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
    }
  ]
}
```

### Example 3: Complex Patterns

Use regex features for flexible matching:

```json
{
  "chapters": [
    {
      "id": "01_part",
      "title": "Part I: Introduction",
      "start_pattern": "^PART I:.*$"
    },
    {
      "id": "02_part",
      "title": "Part II: Methodology",
      "start_pattern": "^PART II:.*$"
    },
    {
      "id": "03_part",
      "title": "Part III: Conclusion",
      "start_pattern": "^PART III:.*$"
    }
  ]
}
```

### Example 4: Custom Chapter IDs

Use any naming convention you prefer:

```json
{
  "chapters": [
    {
      "id": "intro",
      "title": "Introduction",
      "start_pattern": "^# Introduction"
    },
    {
      "id": "main_content",
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
```

## Usage

To use manual chapter splitting:

```bash
python3 -m book_pipeline.split_chapters \
  --project-dir projects/my-book \
  --mode manual \
  --rules-file chapter-rules.json
```

## Error Handling

The system will report errors for:

- **Missing file**: Rules file doesn't exist
- **Invalid JSON**: File is not valid JSON
- **Missing required fields**: Chapter rule missing `id`, `title`, or `start_pattern`
- **Invalid regex**: Pattern is not a valid regular expression
- **Pattern not found**: Pattern doesn't match any text in the source
- **Empty rules**: No chapters defined in the rules file

## Tips and Best Practices

1. **Test patterns first**: Use a regex tester to verify your patterns match correctly
2. **Start simple**: Begin with basic patterns and add complexity as needed
3. **Use anchors**: Start patterns with `^` to match line beginnings
4. **Escape special characters**: Remember to escape regex special characters: `( ) [ ] { } + * ? ^ $ | . \`
5. **Check line endings**: Ensure your patterns account for different line ending styles
6. **Validate incrementally**: Test with a few chapters first, then add more
7. **Keep IDs consistent**: Use a consistent naming convention for chapter IDs
8. **Document patterns**: Add comments in a separate file explaining complex patterns

## Common Patterns

### Match level-1 heading
```
"^# Chapter \\d+"
```

### Match numbered sections
```
"^\\d+\\. "
```

### Match part markers
```
"^PART [IVX]+:"
```

### Match custom markers
```
"^=== Chapter Start ==="
```

### Match case-insensitive
```
"^(?i)chapter \\d+"
```

## Troubleshooting

### Pattern doesn't match
- Check that the pattern exists in the normalized text
- Verify regex syntax is correct
- Ensure line endings are handled properly
- Try simplifying the pattern

### Wrong content extracted
- Check that patterns are in the correct order
- Verify end_pattern is matching the right location
- Review the normalized text to understand its structure

### Chapters overlap
- Ensure patterns are mutually exclusive
- Check that end_pattern comes before next start_pattern
- Verify chapter order in rules file

## See Also

- `chapter-rules.example.json` - Example rules file
- `book_pipeline/split_chapters.py` - Implementation
- `book_pipeline/test_split_chapters_manual.py` - Test suite
