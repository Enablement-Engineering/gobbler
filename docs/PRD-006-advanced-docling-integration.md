# PRD-006: Advanced Docling Integration

## Overview
**Epic**: Document Intelligence & RAG Optimization
**Phase**: 3 - Advanced Features
**Estimated Effort**: 5-7 days
**Dependencies**: Docling service running (docker-compose)
**Parallel**: ✅ Can be implemented alongside other features

## Problem Statement

Gobbler's current Docling integration is minimal—a simple HTTP POST that returns flat markdown. This wastes Docling's powerful capabilities:

- **No structured access**: Tables become markdown strings, losing DataFrame functionality
- **No chunking**: Users must chunk documents themselves for RAG applications
- **No schema extraction**: Can't extract structured data (invoices, forms, contracts)
- **No image intelligence**: Pictures are ignored, no captions or classification
- **No provenance**: No page numbers, bounding boxes for citations
- **Single pipeline**: No access to VLM pipeline for complex/scanned documents

**User Stories:**
- "As a data analyst, I want to extract tables as DataFrames so I can analyze financial reports programmatically"
- "As a RAG developer, I want pre-chunked documents with metadata so I can build better retrieval systems"
- "As a compliance officer, I want to extract structured data from contracts using a schema so I can automate reviews"
- "As a researcher, I want page-level citations so I can reference exactly where information came from"

## Success Criteria

- [ ] Return structured DoclingDocument with tables, images, sections accessible
- [ ] Provide RAG-optimized chunking with hierarchical and hybrid strategies
- [ ] Support schema-based structured extraction (Pydantic models)
- [ ] Extract tables as DataFrames/CSV/JSON
- [ ] Include provenance (page numbers, bounding boxes) for visual grounding
- [ ] Support pipeline selection (standard, VLM, fast)
- [ ] Enable image classification and VLM captioning
- [ ] Offer PII detection and redaction mode

## Inspiration: Code Mode Pattern

