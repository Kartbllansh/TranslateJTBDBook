# Requirements Document

## Introduction

This document specifies requirements for automating the book translation pipeline system. The system transforms PDF books from English to Russian through extraction, normalization, translation, review, and publishing stages. The system must support multiple book projects, preserve manual edits, maintain terminology consistency, and produce both web-based and standalone HTML readers.

The system builds upon existing components: `opendataloader-pdf` for extraction, a project structure in `book_pipeline/`, terminology management in `TERMINOLOGY.md`, and a reader interface. The goal is to complete and integrate these components into a cohesive, repeatable pipeline.

## Glossary

- **Pipeline**: The complete workflow from PDF import to published reader
- **Project**: A single book translation workspace with its own directory structure
- **Book_Pipeline**: Python module containing pipeline commands
- **Opendataloader_PDF**: External tool for extracting structured data from PDF files
- **Chapter**: A logical division of the book (foreword, chapter, appendix, notes)
- **Chunk**: A subdivision of a chapter sized for LLM translation (typically 4000-6000 characters)
- **Source_Text**: Original English text extracted from PDF
- **Translated_Text**: Russian translation of source text
- **Glossary**: Terminology database mapping English terms to Russian translations
- **Metadata_File**: JSON file containing book information and chapter structure
- **Pipeline_State_File**: JSON file tracking progress through pipeline stages
- **Reader**: HTML-based interface for reading translated books
- **Standalone_HTML**: Single-file HTML containing complete book with embedded assets
- **Normalization**: Process of cleaning extracted text (removing headers, footers, fixing line breaks)
- **LLM**: Large Language Model used for translation
- **Round_Trip_Property**: Property where parsing then printing produces equivalent output

## Requirements

### Requirement 1: Project Initialization

**User Story:** As a translator, I want to create a new book project from a PDF file, so that I can organize all translation artifacts in a dedicated workspace.

#### Acceptance Criteria

1. WHEN a user provides a PDF file path, title, author, and book ID, THE Book_Pipeline SHALL create a project directory structure
2. THE Book_Pipeline SHALL copy the source PDF to `projects/<book-id>/input/book.pdf`
3. THE Book_Pipeline SHALL create a Metadata_File with book information, empty chapter list, and timestamps
4. THE Book_Pipeline SHALL create a Pipeline_State_File with all stages set to "pending" except "init" set to "done"
5. THE Book_Pipeline SHALL create empty subdirectories: input, source, source/images, chapters, chunks, translated, review, dist
6. THE Book_Pipeline SHALL create a project-specific glossary file referencing the root TERMINOLOGY.md
7. IF the project directory already exists and force flag is false, THEN THE Book_Pipeline SHALL return an error without modifying files
8. WHEN project creation completes successfully, THE Book_Pipeline SHALL print the next command to run

### Requirement 2: PDF Extraction

**User Story:** As a translator, I want to extract structured text and metadata from PDF files, so that I can work with machine-readable content instead of binary PDF.

#### Acceptance Criteria

1. WHEN a user specifies a project directory, THE Book_Pipeline SHALL invoke Opendataloader_PDF with the project's input PDF
2. THE Book_Pipeline SHALL request both markdown and JSON output formats from Opendataloader_PDF
3. THE Book_Pipeline SHALL write extracted markdown to `projects/<book-id>/source/`
4. THE Book_Pipeline SHALL write extracted JSON metadata to `projects/<book-id>/source/`
5. THE Book_Pipeline SHALL extract images to `projects/<book-id>/source/images/` when image-output is "external"
6. IF Java 11+ is not available in PATH, THEN THE Book_Pipeline SHALL return an error with installation instructions
7. IF Opendataloader_PDF is not installed, THEN THE Book_Pipeline SHALL return an error with installation instructions
8. WHEN extraction completes successfully, THE Book_Pipeline SHALL update Pipeline_State_File stage "extract" to "done"
9. THE Book_Pipeline SHALL support optional page range extraction for testing (e.g., "1-5")
10. THE Book_Pipeline SHALL support both Python API and CLI modes for Opendataloader_PDF invocation

### Requirement 3: Text Normalization

**User Story:** As a translator, I want extracted text to be cleaned and normalized, so that I can work with consistent formatting without PDF artifacts.

#### Acceptance Criteria

