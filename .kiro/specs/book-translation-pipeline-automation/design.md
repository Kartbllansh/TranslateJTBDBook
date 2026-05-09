# Design Document: Book Translation Pipeline Automation

## Overview

The Book Translation Pipeline Automation system is a Python-based CLI toolchain that transforms PDF books from English to Russian through a structured, repeatable pipeline. The system emphasizes file-based state management, manual edit preservation, and modular design to support multiple concurrent book projects.

### Design Goals

1. **Repeatability**: Every pipeline stage can be re-run without data loss
2. **Transparency**: All state lives in readable files on disk
3. **Manual Control**: Human edits are preserved and never overwritten without explicit force flags
4. **Modularity**: Each pipeline stage is independent and testable
5. **Multi-Project**: Support multiple book translations simultaneously

### Non-Goals

- Real-time collaborative editing
- Cloud-based processing (local-first design)
- Automatic copyright/licensing management
- Support for non-PDF formats (EPUB, DOCX) in initial version

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Book Pipeline CLI                            │
│  (Python modules in book_pipeline/)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                         │
│  - Stage management                                              │
│  - State persistence                                             │
│  - Error handling                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐      ┌──────────────┐
│  Extraction  │    │ Translation  │      │  Publishing  │
│   Pipeline   │    │   Pipeline   │      │   Pipeline   │
└──────────────┘    └──────────────┘      └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐      ┌──────────────┐
│ opendataloader│   │  LLM Service │      │    Reader    │
│     -pdf      │    │   (external) │      │   Template   │
└──────────────┘    └──────────────┘      └──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  File System     │
                    │  projects/       │
                    │    <book-id>/    │
                    └──────────────────┘
```

### Pipeline Stages

The system implements a linear pipeline with nine stages:

1. **init**: Create project structure and metadata
2. **extract**: Extract text and structure from PDF using opendataloader-pdf
3. **normalize**: Clean extracted text (remove headers/footers, fix line breaks)
4. **split**: Divide normalized text into logical chapters
5. **chunk**: Subdivide chapters into translation-sized segments
6. **translate**: Translate chunks using LLM with glossary context
7. **assemble**: Concatenate translated chunks into complete chapters
8. **review**: Run quality checks and generate reports
9. **publish**: Generate web reader and standalone HTML

Each stage:
- Reads from previous stage outputs
- Writes to its own output directory
- Updates pipeline-state.json on completion
- Can be re-run independently

### Component Architecture

```
book_pipeline/
├── __init__.py
├── common.py                 # Shared utilities
├── init_project.py           # Stage 1: Project initialization
├── extract_opendataloader.py # Stage 2: PDF extraction
├── normalize.py              # Stage 3: Text normalization
├── split_chapters.py         # Stage 4: Chapter splitting
├── chunk.py                  # Stage 5: Chunk creation
├── translate.py              # Stage 6: Translation
├── assemble.py               # Stage 7: Chapter assembly
├── review.py                 # Stage 8: Quality checks
├── publish.py                # Stage 9: Reader generation
└── project_status.py         # Status reporting
```

## Components and Interfaces

### 1. Common Module (`common.py`)

**Purpose**: Shared utilities for file I/O, state management, and string operations.

**Key Functions**:

```python
def read_json(path: Path) -> dict[str, Any]:
    """Parse JSON file with UTF-8 encoding."""

def write_json(path: Path, data: dict[str, Any]) -> None:
    """Serialize JSON with 2-space indent, ensure_ascii=False."""

def update_pipeline_stage(project_dir: Path, stage: str, status: str) -> None:
    """Update pipeline-state.json with new stage status."""

def slugify(value: str) -> str:
    """Convert string to kebab-case slug."""

def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
```

**Constants**:
```python
PIPELINE_STAGES = [
    "init", "extract", "normalize", "split", 
    "chunk", "translate", "assemble", "review", "publish"
]
```

### 2. Project Initialization (`init_project.py`)

**Purpose**: Create new book project workspace with directory structure and metadata files.

**Interface**:
```python
def main() -> int:
    """
    CLI entry point.
    
    Args (from argparse):
        --book-id: Project identifier (kebab-case)
        --title: Book title
        --author: Book author
        --pdf: Source PDF path
        --source-language: Source language code (default: en)
        --target-language: Target language code (default: ru)
        --translator-contact: Translator contact info
        --force: Overwrite existing project
    
    Returns:
        0 on success, 2 on error
    """