From [Cloudflare's Code Mode](https://blog.cloudflare.com/code-mode/):

> "LLMs are better at writing code to call MCP, than at calling MCP directly."

Instead of simple tool calls, we should expose Docling as a **composable API** that Claude can write code against. This enables:

1. **Chained operations** without round-trips through the LLM
2. **Filtering and aggregation** in a single execution
3. **Familiar programming patterns** that LLMs excel at

**Vision**: Claude writes code like:
```python
doc = gobbler.docling.convert("report.pdf")
revenue_tables = [t for t in doc.tables if "revenue" in t.caption.lower()]
q3_data = revenue_tables[0].to_dataframe().query("quarter == 'Q3'")
print(f"Q3 Total: ${q3_data['amount'].sum():,.2f}")
```

This PRD focuses on exposing the building blocks. A future PRD could implement the full "Code Mode" sandbox execution.

---

## Technical Requirements

### Phase 1: Structured Document Output

#### 1.1 Enhanced `convert_document` Tool

Extend the existing tool with new output modes:

```python
@mcp.tool()
async def convert_document(
    file_path: str,
    enable_ocr: bool = True,
    output_format: Literal["markdown", "structured", "chunks"] = "markdown",
    output_file: Optional[str] = None,
) -> str:
    """
    Convert document to markdown or structured format using Docling.

    Args:
        file_path: Absolute path to document (PDF, DOCX, PPTX, XLSX)
        enable_ocr: Enable OCR for scanned documents (default: True)
        output_format: Output format:
            - "markdown": Clean markdown with frontmatter (default)
            - "structured": JSON with full document structure
            - "chunks": RAG-ready chunks with metadata
        output_file: Optional path to save output

    Returns:
        Converted content in requested format
    """
```

#### 1.2 New `DoclingDocument` Response Schema

```python
# src/gobbler_mcp/types.py

from typing import TypedDict, List, Optional

class BoundingBox(TypedDict):
    page: int
    x: float
    y: float
    width: float
    height: float

class TableCell(TypedDict):
    row: int
    col: int
    text: str
    is_header: bool

class TableItem(TypedDict):
    id: str
    caption: Optional[str]
    page: int
    bbox: BoundingBox
    rows: int
    cols: int
    cells: List[TableCell]
    markdown: str
    csv: str  # CSV representation

class PictureItem(TypedDict):
    id: str
    caption: Optional[str]
    page: int
    bbox: BoundingBox
    classification: Optional[str]  # "chart", "diagram", "photo", etc.
    description: Optional[str]     # VLM-generated description

class TextSection(TypedDict):
    id: str
    level: int  # 0=body, 1=h1, 2=h2, etc.
    heading: Optional[str]
    text: str
    page: int
    bbox: BoundingBox

class StructuredDocument(TypedDict):
    """Full structured representation of a converted document."""
    source: str
    title: str
    pages: int
    word_count: int
    sections: List[TextSection]
    tables: List[TableItem]
    pictures: List[PictureItem]
    markdown: str  # Full markdown for convenience
    confidence_score: float  # Docling's quality score
    conversion_time_ms: int
```

#### 1.3 Implementation

```python
# src/gobbler_mcp/converters/document.py

async def convert_document_structured(
    file_path: str,
    enable_ocr: bool = True,
) -> StructuredDocument:
    """
    Convert document and return full structured representation.

    Uses Docling's JSON export to preserve:
    - Document hierarchy (sections, subsections)
    - Table structure with cell-level data
    - Image metadata and classifications
    - Bounding boxes for visual grounding
    """
    config = get_config()
    service_url = config.get_service_url("docling")

    async with aiofiles.open(file_path, "rb") as f:
        file_data = await f.read()

    async with RetryableHTTPClient(timeout=120.0) as client:
        response = await client.post(
            f"{service_url}/v1/convert/file",
            files={"files": (os.path.basename(file_path), file_data)},
            data={
                "to_formats": "json,md",  # Request both
                "do_ocr": str(enable_ocr).lower(),
                "include_images": "true",
                "image_mode": "embedded",
            }
        )
        result = response.json()

    doc_data = result.get("document", {})

    # Parse Docling's JSON structure into our schema
    return StructuredDocument(
        source=file_path,
        title=doc_data.get("name", Path(file_path).stem),
        pages=doc_data.get("num_pages", 0),
        word_count=count_words(doc_data.get("md_content", "")),
        sections=parse_sections(doc_data),
        tables=parse_tables(doc_data),
        pictures=parse_pictures(doc_data),
        markdown=doc_data.get("md_content", ""),
        confidence_score=doc_data.get("confidence_score", 0.0),
        conversion_time_ms=int(result.get("timings", {}).get("total", 0) * 1000),
    )
```

---

### Phase 2: RAG-Optimized Chunking

#### 2.1 New `chunk_document` Tool

```python
@mcp.tool()
async def chunk_document(
    file_path: str,
    strategy: Literal["hierarchical", "hybrid"] = "hybrid",
    max_tokens: int = 512,
    tokenizer: str = "cl100k_base",  # OpenAI's tokenizer
    include_headers: bool = True,
    merge_peers: bool = True,
    output_file: Optional[str] = None,
) -> str:
    """
    Convert document to RAG-optimized chunks using Docling's native chunkers.

    Args:
        file_path: Absolute path to document
        strategy: Chunking strategy:
            - "hierarchical": Structure-aware, respects document hierarchy
            - "hybrid": Hierarchical + token-aware splitting/merging
        max_tokens: Maximum tokens per chunk (default: 512)
        tokenizer: Tokenizer to use:
            - "cl100k_base": OpenAI (GPT-4, text-embedding-3)
            - "o200k_base": OpenAI (GPT-4o)
            - "bert-base": BERT-style models
        include_headers: Include section headers in chunk context (default: True)
        merge_peers: Merge small adjacent chunks with same context (default: True)
        output_file: Optional path to save chunks as JSON

    Returns:
        JSON array of chunks, each with:
        - text: Chunk content
        - metadata: {page, section, headers, bbox}
        - token_count: Actual token count
    """
```

#### 2.2 Chunk Schema

```python
class DocumentChunk(TypedDict):
    """A single chunk optimized for RAG retrieval."""
    id: str
    text: str
    token_count: int
    metadata: ChunkMetadata

class ChunkMetadata(TypedDict):
    source: str           # File path
    page_start: int       # Starting page
    page_end: int         # Ending page
    section_headers: List[str]  # Hierarchical headers ["Chapter 1", "Section 1.2"]
    bbox: Optional[BoundingBox]  # For visual grounding
    chunk_type: str       # "text", "table", "list", "code"

class ChunkedDocument(TypedDict):
    """Document converted to RAG-ready chunks."""
    source: str
    title: str
    total_chunks: int
    total_tokens: int
    strategy: str
    tokenizer: str
    chunks: List[DocumentChunk]
```

#### 2.3 Implementation Notes

Docling exposes chunking via Python API, not REST. Options:

**Option A: Extend Docling-serve**
Add a `/v1/chunk` endpoint to the Docling Docker service.

**Option B: Use Docling Python directly**
Install `docling` package in Gobbler and chunk locally after fetching DoclingDocument JSON.

**Option C: Implement chunking in Gobbler**
Use the structured document output and implement chunking logic ourselves.

**Recommendation**: Option B - Install `docling` package for native chunking:

```python
# src/gobbler_mcp/converters/chunking.py

from docling.chunking import HybridChunker
from docling.datamodel.document import DoclingDocument
import tiktoken

async def chunk_document(
    structured_doc: StructuredDocument,
    strategy: str = "hybrid",
    max_tokens: int = 512,
    tokenizer_name: str = "cl100k_base",
) -> ChunkedDocument:
    """Chunk a structured document using Docling's native chunkers."""

    # Load tokenizer
    tokenizer = tiktoken.get_encoding(tokenizer_name)

    # Convert to Docling's internal format
    docling_doc = DoclingDocument.from_dict(structured_doc)

    # Create chunker
    if strategy == "hybrid":
        chunker = HybridChunker(
            tokenizer=tokenizer,
            max_tokens=max_tokens,
            merge_peers=True,
        )
    else:
        chunker = HierarchicalChunker()

    # Generate chunks
    chunks = list(chunker.chunk(docling_doc))

    return ChunkedDocument(
        source=structured_doc["source"],
        title=structured_doc["title"],
        total_chunks=len(chunks),
        total_tokens=sum(c.token_count for c in chunks),
        strategy=strategy,
        tokenizer=tokenizer_name,
        chunks=[chunk_to_dict(c) for c in chunks],
    )
```

---

### Phase 3: Structured Data Extraction

#### 3.1 New `extract_structured_data` Tool

```python
@mcp.tool()
async def extract_structured_data(
    file_path: str,
    schema: str,
    schema_format: Literal["json_schema", "typescript", "example"] = "json_schema",
) -> str:
    """
    Extract structured data from a document using a schema.

    Uses Docling's extraction API to pull specific fields from unstructured
    documents like invoices, contracts, forms, or reports.

    Args:
        file_path: Absolute path to document
        schema: Schema definition (JSON Schema, TypeScript interface, or example JSON)
        schema_format: Format of the schema:
            - "json_schema": Standard JSON Schema
            - "typescript": TypeScript interface definition
            - "example": Example JSON object (schema inferred)

    Returns:
        Extracted data matching the schema, as JSON

    Example schemas:

    JSON Schema:
    ```json
    {
      "type": "object",
      "properties": {
        "vendor_name": {"type": "string"},
        "invoice_number": {"type": "string"},
        "total_amount": {"type": "number"},
        "line_items": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "description": {"type": "string"},
              "quantity": {"type": "integer"},
              "unit_price": {"type": "number"}
            }
          }
        }
      }
    }
    ```

    TypeScript:
    ```typescript
    interface Invoice {
      vendor_name: string;
      invoice_number: string;
      total_amount: number;
      line_items: Array<{
        description: string;
        quantity: number;
        unit_price: number;
      }>;
    }
    ```

    Example:
    ```json
    {
      "vendor_name": "Acme Corp",
      "invoice_number": "INV-001",
      "total_amount": 1500.00,
      "line_items": [{"description": "Widget", "quantity": 10, "unit_price": 150.00}]
    }
    ```
    """
```