1. WHEN normalization runs on extracted markdown, THE Book_Pipeline SHALL remove page numbers from text
2. THE Book_Pipeline SHALL remove repeated headers and footers
3. THE Book_Pipeline SHALL join hyphenated words split across lines
4. THE Book_Pipeline SHALL preserve intentional formatting (lists, quotes, code blocks)
5. THE Book_Pipeline SHALL identify potential chapter boundaries based on heading patterns
6. THE Book_Pipeline SHALL write normalized text to a staging area
7. THE Book_Pipeline SHALL generate a report of detected chapter boundaries
8. WHEN normalization completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "normalize" to "done"

### Requirement 4: Chapter Splitting

**User Story:** As a translator, I want the book divided into logical chapters, so that I can translate and review manageable sections.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL support automatic chapter detection based on heading patterns
2. THE Book_Pipeline SHALL support manual chapter splitting via a rules file
3. WHEN using manual rules, THE Book_Pipeline SHALL read chapter definitions from a JSON configuration file
4. FOR EACH detected or configured chapter, THE Book_Pipeline SHALL create a separate markdown file in `projects/<book-id>/chapters/`
5. THE Book_Pipeline SHALL update Metadata_File with chapter list including id, title, source_path, and status
6. THE Book_Pipeline SHALL assign sequential IDs to chapters (00_foreword, 01_chapter, 02_chapter, etc.)
7. THE Book_Pipeline SHALL preserve chapter ordering in Metadata_File
8. WHEN chapter splitting completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "split" to "done"
9. IF a chapter boundary is ambiguous, THE Book_Pipeline SHALL log a warning in review/notes.md

### Requirement 5: Chapter Chunking

**User Story:** As a translator, I want chapters divided into translation-sized chunks, so that LLM translation requests stay within context limits and produce coherent results.

#### Acceptance Criteria

1. WHEN chunking a chapter, THE Book_Pipeline SHALL divide text into segments not exceeding a configurable character limit (default 6000)
2. THE Book_Pipeline SHALL NOT split a heading from its immediately following paragraph
3. THE Book_Pipeline SHALL NOT split list items across chunks unless the list exceeds the chunk size limit
4. THE Book_Pipeline SHALL NOT split code blocks or block quotes across chunks
5. FOR EACH chunk, THE Book_Pipeline SHALL create three files: `<chunk-id>.source.md`, `<chunk-id>.ru.md`, `<chunk-id>.meta.json`
6. THE Book_Pipeline SHALL write chunks to `projects/<book-id>/chunks/<chapter-id>/`
7. THE Book_Pipeline SHALL record chunk metadata including chapter reference, sequence number, character count, and status
8. WHEN chunking completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "chunk" to "done"

### Requirement 6: Terminology Management

**User Story:** As a translator, I want consistent terminology across all translations, so that readers experience coherent language and key concepts are properly conveyed.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL read terminology mappings from the root TERMINOLOGY.md file
2. THE Book_Pipeline SHALL read project-specific terminology from `projects/<book-id>/glossary.md` if it exists
3. WHEN project-specific and root glossaries conflict, THE Book_Pipeline SHALL log a warning in review/terminology-report.md
4. THE Book_Pipeline SHALL include glossary content in translation prompts
5. THE Book_Pipeline SHALL support terminology entries with usage rules and context
6. THE Book_Pipeline SHALL preserve terminology entries in structured format (English term, Russian translation, usage notes)

### Requirement 7: Translation Execution

**User Story:** As a translator, I want automated translation of chunks using LLM with terminology awareness, so that I can focus on review and refinement rather than initial translation.

#### Acceptance Criteria

1. WHEN translation runs, THE Book_Pipeline SHALL translate each chunk with status "pending" or "chunked"
2. THE Book_Pipeline SHALL include glossary content in each translation request
3. THE Book_Pipeline SHALL include surrounding context (previous and next chunk summaries) when available
4. THE Book_Pipeline SHALL write translated text to `<chunk-id>.ru.md`
5. THE Book_Pipeline SHALL update chunk meta.json with status "translated" and timestamp
6. IF a chunk is already translated and force flag is false, THEN THE Book_Pipeline SHALL skip that chunk
7. IF translation fails for a chunk, THEN THE Book_Pipeline SHALL set chunk status to "error" and log details to review/translation-errors.md
8. THE Book_Pipeline SHALL support translation modes: quick (direct), normal (with terminology analysis), refined (with review pass)
9. WHEN all chunks in a chapter are translated, THE Book_Pipeline SHALL update chapter status in Metadata_File
10. THE Book_Pipeline SHALL preserve manual edits to translated chunks when re-running translation

### Requirement 8: Chapter Assembly

