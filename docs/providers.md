# Providers

Gobbler uses a **provider abstraction** system that allows pluggable backends for content conversion. This enables swapping between local and cloud-based services, adding new backends without changing application code, and graceful fallback between multiple providers.

## Overview

Providers are organized by **category** (the type of content they process):

| Category | Purpose | Available Providers |
|----------|---------|---------------------|
| `transcription` | Audio/video to text | `whisper-local` |
| `document` | PDF, DOCX, PPTX, XLSX to markdown | `docling` |
| `webpage` | Web pages to markdown | `crawl4ai` |

Each category has a default provider that can be overridden via configuration or CLI flags.

## Available Providers

### Transcription Providers

| Provider | Description | Requirements |
|----------|-------------|--------------|
| `whisper-local` | Local transcription using faster-whisper with CoreML acceleration on M-series Macs | ffmpeg |

#### whisper-local

Uses the [faster-whisper](https://github.com/guillaumekln/faster-whisper) library for fast, local transcription. Automatically uses CoreML acceleration on Apple Silicon Macs.

**Features:**
- Fully offline - no API keys required
- CoreML/Metal acceleration on M-series Macs
- Multiple model sizes (tiny, base, small, medium, large)
- Language auto-detection

**Model sizes:**

| Model | Speed | Accuracy | Memory | Use Case |
|-------|-------|----------|--------|----------|
| tiny | ~32x realtime | Lower | ~1GB | Quick drafts |
| base | ~16x realtime | Moderate | ~1GB | General use |
| **small** | ~6x realtime | Good | ~2GB | **Default** |
| medium | ~2x realtime | Better | ~5GB | Important content |
| large | ~1x realtime | Best | ~10GB | Critical accuracy |

### Document Providers

| Provider | Description | Requirements |
|----------|-------------|--------------|
| `docling` | Docling Docker service for document conversion with OCR | Docling running |

#### docling

Uses the [Docling](https://github.com/DS4SD/docling) service running in Docker for enterprise-grade document conversion.

**Features:**
- PDF, DOCX, PPTX, XLSX support
- Optional OCR for scanned documents
- Table extraction with structure preservation
- Markdown output with formatting

**Supported formats:**

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | With optional OCR for scanned pages |
| Word | `.docx` | Microsoft Word documents |
| PowerPoint | `.pptx` | Presentations with slide structure |
| Excel | `.xlsx` | Spreadsheets as markdown tables |

### Webpage Providers

| Provider | Description | Requirements |
|----------|-------------|--------------|
| `crawl4ai` | Crawl4AI Docker service with JavaScript rendering | Crawl4AI running |

#### crawl4ai

Uses the [Crawl4AI](https://github.com/unclecode/crawl4ai) service running in Docker for web scraping with full JavaScript support.

**Features:**
- JavaScript rendering via Playwright
- Clean markdown extraction
- CSS selector support
- Link and image extraction

## Configuration

Configure providers in `~/.config/gobbler/config.yaml`:

```yaml
# Provider configuration
providers:
  transcription:
    default: whisper-local
    whisper-local:
      model: small
      device: auto

  document:
    default: docling
    docling:
      service_url: http://localhost:5001
      timeout: 120

  webpage:
    default: crawl4ai
    crawl4ai:
      service_url: http://localhost:11235
      api_token: gobbler-local-token
```

### Provider-Specific Configuration

#### whisper-local

```yaml
providers:
  transcription:
    default: whisper-local
    whisper-local:
      model: small          # tiny, base, small, medium, large
      device: auto          # auto, cpu, cuda, mps
```

#### docling

```yaml
providers:
  document:
    default: docling
    docling:
      service_url: http://localhost:5001
      timeout: 120          # Request timeout in seconds
```

#### crawl4ai

```yaml
providers:
  webpage:
    default: crawl4ai
    crawl4ai:
      service_url: http://localhost:11235
      api_token: gobbler-local-token
```

### Environment Variables

Provider configuration can also be set via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GOBBLER_WHISPER_MODEL` | Default Whisper model | `small` |
| `GOBBLER_DOCLING_URL` | Docling service URL | `http://localhost:5001` |
| `GOBBLER_CRAWL4AI_URL` | Crawl4AI service URL | `http://localhost:11235` |
| `OPENAI_API_KEY` | OpenAI API key (for future openai-whisper provider) | - |

## CLI Usage

### List Providers

```bash
# List all providers
gobbler providers list

# Filter by category
gobbler providers list --category transcription
gobbler providers list -c document

# JSON output
gobbler providers list --format json
```

**Example output:**

```
All Providers
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category      ┃ Name           ┃ Description                           ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ document      │ docling        │ Docling document conversion provider  │
│ transcription │ whisper-local  │ Local transcription using faster-wh...│
│ webpage       │ crawl4ai       │ Crawl4AI web page conversion provider │
└───────────────┴────────────────┴───────────────────────────────────────┘
```

### Get Provider Info

```bash
# Get detailed provider information
gobbler providers info transcription whisper-local
gobbler providers info document docling

# JSON output
gobbler providers info transcription whisper-local --format json
```

**Example output:**

```
Provider: whisper-local

  Category:    transcription
  Name:        whisper-local
  Class:       WhisperLocalProvider
  Module:      gobbler_core.providers.transcription.whisper

Description:

  Local transcription provider using faster-whisper.

  Uses the faster-whisper library with automatic CoreML acceleration
  on M-series Macs. Models are cached globally to avoid reloading.
```

### Using --provider Flag

Override the default provider for any conversion command:

```bash
# Audio transcription with specific provider
gobbler audio recording.mp3 --provider whisper-local

# Document conversion (provider override)
gobbler document report.pdf --provider docling

# Webpage conversion (provider override)
gobbler webpage "https://example.com" --provider crawl4ai
```

!!! note "Provider availability"
    The `--provider` flag is currently in development. Provider selection
    is determined by the configuration file default settings.

## Provider Comparison

### Local vs API-Based Providers

| Aspect | Local Providers | API-Based Providers |
|--------|-----------------|---------------------|
| **Privacy** | Data stays local | Data sent to external service |
| **Cost** | Hardware cost only | Per-request pricing |
| **Speed** | Depends on hardware | Generally consistent |
| **Reliability** | No network dependency | Requires internet |
| **Setup** | Install dependencies | API key only |
| **Model updates** | Manual updates | Automatic |

### When to Use Each

**Use local providers (whisper-local, docling, crawl4ai) when:**
- Data privacy is critical
- Processing large volumes (cost savings)
- Working offline
- Consistent latency is needed

**Use API-based providers when:**
- No local hardware for processing
- Occasional use (simpler setup)
- Need latest model improvements automatically
- Don't want to manage Docker services

## Creating Custom Providers

Gobbler's provider system is extensible. To create a custom provider:

### 1. Implement the Base Class

```python
from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

class MyTranscriptionProvider(TranscriptionProvider):
    """Custom transcription provider using MyService."""

    @property
    def name(self) -> str:
        return "my-provider"

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options,
    ) -> TranscriptionResult:
        # Your implementation here
        return TranscriptionResult(
            text="transcribed text",
            segments=[],
            language="en",
            duration=120.0,
        )

    def supports_format(self, file_extension: str) -> bool:
        return file_extension.lower() in {".mp3", ".wav"}
```

### 2. Register with the Registry

```python
from gobbler_core.providers.registry import ProviderRegistry

# At module load time
ProviderRegistry.register("transcription", "my-provider", MyTranscriptionProvider)
```

### 3. Add Configuration

```yaml
providers:
  transcription:
    default: my-provider
    my-provider:
      api_key: ${MY_API_KEY}
      endpoint: https://api.myservice.com
```

For detailed implementation guidance, see [Contributing](contributing.md).

## Architecture

The provider abstraction uses a registry pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                     ProviderRegistry                         │
├─────────────────────────────────────────────────────────────┤
│  register(category, name, provider_class)                   │
│  create(category, name, **kwargs) -> Provider               │
│  list_providers(category) -> list[str]                      │
│  get_provider_info(category, name) -> dict                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ transcription │     │   document    │     │   webpage     │
├───────────────┤     ├───────────────┤     ├───────────────┤
│ whisper-local │     │   docling     │     │   crawl4ai    │
└───────────────┘     └───────────────┘     └───────────────┘
```

### Base Classes

Each category has an abstract base class defining the interface:

| Category | Base Class | Key Method |
|----------|------------|------------|
| `transcription` | `TranscriptionProvider` | `transcribe(audio_path, language)` |
| `document` | `DocumentProvider` | `convert(file_path, ocr)` |
| `webpage` | `WebPageProvider` | `fetch(url, timeout)` |

### Result Types

Each category returns a standardized result type:

- `TranscriptionResult` - text, segments, language, duration
- `DocumentResult` - markdown, pages, metadata
- `WebPageResult` - markdown, title, url, links

See [Architecture](ARCHITECTURE.md#provider-layer) for implementation details.