#### 3.2 Implementation

Docling's extraction API is in beta. We'll need to either:
1. Wait for stable Docling-serve support
2. Use Docling Python package directly
3. Implement with LLM extraction fallback

```python
# src/gobbler_mcp/converters/extraction.py

async def extract_structured(
    file_path: str,
    schema: dict,
) -> dict:
    """
    Extract structured data from document using schema.

    Primary: Use Docling's extraction API
    Fallback: Use LLM-based extraction with the document content
    """
    # First, convert to structured document
    doc = await convert_document_structured(file_path)

    try:
        # Try Docling's native extraction (when available)
        return await docling_extract(doc, schema)
    except NotImplementedError:
        # Fallback: Use LLM with structured output
        return await llm_extract(doc.markdown, schema)


async def llm_extract(content: str, schema: dict) -> dict:
    """
    Fallback extraction using LLM with structured output.

    Uses Claude or other LLM with JSON mode to extract
    data matching the schema from document content.
    """
    # This would integrate with the MCP client's LLM
    # or use a configured extraction model
    pass
```

---

### Phase 4: Table Intelligence

#### 4.1 New `extract_tables` Tool

```python
@mcp.tool()
async def extract_tables(
    file_path: str,
    output_format: Literal["json", "csv", "markdown"] = "json",
    table_mode: Literal["fast", "accurate"] = "accurate",
    include_captions: bool = True,
) -> str:
    """
    Extract all tables from a document with full structure.

    Args:
        file_path: Absolute path to document
        output_format: Format for table data:
            - "json": Structured JSON with rows/cols/cells
            - "csv": Separate CSV for each table
            - "markdown": Markdown tables
        table_mode: TableFormer mode:
            - "fast": Faster, less accurate
            - "accurate": Better for complex tables (default)
        include_captions: Include detected table captions (default: True)

    Returns:
        Extracted tables in requested format, with metadata:
        - table_id, page, caption, bbox
        - row_count, col_count
        - data in requested format
    """
```