**User Story:** As a translator, I want translated chunks assembled into complete chapter files, so that I can review full chapters and prepare for publishing.

#### Acceptance Criteria

1. WHEN assembly runs, THE Book_Pipeline SHALL concatenate all translated chunks for each chapter in sequence order
2. THE Book_Pipeline SHALL write assembled chapters to `projects/<book-id>/translated/<chapter-id>.md`
3. THE Book_Pipeline SHALL preserve markdown formatting during assembly
4. THE Book_Pipeline SHALL generate a report of missing chunks in review/missing-sections.md
5. IF any chunks have status "error" or "pending", THEN THE Book_Pipeline SHALL mark the chapter as incomplete in the report
6. THE Book_Pipeline SHALL update chapter status in Metadata_File to "translated" when assembly succeeds
7. WHEN assembly completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "assemble" to "done"

### Requirement 9: Translation Review and Quality Checks

**User Story:** As a translator, I want automated quality checks on translations, so that I can identify issues before manual review.

#### Acceptance Criteria

1. WHEN review runs, THE Book_Pipeline SHALL verify all chapters in Metadata_File have corresponding translated files
2. THE Book_Pipeline SHALL verify chapter file sizes are within expected ranges (not empty, not suspiciously large)
3. THE Book_Pipeline SHALL check that key terms from glossary appear in translations with consistent spelling
4. THE Book_Pipeline SHALL detect English text remaining in Russian translations (excluding proper nouns and technical terms)
5. THE Book_Pipeline SHALL verify markdown structure is preserved (headings, lists, quotes)
6. THE Book_Pipeline SHALL generate review/terminology-report.md with term usage statistics
7. THE Book_Pipeline SHALL generate review/quality-report.md with all detected issues
8. THE Book_Pipeline SHALL NOT modify translation files during review
9. WHEN review completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "review" to "done"

### Requirement 10: Reader Publishing

**User Story:** As a translator, I want to publish translations as a web reader and standalone HTML file, so that readers can access the translated book in convenient formats.

#### Acceptance Criteria

1. WHEN publishing runs, THE Book_Pipeline SHALL read Metadata_File and all translated chapter files
2. THE Book_Pipeline SHALL generate a table of contents from chapter titles
3. THE Book_Pipeline SHALL copy the reader template to `projects/<book-id>/dist/reader/`
4. THE Book_Pipeline SHALL inject translated chapters into the reader HTML
5. THE Book_Pipeline SHALL inject metadata (title, author, translator contact) into the reader
6. THE Book_Pipeline SHALL generate a standalone HTML file at `projects/<book-id>/dist/<book-id>-ru.html`
7. THE Standalone_HTML SHALL embed all JavaScript, CSS, and content without external dependencies
8. THE Standalone_HTML SHALL be openable by double-clicking the file
9. THE Reader SHALL support search functionality across all chapters
10. THE Reader SHALL support table of contents navigation
11. THE Reader SHALL support theme switching (light/dark)
12. THE Reader SHALL support font size adjustment
13. WHEN publishing completes, THE Book_Pipeline SHALL update Pipeline_State_File stage "publish" to "done"

### Requirement 11: Project Status Reporting

**User Story:** As a translator, I want to view project status at any time, so that I can understand progress and identify next steps.

#### Acceptance Criteria

1. WHEN status command runs, THE Book_Pipeline SHALL read Metadata_File and Pipeline_State_File
2. THE Book_Pipeline SHALL display book title, author, and language pair
3. THE Book_Pipeline SHALL display current pipeline stage
4. THE Book_Pipeline SHALL display status of all pipeline stages
5. THE Book_Pipeline SHALL display chapter count and translation progress
6. THE Book_Pipeline SHALL complete status check in under 1 second for typical projects
7. IF Metadata_File or Pipeline_State_File is missing, THEN THE Book_Pipeline SHALL return an error with diagnostic information

### Requirement 12: Multi-Project Support

**User Story:** As a translator, I want to manage multiple book projects simultaneously, so that I can work on several translations in parallel.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL store each project in a separate `projects/<book-id>/` directory
2. THE Book_Pipeline SHALL NOT share state between projects except for the root TERMINOLOGY.md
3. THE Book_Pipeline SHALL support listing all projects in the projects directory
4. THE Book_Pipeline SHALL allow running pipeline commands on any project by specifying project directory
5. THE Book_Pipeline SHALL prevent project ID collisions by checking for existing directories during initialization

### Requirement 13: Progress Persistence and Resumability