```

**Outputs**:
- `projects/<book-id>/` directory structure
- `metadata.json` with initial book information
- `pipeline-state.json` with init=done, others=pending
- `glossary.md` template
- `review/notes.md` template
- Copy of PDF in `input/book.pdf`

### 3. PDF Extraction (`extract_opendataloader.py`)

**Purpose**: Wrapper around opendataloader-pdf for extracting structured content from PDF.

**Interface**:
```python
def main() -> int:
    """
    CLI entry point.
    
    Args:
        --project-dir: Project directory
        --format: Output formats (default: markdown,json)
        --image-output: Image handling (off|embedded|external)
        --use-struct-tree: Use PDF structure tags
        --pages: Page range for extraction
        --use-cli: Use CLI instead of Python API
    
    Returns:
        0 on success, 2 on error
    """
```

**Outputs**:
- `source/extracted.md`: Markdown text
- `source/extracted.json`: Structure metadata
- `source/images/`: Extracted images (if external mode)

**Dependencies**:
- Java 11+ (required by opendataloader-pdf)
- opendataloader-pdf Python package or CLI

### 4. Text Normalization (`normalize.py`)

**Purpose**: Clean extracted text to remove PDF artifacts and prepare for chapter splitting.

**Interface**:
```python
def normalize_text(text: str, config: NormalizationConfig) -> str:
    """
    Clean extracted markdown text.
    
    Args:
        text: Raw extracted markdown
        config: Normalization configuration
    
    Returns:
        Cleaned markdown text
    """

@dataclass
class NormalizationConfig:
    remove_page_numbers: bool = True
    join_hyphenated_words: bool = True
    detect_headers_footers: bool = True
    preserve_code_blocks: bool = True
    preserve_lists: bool = True
```

**Algorithm**:
1. Identify repeated headers/footers by pattern matching
2. Remove page numbers (patterns: "Page N", "N |", etc.)
3. Join hyphenated words split across lines
4. Preserve markdown structure (lists, quotes, code blocks)
5. Generate chapter boundary suggestions

**Outputs**:
- `source/normalized.md`: Cleaned text
- `review/normalization-report.md`: Detected patterns and suggestions

### 5. Chapter Splitting (`split_chapters.py`)

**Purpose**: Divide normalized text into logical chapters based on headings or manual rules.

**Interface**:
```python
def split_chapters(
    text: str,
    mode: SplitMode,
    rules: Optional[ChapterRules] = None
) -> list[Chapter]:
    """
    Split text into chapters.
    
    Args:
        text: Normalized markdown
        mode: 'auto' or 'manual'
        rules: Manual chapter definitions (required if mode='manual')
    
    Returns:
        List of Chapter objects
    """

@dataclass
class Chapter:
    id: str
    title: str
    content: str
    start_line: int
    end_line: int
```

**Auto Mode Algorithm**:
1. Scan for level-1 headings (`# Chapter N`)
2. Detect special sections (Foreword, Acknowledgments, Appendix, Notes)
3. Assign sequential IDs (00_foreword, 01_chapter, etc.)
4. Extract title from heading text

**Manual Mode**:
- Read `chapter-rules.json` with start/end patterns
- Match patterns against normalized text
- Split at specified boundaries

**Outputs**:
- `chapters/<chapter-id>.md`: Individual chapter files
- Updated `metadata.json` with chapter list

### 6. Chunking (`chunk.py`)

**Purpose**: Subdivide chapters into translation-sized segments that respect markdown structure.

**Interface**:
```python
def chunk_chapter(
    chapter: Chapter,
    max_chars: int = 6000
) -> list[Chunk]:
    """
    Split chapter into chunks respecting structure.
    
    Args:
        chapter: Chapter object
        max_chars: Maximum characters per chunk
    
    Returns:
        List of Chunk objects
    """

@dataclass
class Chunk:
    id: str
    chapter_id: str
    sequence: int
    content: str
    char_count: int
    status: str
```

**Smart Chunking Algorithm**:

```
function chunk_chapter(text, max_chars):
    chunks = []
    current_chunk = []
    current_size = 0
    
    blocks = parse_markdown_blocks(text)
    
    for block in blocks:
        block_size = len(block.text)
        
        # Never split heading from following paragraph
        if block.type == HEADING:
            if current_size + block_size > max_chars and current_chunk:
                chunks.append(join(current_chunk))
                current_chunk = [block]
                current_size = block_size
            else:
                current_chunk.append(block)
                current_size += block_size
            continue
        
        # Keep lists together if possible
        if block.type == LIST:
            if block_size > max_chars:
                # Split large lists at item boundaries
                items = split_list_items(block)
                for item in items:
                    if current_size + len(item) > max_chars:
                        chunks.append(join(current_chunk))
                        current_chunk = [item]
                        current_size = len(item)
                    else:
                        current_chunk.append(item)
                        current_size += len(item)
            else:
                if current_size + block_size > max_chars:
                    chunks.append(join(current_chunk))
                    current_chunk = [block]
                    current_size = block_size
                else:
                    current_chunk.append(block)
                    current_size += block_size
            continue
        
        # Never split code blocks or quotes
        if block.type in [CODE_BLOCK, QUOTE]:
            if current_size + block_size > max_chars and current_chunk:
                chunks.append(join(current_chunk))
                current_chunk = [block]
                current_size = block_size
            else:
                current_chunk.append(block)
                current_size += block_size
            continue
        
        # Regular paragraphs can be split
        if current_size + block_size > max_chars:
            if current_chunk:
                chunks.append(join(current_chunk))
            current_chunk = [block]
            current_size = block_size
        else:
            current_chunk.append(block)
            current_size += block_size
    
    if current_chunk:
        chunks.append(join(current_chunk))
    
    return chunks
```

**Outputs**:
- `chunks/<chapter-id>/<sequence>.source.md`: Source chunk
- `chunks/<chapter-id>/<sequence>.ru.md`: Translation (empty initially)
- `chunks/<chapter-id>/<sequence>.meta.json`: Chunk metadata

### 7. Translation (`translate.py`)

**Purpose**: Translate chunks using LLM with glossary context and surrounding chunk awareness.

**Interface**:
```python
def translate_chunk(
    chunk: Chunk,
    glossary: Glossary,
    context: TranslationContext,
    mode: TranslationMode
) -> TranslationResult:
    """
    Translate a single chunk.
    
    Args:
        chunk: Chunk to translate
        glossary: Terminology mappings
        context: Previous/next chunk context
        mode: Translation mode (quick|normal|refined)
    
    Returns:
        TranslationResult with translated text and metadata
    """

@dataclass
class TranslationContext:
    previous_chunk_summary: Optional[str]
    next_chunk_summary: Optional[str]
    chapter_title: str

class TranslationMode(Enum):
    QUICK = "quick"      # Direct translation
    NORMAL = "normal"    # With terminology analysis
    REFINED = "refined"  # With review pass
```

**Translation Prompt Structure**:

```
You are translating a technical book from English to Russian.

GLOSSARY:
{glossary_entries}

CONTEXT:
Previous section: {previous_summary}
Current chapter: {chapter_title}
Next section: {next_summary}

SOURCE TEXT:
{chunk_content}

INSTRUCTIONS:
1. Translate the text naturally while maintaining technical accuracy
2. Use glossary terms consistently
3. Preserve markdown formatting
4. Maintain the author's tone and style
5. Do not translate proper nouns, product names, or code

TRANSLATION:
```

**Translation Modes**:

- **Quick**: Single-pass translation with glossary
- **Normal**: Two-pass (translate + terminology check)
- **Refined**: Three-pass (translate + review + polish)

**Outputs**:
- Updated `chunks/<chapter-id>/<sequence>.ru.md`
- Updated `chunks/<chapter-id>/<sequence>.meta.json` with status and timestamp
- `review/translation-errors.md` for failed chunks

### 8. Assembly (`assemble.py`)

**Purpose**: Concatenate translated chunks into complete chapter files.

**Interface**:
```python
def assemble_chapter(chapter_id: str, project_dir: Path) -> AssemblyResult:
    """
    Assemble translated chunks into complete chapter.
    
    Args:
        chapter_id: Chapter identifier
        project_dir: Project root directory
    
    Returns:
        AssemblyResult with status and warnings
    """

@dataclass
class AssemblyResult:
    success: bool
    output_path: Path
    missing_chunks: list[str]
    warnings: list[str]
```