#### 4.2 Table Response Schema

```python
class ExtractedTable(TypedDict):
    table_id: str
    page: int
    caption: Optional[str]
    bbox: BoundingBox
    row_count: int
    col_count: int
    headers: List[str]
    data: Union[List[List[str]], str]  # Rows or CSV string
    markdown: str
    confidence: float

class TablesResponse(TypedDict):
    source: str
    table_count: int
    tables: List[ExtractedTable]
```

---

### Phase 5: Pipeline Selection & Advanced Options

#### 5.1 Enhanced Pipeline Configuration

```python
@mcp.tool()
async def convert_document_advanced(
    file_path: str,
    pipeline: Literal["standard", "vlm", "fast"] = "standard",
    vlm_model: Optional[str] = None,
    ocr_engine: Literal["easyocr", "tesseract", "rapidocr"] = "easyocr",
    enrich_images: bool = False,
    enrich_code: bool = False,
    enrich_formulas: bool = False,
    redact_pii: bool = False,
    output_format: Literal["markdown", "structured", "chunks"] = "markdown",
) -> str:
    """
    Convert document with advanced pipeline options.

    Args:
        file_path: Absolute path to document
        pipeline: Conversion pipeline:
            - "standard": Default, balanced speed/quality
            - "vlm": Vision-Language Model for complex/scanned docs
            - "fast": Quick conversion, lower quality
        vlm_model: VLM model for 'vlm' pipeline (default: granite-docling)
        ocr_engine: OCR engine to use
        enrich_images: Classify and caption images using VLM
        enrich_code: Detect code blocks and identify language
        enrich_formulas: Extract LaTeX from equations
        redact_pii: Detect and redact personally identifiable information
        output_format: Output format (see convert_document)

    Returns:
        Converted document with requested enrichments
    """
```