**User Story:** As a translator, I want to resume pipeline execution after interruption, so that I don't lose progress from long-running operations.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL save chunk status after each chunk translation completes
2. THE Book_Pipeline SHALL save Pipeline_State_File after each stage completes
3. WHEN a pipeline command is interrupted, THE Book_Pipeline SHALL NOT corrupt existing files
4. WHEN resuming translation, THE Book_Pipeline SHALL skip chunks with status "translated" or "approved"
5. THE Book_Pipeline SHALL support force flag to re-translate already translated chunks
6. THE Book_Pipeline SHALL update Metadata_File updated_at timestamp when any content changes

### Requirement 14: Manual Edit Preservation

**User Story:** As a translator, I want to manually edit translations without the pipeline overwriting my changes, so that I can refine translations and fix errors.

#### Acceptance Criteria

1. WHEN translation runs without force flag, THE Book_Pipeline SHALL NOT overwrite existing translated chunk files
2. WHEN assembly runs, THE Book_Pipeline SHALL use existing translated chunks regardless of their modification time
3. THE Book_Pipeline SHALL support marking chunks as "approved" to indicate manual review completion
4. THE Book_Pipeline SHALL NOT modify files in the translated/ directory except during assembly
5. THE Book_Pipeline SHALL preserve file modification timestamps when reading files

### Requirement 15: Error Handling and Diagnostics

**User Story:** As a translator, I want clear error messages and diagnostic information, so that I can resolve issues without deep technical knowledge.

#### Acceptance Criteria

1. WHEN a pipeline command fails, THE Book_Pipeline SHALL return a non-zero exit code
2. THE Book_Pipeline SHALL print error messages to stderr
3. THE Book_Pipeline SHALL include actionable remediation steps in error messages
4. THE Book_Pipeline SHALL write detailed error logs to review/ directory for complex failures
5. THE Book_Pipeline SHALL validate prerequisites (Java, Python version, dependencies) before running extraction
6. IF a required file is missing, THEN THE Book_Pipeline SHALL specify the expected file path in the error message
7. THE Book_Pipeline SHALL NOT leave partially written files when operations fail

### Requirement 16: Configuration and Customization

**User Story:** As a translator, I want to customize pipeline behavior per project, so that I can adapt to different book structures and translation requirements.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL support configurable chunk size limits
2. THE Book_Pipeline SHALL support configurable translation modes (quick, normal, refined)
3. THE Book_Pipeline SHALL support configurable source and target languages
4. THE Book_Pipeline SHALL read configuration from Metadata_File
5. THE Book_Pipeline SHALL support command-line overrides for configuration values
6. THE Book_Pipeline SHALL validate configuration values and reject invalid settings with clear error messages

### Requirement 17: Metadata Parsing and Serialization

**User Story:** As a developer, I want reliable JSON parsing and serialization, so that metadata files remain consistent and readable.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL parse JSON files with UTF-8 encoding
2. THE Book_Pipeline SHALL serialize JSON with 2-space indentation and ensure_ascii=False
3. THE Book_Pipeline SHALL add a trailing newline to JSON files
4. THE Book_Pipeline SHALL create parent directories when writing JSON files
5. FOR ALL valid Metadata_File objects, THE Book_Pipeline SHALL satisfy: parse(serialize(metadata)) produces equivalent metadata (round-trip property)
6. IF JSON parsing fails, THEN THE Book_Pipeline SHALL return an error with file path and parse error details

### Requirement 18: Pipeline State Transitions

**User Story:** As a developer, I want pipeline stages to transition in correct order, so that the system maintains valid state.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL enforce stage order: init → extract → normalize → split → chunk → translate → assemble → review → publish
2. WHEN a stage completes with status "done", THE Book_Pipeline SHALL set current_stage to the next pending stage
3. THE Book_Pipeline SHALL update Pipeline_State_File updated_at timestamp on every state change
4. THE Book_Pipeline SHALL allow re-running any stage regardless of current_stage
5. THE Book_Pipeline SHALL NOT automatically transition to next stage if current stage completes with status "error"

### Requirement 19: File System Operations Safety

**User Story:** As a translator, I want the pipeline to protect my work from accidental data loss, so that I can experiment safely.

#### Acceptance Criteria

1. WHEN creating a project directory that already exists, THE Book_Pipeline SHALL require force flag to proceed
2. WHEN copying PDF to input directory, THE Book_Pipeline SHALL require force flag to overwrite existing PDF
3. THE Book_Pipeline SHALL NOT delete user-created files in review/ directory
4. THE Book_Pipeline SHALL NOT delete manually edited translations without explicit force flag
5. THE Book_Pipeline SHALL create backup copies of Metadata_File and Pipeline_State_File before modifying them
6. IF disk space is insufficient for an operation, THEN THE Book_Pipeline SHALL fail before modifying any files

