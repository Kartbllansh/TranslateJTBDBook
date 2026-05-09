# Implementation Plan: Book Translation Pipeline Automation

## Overview

This implementation plan breaks down the book translation pipeline into actionable coding tasks. The system is a Python-based CLI toolchain that transforms PDF books from English to Russian through a 9-stage pipeline: init → extract → normalize → split → chunk → translate → assemble → review → publish.

**Existing Components:**
- ✅ `book_pipeline/common.py` - Core utilities (JSON I/O, slugify, pipeline state management)
- ✅ `book_pipeline/init_project.py` - Project initialization (complete)
- ✅ `book_pipeline/extract_opendataloader.py` - PDF extraction wrapper (complete)
- ✅ `book_pipeline/project_status.py` - Status reporting (complete)

**Implementation Strategy:**
1. Complete foundation utilities and enhance common module
2. Implement extraction pipeline stages (normalize, split, chunk)
3. Implement translation pipeline (translate, assemble)
4. Implement quality and publishing stages (review, publish)
5. Add integration and testing

## Tasks

### 1. Foundation: Enhance Common Utilities

- [x] 1.1 Add markdown parsing utilities to common.py
  - Implement `parse_markdown_blocks()` to identify block types (heading, paragraph, list, code, quote)
  - Implement `split_list_items()` for list chunking
  - Add block type enumeration (HEADING, PARAGRAPH, LIST, CODE_BLOCK, QUOTE)
  - _Requirements: 5.2, 5.3, 5.4_

- [x] 1.2 Add glossary parsing utilities to common.py
  - Implement `parse_glossary_table()` to extract English/Russian/Notes from markdown tables
  - Handle multi-line usage notes in table cells
  - Return structured glossary entries as list of dicts
  - _Requirements: 6.1, 6.2, 21.1, 21.2_

- [x] 1.3 Add metadata update utilities to common.py
  - Implement `update_chapter_metadata()` to modify chapter entries in metadata.json
  - Implement `get_chapter_by_id()` to retrieve chapter metadata
  - Implement `calculate_word_count()` for chapter text
  - _Requirements: 22.1, 22.2, 22.3_

- [x]* 1.4 Write unit tests for common utilities
  - Test `slugify()` with Unicode, special characters, empty strings
  - Test JSON round-trip property: parse(serialize(data)) == data
  - Test markdown block parsing with nested structures
  - Test glossary parsing with edge cases (empty cells, special characters)
  - _Requirements: 17.5_

### 2. Stage 3: Text Normalization

- [x] 2.1 Create book_pipeline/normalize.py module
  - Implement CLI argument parsing (--project-dir, --force)
  - Implement `main()` entry point following existing module patterns
  - Read from `source/extracted.md`, write to `source/normalized.md`
  - Update pipeline-state.json on completion
  - _Requirements: 3.1, 3.6, 3.8_

- [x] 2.2 Implement normalization algorithms
  - Implement `detect_headers_footers()` to find repeated patterns
  - Implement `remove_page_numbers()` with regex patterns (Page N, N |, etc.)
  - Implement `join_hyphenated_words()` to merge words split across lines
  - Implement `preserve_markdown_structure()` to protect lists, quotes, code blocks
  - Create `NormalizationConfig` dataclass with configuration options
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 2.3 Implement chapter boundary detection
  - Scan for level-1 headings (`# Chapter N`)
  - Detect special sections (Foreword, Acknowledgments, Appendix, Notes)
  - Generate suggestions in `review/normalization-report.md`
  - _Requirements: 3.5, 3.7_

- [x]* 2.4 Write unit tests for normalization
  - Test page number removal with various formats
  - Test hyphenation joining (preserve intentional hyphens)
  - Test markdown structure preservation
  - Test header/footer detection with repeated patterns
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

### 3. Stage 4: Chapter Splitting

- [x] 3.1 Create book_pipeline/split_chapters.py module
  - Implement CLI with --project-dir, --mode (auto|manual), --rules-file
  - Implement `main()` entry point
  - Read from `source/normalized.md`
  - Write chapters to `chapters/<chapter-id>.md`
  - Update metadata.json with chapter list
  - Update pipeline-state.json on completion
  - _Requirements: 4.1, 4.2, 4.4, 4.8_

- [x] 3.2 Implement automatic chapter detection
  - Scan for level-1 headings as chapter boundaries
  - Assign sequential IDs (00_foreword, 01_chapter, 02_chapter, etc.)
  - Extract chapter titles from heading text
  - Handle special sections (foreword, appendix, notes)
  - _Requirements: 4.1, 4.6, 4.7_