---

## API Summary

| Tool | Purpose | Phase |
|------|---------|-------|
| `convert_document` | Enhanced with `output_format` param | 1 |
| `chunk_document` | RAG-optimized chunking | 2 |
| `extract_structured_data` | Schema-based extraction | 3 |
| `extract_tables` | Table-specific extraction | 4 |
| `convert_document_advanced` | Full pipeline control | 5 |

---

## Dependencies

### Python Packages (add to pyproject.toml)

```toml
[project.dependencies]
# ... existing ...
docling = ">=2.0.0"           # For native chunking and document model
tiktoken = ">=0.5.0"          # OpenAI tokenizer for chunking
```

### Docling-serve Updates

May need to extend or configure Docling-serve for:
- JSON output format
- Image embedding modes
- Table mode configuration

---

## Testing Requirements

### Unit Tests
- [ ] Test structured document parsing from Docling JSON
- [ ] Test chunking with various strategies and tokenizers
- [ ] Test schema validation for extraction
- [ ] Test table parsing and format conversion

### Integration Tests
- [ ] Test full pipeline with real PDFs (tables, images, text)
- [ ] Test VLM pipeline with scanned documents
- [ ] Test chunking produces valid token counts
- [ ] Test extraction with various schema formats

### Test Documents
Create fixtures in `tests/fixtures/documents/`:
- `invoice_sample.pdf` - For extraction testing
- `table_heavy.pdf` - Complex tables
- `scanned_doc.pdf` - OCR testing
- `mixed_content.pdf` - Images, tables, text

---

## Rollout Plan

### Phase 1: Structured Output (2 days)
- Extend `convert_document` with `output_format` parameter
- Implement `StructuredDocument` response type
- Add structured parsing from Docling JSON

### Phase 2: Chunking (1-2 days)
- Add `docling` package dependency
- Implement `chunk_document` tool
- Support hierarchical and hybrid strategies

### Phase 3: Extraction (1-2 days)
- Implement `extract_structured_data` tool
- Add schema validation (JSON Schema, TypeScript, example)
- Add LLM fallback for extraction

### Phase 4: Tables (1 day)
- Implement `extract_tables` tool
- Support CSV, JSON, markdown output

### Phase 5: Advanced Pipeline (1 day)
- Implement `convert_document_advanced`
- Add pipeline selection and enrichment options

---

## Future Considerations

### Code Mode Execution (Future PRD)

Inspired by Cloudflare's approach, a future enhancement could:

1. **Expose Gobbler as a TypeScript/Python SDK**
2. **Run Claude-generated code in a sandbox**
3. **Enable chained operations** without round-trips

Example workflow:
```python
# Claude generates this code
doc = await gobbler.convert("report.pdf", output="structured")
tables = [t for t in doc.tables if "revenue" in t.caption.lower()]
chunks = await gobbler.chunk(doc, strategy="hybrid", max_tokens=512)
embeddings = [embed(c.text) for c in chunks]
```

This would require:
- Sandbox execution environment (like Cloudflare Workers)
- SDK generation from MCP tool definitions
- Security boundaries for file/network access

### Visual Grounding UI

With bounding boxes preserved, we could:
- Generate highlighted PDFs showing source locations
- Build a "citation viewer" for RAG applications
- Enable "click to source" in document Q&A

---

## Success Metrics

- **Adoption**: % of document conversions using structured/chunks output
- **RAG Quality**: User feedback on chunk quality for retrieval
- **Extraction Accuracy**: Schema match rate for structured extraction
- **Performance**: Conversion time with various pipeline options