**Algorithm**:
1. Read all chunk metadata for chapter
2. Sort chunks by sequence number
3. Verify no gaps in sequence
4. Concatenate translated content
5. Preserve markdown structure
6. Write to `translated/<chapter-id>.md`

**Outputs**:
- `translated/<chapter-id>.md`: Complete translated chapter
- `review/missing-sections.md`: Report of incomplete chapters

### 9. Review (`review.py`)

**Purpose**: Run automated quality checks on translations.

**Interface**:
```python
def review_project(project_dir: Path) -> ReviewReport:
    """
    Run all quality checks on project.
    
    Args:
        project_dir: Project root directory
    
    Returns:
        ReviewReport with findings
    """

@dataclass
class ReviewReport:
    structural_issues: list[Issue]
    terminology_issues: list[Issue]
    completeness_issues: list[Issue]
    quality_score: float
```

**Quality Checks**:

1. **Structural Checks**:
   - All chapters in metadata have translated files
   - No empty chapter files
   - Markdown structure preserved (heading levels, lists)
   - File sizes within expected ranges

2. **Terminology Checks**:
   - Glossary terms used consistently
   - Key abbreviations not accidentally translated
   - English phrases not left in Russian text

3. **Completeness Checks**:
   - All chunks translated
   - No missing sections
   - Image references preserved

**Outputs**:
- `review/quality-report.md`: Overall quality assessment
- `review/terminology-report.md`: Term usage statistics
- `review/structural-report.md`: Structure validation results

### 10. Publishing (`publish.py`)

**Purpose**: Generate web reader and standalone HTML from translated chapters.

**Interface**:
```python
def publish_project(
    project_dir: Path,
    standalone: bool = True
) -> PublishResult:
    """
    Generate reader outputs.
    
    Args:
        project_dir: Project root directory
        standalone: Generate standalone HTML
    
    Returns:
        PublishResult with output paths
    """
```

**Publishing Algorithm**:

1. Read metadata.json and all translated chapters
2. Generate table of contents from chapter titles
3. Copy reader template to `dist/reader/`
4. Inject chapter content into reader HTML
5. If standalone mode:
   - Inline all CSS from styles.css
   - Inline all JavaScript from app.js
   - Embed chapter content as JSON
   - Convert cover image to base64 data URI
   - Write single HTML file

**Standalone HTML Generation**:

```python
def generate_standalone_html(
    template_html: str,
    css: str,
    js: str,
    chapters: list[Chapter],
    cover_image: bytes
) -> str:
    """
    Generate standalone HTML with embedded assets.
    
    Critical: Preserve JavaScript special characters during embedding.
    """
    # Escape chapter content for JSON embedding
    chapters_json = json.dumps(chapters, ensure_ascii=False)
    # Escape < to prevent HTML injection
    chapters_json = chapters_json.replace('<', '\\u003c')
    
    # Convert cover to data URI
    cover_data = f"data:image/png;base64,{base64.b64encode(cover_image).decode()}"
    
    # Inline CSS
    html = template_html.replace(
        '<link rel="stylesheet" href="./styles.css">',
        f'<style>\n{css}\n</style>'
    )
    
    # Inline cover
    html = html.replace('src="./cover.png"', f'src="{cover_data}"')
    
    # Inline JavaScript with embedded chapters
    html = html.replace(
        '<script src="./app.js"></script>',
        f'<script>\nwindow.EMBEDDED_CHAPTERS = {chapters_json};\n</script>\n<script>\n{js}\n</script>'
    )
    
    return html
```

**Outputs**:
- `dist/reader/`: Web reader directory
- `dist/<book-id>-ru.html`: Standalone HTML file

## Data Models

### metadata.json Schema

```json
{
  "schema_version": 1,
  "book_id": "when-coffee-and-kale-compete",
  "title": "When Coffee and Kale Compete",
  "author": "Alan Klement",
  "source_language": "en",
  "target_language": "ru",
  "input_file": "input/book.pdf",
  "translator": {
    "contact": "@mark0vartem"
  },
  "chapters": [
    {
      "id": "01_chapter",
      "title": "Chapter 1. Challenges, Hope, and Progress",
      "source_path": "chapters/01_chapter.md",
      "translated_path": "translated/01_chapter.md",
      "status": "translated",
      "word_count": 3542,
      "chunk_count": 3
    }
  ],
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T14:30:00Z"
}
```