- [x] 3.3 Implement manual chapter splitting
  - Define `ChapterRules` schema (JSON with start/end patterns)
  - Read rules from `chapter-rules.json` if provided
  - Match patterns against normalized text
  - Split at specified boundaries
  - _Requirements: 4.2, 4.3_

- [x] 3.4 Implement Chapter dataclass and metadata generation
  - Create `Chapter` dataclass with id, title, content, start_line, end_line
  - Calculate word count for each chapter
  - Update metadata.json with chapter entries
  - Log ambiguous boundaries to `review/notes.md`
  - _Requirements: 4.5, 4.6, 4.9, 22.3_

- [x]* 3.5 Write unit tests for chapter splitting
  - Test auto-detection with various heading formats
  - Test manual splitting with pattern matching
  - Test special section detection (foreword, appendix)
  - Test sequential ID assignment
  - _Requirements: 4.1, 4.2, 4.6_

### 4. Stage 5: Chunking

- [x] 4.1 Create book_pipeline/chunk.py module
  - Implement CLI with --project-dir, --max-chars (default 6000), --force
  - Implement `main()` entry point
  - Read chapters from `chapters/` directory
  - Write chunks to `chunks/<chapter-id>/<sequence>.source.md`
  - Create empty `.ru.md` files for translations
  - Create `.meta.json` files with chunk metadata
  - Update pipeline-state.json on completion
  - _Requirements: 5.1, 5.5, 5.6, 5.7, 5.8_

- [x] 4.2 Implement smart chunking algorithm
  - Parse markdown into blocks using common.py utilities
  - Never split heading from following paragraph
  - Keep lists together unless they exceed max_chars
  - Never split code blocks or block quotes
  - Split large lists at item boundaries
  - Create `Chunk` dataclass with id, chapter_id, sequence, content, char_count, status
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.7_

- [x] 4.3 Implement chunk metadata management
  - Generate chunk IDs: `<chapter-id>_<sequence>`
  - Record metadata: chapter_id, sequence, char_count, status, created_at
  - Write metadata to `<chunk-id>.meta.json`
  - Update chapter metadata with chunk_count
  - _Requirements: 5.7, 22.4_

- [x]* 4.4 Write unit tests for chunking
  - Test heading preservation (never split from paragraph)
  - Test list handling (keep together, split large lists)
  - Test code block preservation
  - Test chunk size limits
  - Test boundary conditions (empty chapters, single paragraph)
  - _Requirements: 5.2, 5.3, 5.4_

### 5. Stage 6: Translation

- [x] 5.1 Create book_pipeline/translate.py module
  - Implement CLI with --project-dir, --mode (quick|normal|refined), --force, --retry-failed
  - Implement `main()` entry point
  - Read chunks from `chunks/` directory
  - Read glossary from root TERMINOLOGY.md and project glossary.md
  - Write translations to `<chunk-id>.ru.md`
  - Update chunk metadata with translation status
  - Update pipeline-state.json on completion
  - _Requirements: 7.1, 7.2, 7.4, 7.5, 7.8, 7.9_

- [x] 5.2 Implement glossary loading and merging
  - Load root TERMINOLOGY.md using common.py utilities
  - Load project-specific glossary.md if exists
  - Merge glossaries (project-specific overrides root)
  - Log conflicts to `review/terminology-report.md`
  - Create `Glossary` class to hold terminology mappings
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 5.3 Implement translation context extraction
  - Create `TranslationContext` dataclass with previous/next chunk summaries and chapter title
  - Extract last paragraph of previous chunk (max 500 chars)
  - Extract first paragraph of next chunk (max 500 chars)
  - Skip context for first/last chunks of chapter
  - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6_

- [x] 5.4 Implement translation prompt construction
  - Create prompt template with glossary, context, and source text
  - Include instructions for terminology consistency and markdown preservation
  - Mark context as "for reference only, do not translate"
  - Support three modes: quick (direct), normal (with terminology), refined (with review)
  - _Requirements: 7.2, 7.3, 7.8, 25.3_

- [x] 5.5 Implement LLM integration (pluggable)
  - Create abstract `LLMService` interface
  - Implement OpenAI adapter (read API key from environment)
  - Implement Anthropic adapter (read API key from environment)
  - Support local model endpoints
  - Handle API errors gracefully
  - _Requirements: 7.7_

- [x] 5.6 Implement translation execution and error handling
  - Skip chunks with status "translated" unless --force flag set
  - Preserve manual edits (check file modification time)
  - Set chunk status to "error" on failure
  - Log errors to `review/translation-errors.md`
  - Update chapter status when all chunks translated
  - Support --retry-failed to retry error chunks
  - _Requirements: 7.6, 7.7, 7.9, 7.10, 14.1, 14.3_