### Requirement 20: Standalone HTML Generation

**User Story:** As a translator, I want to generate a single-file HTML with all content embedded, so that I can share translations without requiring web hosting.

#### Acceptance Criteria

1. WHEN generating Standalone_HTML, THE Book_Pipeline SHALL embed all JavaScript code inline
2. THE Book_Pipeline SHALL embed all CSS styles inline
3. THE Book_Pipeline SHALL embed all chapter content inline
4. THE Book_Pipeline SHALL NOT include external resource references (no src= or href= to external URLs)
5. THE Standalone_HTML SHALL preserve special characters and Unicode text correctly
6. THE Standalone_HTML SHALL NOT corrupt JavaScript template literals or regex patterns during embedding
7. THE Standalone_HTML SHALL be under 10MB for typical books (300-500 pages)
8. WHEN opened in a browser, THE Standalone_HTML SHALL function identically to the web reader version

### Requirement 21: Glossary Format and Parsing

**User Story:** As a translator, I want to maintain glossary in readable markdown format, so that I can edit terminology without special tools.

#### Acceptance Criteria

1. THE Book_Pipeline SHALL parse glossary from markdown tables with columns: English, Russian, Usage Notes
2. THE Book_Pipeline SHALL support glossary entries with multi-line usage notes
3. THE Book_Pipeline SHALL preserve glossary formatting when reading
4. THE Book_Pipeline SHALL ignore markdown comments and non-table content in glossary files
5. IF glossary parsing fails, THEN THE Book_Pipeline SHALL log a warning and continue with empty glossary

### Requirement 22: Chapter Metadata Tracking

**User Story:** As a translator, I want detailed metadata for each chapter, so that I can track translation progress and quality metrics.

#### Acceptance Criteria

1. FOR EACH chapter, THE Metadata_File SHALL store: id, title, source_path, translated_path, status, word_count, chunk_count
2. THE Book_Pipeline SHALL update chapter metadata when chapter content changes
3. THE Book_Pipeline SHALL calculate word count from source text
4. THE Book_Pipeline SHALL track chunk count from chunks directory
5. THE Book_Pipeline SHALL support chapter statuses: pending, extracted, normalized, chunked, translated, reviewed, approved, published

### Requirement 23: Image Handling

**User Story:** As a translator, I want images from the PDF preserved and accessible, so that I can include them in the published reader if needed.

#### Acceptance Criteria

1. WHEN extraction runs with image-output "external", THE Book_Pipeline SHALL save images to source/images/
2. THE Book_Pipeline SHALL preserve image filenames from Opendataloader_PDF
3. THE Book_Pipeline SHALL record image references in extracted JSON metadata
4. THE Book_Pipeline SHALL support copying images to dist/ directory during publishing
5. THE Book_Pipeline SHALL support embedding images in Standalone_HTML as base64 data URIs

### Requirement 24: Command-Line Interface Consistency

**User Story:** As a translator, I want consistent command-line interface across all pipeline commands, so that I can learn the system quickly.

#### Acceptance Criteria

1. ALL pipeline commands SHALL accept --project-dir parameter to specify project location
2. ALL pipeline commands SHALL support --help flag showing usage information
3. ALL pipeline commands SHALL print progress messages to stdout
4. ALL pipeline commands SHALL print errors to stderr
5. ALL pipeline commands SHALL return 0 on success, non-zero on failure
6. ALL pipeline commands SHALL support --force flag for operations that modify existing files
7. ALL pipeline commands SHALL validate required parameters before starting work

### Requirement 25: Translation Context Preservation

**User Story:** As a translator, I want translation to consider surrounding context, so that translations maintain coherence across chunk boundaries.

#### Acceptance Criteria

1. WHEN translating a chunk, THE Book_Pipeline SHALL include the last paragraph of the previous chunk as context
2. THE Book_Pipeline SHALL include the first paragraph of the next chunk as context
3. THE Book_Pipeline SHALL mark context text as "for reference only, do not translate"
4. THE Book_Pipeline SHALL NOT include context for the first chunk of a chapter
5. THE Book_Pipeline SHALL NOT include context for the last chunk of a chapter
6. THE Book_Pipeline SHALL limit context to 500 characters per boundary