**Field Descriptions**:
- `schema_version`: Metadata format version for future migrations
- `book_id`: Unique project identifier (kebab-case)
- `chapters`: Array of chapter metadata objects
- `status`: One of: pending, extracted, normalized, chunked, translated, reviewed, approved, published

### pipeline-state.json Schema

```json
{
  "current_stage": "translate",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T14:30:00Z",
  "stages": {
    "init": "done",
    "extract": "done",
    "normalize": "done",
    "split": "done",
    "chunk": "done",
    "translate": "in_progress",
    "assemble": "pending",
    "review": "pending",
    "publish": "pending"
  }
}
```

**Stage Status Values**:
- `pending`: Not started
- `in_progress`: Currently running
- `done`: Completed successfully
- `error`: Failed with errors

### Chunk Metadata Schema

```json
{
  "chunk_id": "01_chapter_0001",
  "chapter_id": "01_chapter",
  "sequence": 1,
  "char_count": 4523,
  "status": "translated",
  "created_at": "2025-01-15T12:00:00Z",
  "translated_at": "2025-01-15T13:15:00Z",
  "translation_mode": "normal",
  "error": null
}
```

### Glossary Format

Glossary files use markdown tables:

```markdown
# Glossary

| English | Russian | Usage Notes |
|---------|---------|-------------|
| Jobs to be Done | Jobs to be Done | Do not translate - proper methodology name |
| progress | прогресс | Context: customer progress toward goal |
| struggle | трудность | Avoid "борьба" - too aggressive |
```

## Error Handling

### Error Handling Strategy

1. **Fail Fast**: Validate prerequisites before starting work
2. **Atomic Operations**: Don't leave partially written files
3. **Clear Messages**: Include actionable remediation steps
4. **Detailed Logging**: Write error details to review/ directory
5. **Graceful Degradation**: Continue processing other chunks if one fails

### Error Categories

**Configuration Errors** (exit code 2):
- Missing required files
- Invalid JSON syntax
- Missing prerequisites (Java, Python packages)

**Processing Errors** (exit code 1):
- PDF extraction failures
- Translation API errors
- File I/O errors

**Validation Errors** (exit code 3):
- Quality check failures
- Incomplete translations
- Structural inconsistencies

### Error Message Format

```
Error: Java was not found in PATH

opendataloader-pdf requires Java 11 or higher.

To fix this:
1. Install a JDK (OpenJDK or Oracle JDK)
2. Verify installation: java -version
3. Ensure java is in your PATH

For installation instructions, visit:
https://adoptium.net/
```

### Error Recovery

**Chunk Translation Failures**:
1. Set chunk status to "error"
2. Log error details to `review/translation-errors.md`
3. Continue with next chunk
4. Allow retry with `--retry-failed` flag

**File System Errors**:
1. Check disk space before operations
2. Create backup of metadata files before updates
3. Rollback on failure

## Testing Strategy

### Unit Testing

**Test Coverage Areas**:
1. JSON parsing and serialization (round-trip properties)
2. Slugify function (special characters, Unicode)
3. Markdown block parsing
4. Chunking algorithm (boundary conditions)
5. Normalization patterns (headers, footers, hyphens)
6. Glossary parsing (table format, multi-line notes)

**Example Unit Tests**:

```python
def test_slugify_basic():
    assert slugify("When Coffee and Kale Compete") == "when-coffee-and-kale-compete"

def test_slugify_unicode():
    assert slugify("Когда кофе и капуста") == "когда-кофе-и-капуста"

def test_json_round_trip():
    original = {"book_id": "test", "chapters": []}
    serialized = json.dumps(original, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert parsed == original

def test_chunk_respects_heading():
    text = "# Heading\n\nParagraph text"
    chunks = chunk_text(text, max_chars=10)
    # Should not split heading from paragraph
    assert len(chunks) == 1
```

### Integration Testing