- [x]* 5.7 Write unit tests for translation
  - Test glossary loading and merging
  - Test context extraction (first/last/middle chunks)
  - Test prompt construction with various inputs
  - Test error handling and retry logic
  - Mock LLM responses for deterministic testing
  - _Requirements: 6.1, 6.2, 25.1, 25.2_

### 6. Stage 7: Assembly

- [x] 6.1 Create book_pipeline/assemble.py module
  - Implement CLI with --project-dir, --force
  - Implement `main()` entry point
  - Read translated chunks from `chunks/` directory
  - Write assembled chapters to `translated/<chapter-id>.md`
  - Update metadata.json chapter status
  - Update pipeline-state.json on completion
  - _Requirements: 8.1, 8.2, 8.6, 8.7_

- [x] 6.2 Implement assembly algorithm
  - Create `AssemblyResult` dataclass with success, output_path, missing_chunks, warnings
  - Read all chunk metadata for each chapter
  - Sort chunks by sequence number
  - Verify no gaps in sequence
  - Concatenate translated content preserving markdown
  - Generate report of missing chunks in `review/missing-sections.md`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 6.3 Implement completeness checking
  - Check for chunks with status "error" or "pending"
  - Mark chapters as incomplete if any chunks missing
  - Update chapter status to "translated" only if complete
  - _Requirements: 8.4, 8.5, 8.6_

- [x]* 6.4 Write unit tests for assembly
  - Test chunk concatenation with proper ordering
  - Test gap detection in sequence numbers
  - Test markdown preservation
  - Test incomplete chapter handling
  - _Requirements: 8.1, 8.2, 8.3_

### 7. Stage 8: Review and Quality Checks

- [x] 7.1 Create book_pipeline/review.py module
  - Implement CLI with --project-dir
  - Implement `main()` entry point
  - Run all quality checks
  - Generate reports in `review/` directory
  - Update pipeline-state.json on completion
  - Do NOT modify translation files
  - _Requirements: 9.1, 9.8, 9.9_

- [x] 7.2 Implement structural checks
  - Create `ReviewReport` dataclass with structural_issues, terminology_issues, completeness_issues, quality_score
  - Verify all chapters in metadata have translated files
  - Check file sizes are within expected ranges (not empty, not too large)
  - Verify markdown structure preserved (heading levels, lists, quotes)
  - _Requirements: 9.1, 9.2, 9.5_

- [x] 7.3 Implement terminology checks
  - Load glossary using common.py utilities
  - Check glossary terms used consistently across chapters
  - Detect English text in Russian translations (excluding proper nouns)
  - Generate `review/terminology-report.md` with term usage statistics
  - _Requirements: 9.3, 9.6_

- [x] 7.4 Implement completeness checks
  - Verify all chunks translated
  - Check for missing sections
  - Verify image references preserved
  - Generate `review/quality-report.md` with all findings
  - _Requirements: 9.4, 9.7_

- [x]* 7.5 Write unit tests for review
  - Test structural validation with various markdown
  - Test terminology consistency checking
  - Test completeness verification
  - Test report generation
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

### 8. Stage 9: Publishing

- [x] 8.1 Create book_pipeline/publish.py module
  - Implement CLI with --project-dir, --standalone (default True)
  - Implement `main()` entry point
  - Read metadata.json and all translated chapters
  - Copy reader template to `dist/reader/`
  - Generate standalone HTML to `dist/<book-id>-ru.html`
  - Update pipeline-state.json on completion
  - _Requirements: 10.1, 10.2, 10.3, 10.6, 10.13_

- [x] 8.2 Implement table of contents generation
  - Extract chapter titles from metadata.json
  - Generate TOC structure for reader navigation
  - Inject TOC into reader HTML
  - _Requirements: 10.2, 10.10_

- [x] 8.3 Implement reader template injection
  - Read reader template from `reader/` directory
  - Inject translated chapters into HTML
  - Inject metadata (title, author, translator contact)
  - Copy to `dist/reader/` directory
  - _Requirements: 10.3, 10.4, 10.5_

- [x] 8.4 Implement standalone HTML generation
  - Create `PublishResult` dataclass with output paths
  - Inline all CSS from styles.css
  - Inline all JavaScript from app.js
  - Embed chapter content as JSON (escape special characters)
  - Convert cover image to base64 data URI
  - Escape `<` as `\u003c` to prevent HTML injection
  - Write single HTML file under 10MB
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8_

- [x] 8.5 Implement reader features verification
  - Verify search functionality works with embedded content
  - Verify TOC navigation works
  - Verify theme switching works
  - Verify font size adjustment works
  - Test standalone HTML opens without network
  - _Requirements: 10.7, 10.8, 10.9, 10.10, 10.11, 10.12_