**Test Scenarios**:
1. Full pipeline execution on sample PDF
2. Resume after interruption
3. Re-run stages with existing data
4. Force flag behavior
5. Multi-project isolation

**Test Data**:
- Small sample PDF (5-10 pages)
- Pre-extracted markdown samples
- Mock LLM responses for translation tests

### Property-Based Testing

Property-based testing is NOT appropriate for this system because:

1. **Infrastructure as Code Nature**: The pipeline is primarily orchestrating external tools (opendataloader-pdf, LLM APIs) and file operations, not implementing pure algorithms
2. **External Dependencies**: Most operations depend on external services (PDF extraction, LLM translation) that are not suitable for property-based testing
3. **File System State**: The system manages complex file system state that doesn't lend itself to property-based testing
4. **Configuration-Heavy**: Much of the behavior is configuration-driven rather than algorithmic

**Alternative Testing Approaches**:
- **Snapshot Testing**: For PDF extraction and normalization outputs
- **Example-Based Tests**: For specific chunking scenarios and edge cases
- **Integration Tests**: For end-to-end pipeline execution
- **Mock-Based Tests**: For translation and external API interactions

### Manual Testing Checklist

- [ ] Create new project from PDF
- [ ] Extract with various page ranges
- [ ] Normalize text with different PDF formats
- [ ] Split chapters automatically and manually
- [ ] Translate with all three modes
- [ ] Assemble chapters with missing chunks
- [ ] Run review checks
- [ ] Publish standalone HTML
- [ ] Verify standalone HTML opens without network
- [ ] Test force flag behavior
- [ ] Test resume after interruption

## Implementation Notes

### Technology Stack

- **Language**: Python 3.10+
- **External Tools**: opendataloader-pdf (requires Java 11+)
- **LLM Integration**: Pluggable (OpenAI, Anthropic, local models)
- **Frontend**: Vanilla JavaScript (no build step)
- **Storage**: File system (no database)

### Performance Considerations

1. **Chunking**: Process chapters in parallel where possible
2. **Translation**: Batch API requests to reduce latency
3. **Assembly**: Stream large files instead of loading entirely into memory
4. **Publishing**: Cache reader template to avoid repeated reads

### Security Considerations

1. **API Keys**: Never commit to repository, use environment variables
2. **PDF Content**: Projects directory in .gitignore (copyright protection)
3. **Input Validation**: Sanitize file paths to prevent directory traversal
4. **External Commands**: Use subprocess with explicit arguments, not shell=True

### Future Enhancements

1. **Web UI**: Local web interface for project management
2. **Parallel Translation**: Translate multiple chunks concurrently
3. **Translation Memory**: Reuse translations across projects
4. **Quality Metrics**: Automated translation quality scoring
5. **EPUB Support**: Extend to non-PDF formats
6. **Incremental Updates**: Re-translate only changed sections

## Appendix: File Structure Reference

```
projects/
└── <book-id>/
    ├── input/
    │   └── book.pdf                    # Source PDF
    ├── source/
    │   ├── extracted.md                # Raw extraction
    │   ├── extracted.json              # Structure metadata
    │   ├── normalized.md               # Cleaned text
    │   └── images/                     # Extracted images
    ├── chapters/
    │   ├── 00_foreword.md              # Individual chapters
    │   └── 01_chapter.md
    ├── chunks/
    │   └── 01_chapter/
    │       ├── 0001.source.md          # Source chunk
    │       ├── 0001.ru.md              # Translated chunk
    │       └── 0001.meta.json          # Chunk metadata
    ├── translated/
    │   ├── 00_foreword.md              # Assembled translations
    │   └── 01_chapter.md
    ├── review/
    │   ├── notes.md                    # Manual review notes
    │   ├── quality-report.md           # Automated checks
    │   ├── terminology-report.md       # Term usage
    │   ├── translation-errors.md       # Failed chunks
    │   └── missing-sections.md         # Incomplete chapters
    ├── dist/
    │   ├── reader/                     # Web reader
    │   │   ├── index.html
    │   │   ├── app.js
    │   │   ├── styles.css
    │   │   └── cover.png
    │   └── <book-id>-ru.html           # Standalone HTML
    ├── metadata.json                   # Book metadata
    ├── pipeline-state.json             # Pipeline progress
    └── glossary.md                     # Project glossary
```