- [x]* 8.6 Write unit tests for publishing
  - Test TOC generation from metadata
  - Test CSS/JS inlining
  - Test JSON escaping for special characters
  - Test base64 image embedding
  - Test file size limits
  - _Requirements: 20.5, 20.6, 20.7_

### 9. Integration and CLI Enhancements

- [x] 9.1 Add multi-project listing command
  - Create `book_pipeline/list_projects.py` module
  - List all projects in projects/ directory
  - Display project ID, title, current stage
  - _Requirements: 12.3_

- [x] 9.2 Enhance error messages across all modules
  - Add actionable remediation steps to all error messages
  - Include expected file paths in missing file errors
  - Validate prerequisites before operations
  - Write detailed logs to review/ directory
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

- [x] 9.3 Add configuration validation
  - Validate chunk size limits (positive integer)
  - Validate translation modes (quick|normal|refined)
  - Validate language codes (2-letter ISO codes)
  - Reject invalid settings with clear messages
  - _Requirements: 16.6_

- [x] 9.4 Implement backup mechanism for metadata files
  - Create backups before modifying metadata.json
  - Create backups before modifying pipeline-state.json
  - Store backups in `review/backups/` directory
  - _Requirements: 19.5_

- [x] 9.5 Add disk space checking
  - Check available disk space before large operations
  - Fail before modifying files if insufficient space
  - _Requirements: 19.6_

### 10. Checkpoint - Core Pipeline Complete

- [x] 10.1 Ensure all pipeline stages are implemented
  - Verify all 9 stages have working modules
  - Verify pipeline-state.json updates correctly
  - Verify stage transitions follow correct order
  - Ensure all tests pass, ask the user if questions arise.

### 11. Image Handling

- [x] 11.1 Implement image extraction support
  - Verify images saved to source/images/ during extraction
  - Preserve image filenames from opendataloader-pdf
  - Record image references in extracted JSON
  - _Requirements: 23.1, 23.2, 23.3_

- [x] 11.2 Implement image publishing
  - Copy images to dist/ directory during publishing
  - Embed images in standalone HTML as base64 data URIs
  - Preserve image references in markdown
  - _Requirements: 23.4, 23.5_

- [x]* 11.3 Write unit tests for image handling
  - Test image path resolution
  - Test base64 encoding
  - Test image reference preservation
  - _Requirements: 23.1, 23.4, 23.5_

### 12. Documentation and Examples

- [x] 12.1 Create comprehensive README for book_pipeline
  - Document installation steps
  - Document full pipeline workflow
  - Provide example commands for each stage
  - Document configuration options
  - _Requirements: 24.2_

- [x] 12.2 Create example project walkthrough
  - Document creating a project from sample PDF
  - Show expected outputs at each stage
  - Document common troubleshooting scenarios
  - _Requirements: 15.3_

- [x] 12.3 Document LLM integration
  - Document API key setup for OpenAI/Anthropic
  - Document local model configuration
  - Provide example .env file
  - _Requirements: 7.5_

### 13. Final Integration Testing

- [ ]* 13.1 Write end-to-end integration tests
  - Test full pipeline on sample PDF (5-10 pages)
  - Test resume after interruption
  - Test re-running stages with existing data
  - Test force flag behavior
  - Test multi-project isolation
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ]* 13.2 Create test fixtures
  - Create small sample PDF for testing
  - Create pre-extracted markdown samples
  - Create mock LLM responses
  - _Requirements: 13.1_

- [x] 13.3 Final checkpoint - Ensure all tests pass
  - Run all unit tests
  - Run all integration tests
  - Verify manual testing checklist complete
  - Ensure all tests pass, ask the user if questions arise.

### 14. Chat-Driven Agent Workflow

- [x] 14.1 Add chat translation queue command
  - Create `book_pipeline/chat_translate.py`
  - Implement `status`, `next`, and `save` subcommands
  - Generate prompt packets for translation inside chat
  - Save chat translations to chunk `.ru.md` files and update metadata

- [x] 14.2 Add stage orchestrator command
  - Create `book_pipeline/run_pipeline.py`
  - Run extraction, normalization, splitting, chunking, translation, assembly, review, and publish in order
  - Support `--translation-method chat|api|echo`
  - Pause at translation when chat chunks are pending

- [x] 14.3 Document chat-driven workflow
  - Create `docs/CHAT_TRANSLATION_WORKFLOW.md`
  - Document how to prepare PDF, generate next chat packet, save translated chunk, and resume publishing

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Implementation follows existing code patterns in book_pipeline/
- All modules follow CLI conventions: --help, --project-dir, --force
- Python 3.10+ is required for type hints and modern syntax
- External dependencies: opendataloader-pdf (Java 11+), LLM API access
