"""File directory batch processing."""

import logging
from pathlib import Path
from typing import List, Optional

from ..converters.audio import convert_audio_to_markdown
from ..converters.document import convert_document_to_markdown
from ..utils import save_markdown_file
from .batch_manager import BatchProcessor
from .models import BatchItem, BatchResult, BatchSummary

logger = logging.getLogger(__name__)

# Supported file extensions
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".avi", ".mkv", ".flac", ".ogg", ".webm"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}


def scan_directory(
    input_dir: str,
    pattern: str = "*",
    recursive: bool = False,
    file_type: str = "audio",
) -> List[Path]:
    """
    Scan directory for files matching pattern.

    Args:
        input_dir: Directory to scan
        pattern: Glob pattern (e.g., '*.mp3', '**/*.pdf')
        recursive: Search subdirectories
        file_type: Type of files to find ('audio' or 'document')

    Returns:
        List of matching file paths
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise ValueError(f"Directory not found: {input_dir}")

    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    # Determine valid extensions
    if file_type == "audio":
        valid_extensions = AUDIO_EXTENSIONS
    elif file_type == "document":
        valid_extensions = DOCUMENT_EXTENSIONS
    else:
        raise ValueError(f"Invalid file_type: {file_type}")

    # Scan directory
    if recursive:
        glob_pattern = f"**/{pattern}"
    else:
        glob_pattern = pattern

    files = []
    for file_path in input_path.glob(glob_pattern):
        if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
            files.append(file_path)

    logger.info(f"Found {len(files)} {file_type} files in {input_dir}")
    return sorted(files)


async def process_audio_batch(
    input_dir: str,
    output_dir: Optional[str] = None,
    model: str = "small",
    language: str = "auto",
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 2,
    skip_existing: bool = True,
    batch_id: Optional[str] = None,
) -> BatchSummary:
    """
    Process directory of audio/video files in batch.

    Args:
        input_dir: Directory containing audio/video files
        output_dir: Directory for transcripts (default: same as input_dir)
        model: Whisper model size
        language: Audio language code or 'auto'
        pattern: Glob pattern for file matching
        recursive: Search subdirectories
        concurrency: Number of concurrent transcriptions
        skip_existing: Skip files with existing transcripts
        batch_id: Optional batch ID

    Returns:
        BatchSummary with processing results
    """
    # Default output to input directory
    output_path = Path(output_dir) if output_dir else Path(input_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Scan for audio files
    files = scan_directory(input_dir, pattern, recursive, file_type="audio")

    if not files:
        raise ValueError(f"No audio/video files found in {input_dir}")

    # Convert to BatchItems
    items = []
    for file_path in files:
        # Generate output filename
        output_file = output_path / f"{file_path.stem}.md"

        items.append(
            BatchItem(
                id=file_path.name,
                source=str(file_path),
                metadata={
                    "expected_output": str(output_file),
                    "file_size_mb": file_path.stat().st_size / 1024 / 1024,
                },
            )
        )

    # Process function for single audio file
    async def process_audio(item: BatchItem) -> BatchResult:
        """Process single audio file."""
        try:
            file_path = Path(item.source)
            expected_path = Path(item.metadata["expected_output"])

            # Check if should skip
            if skip_existing and expected_path.exists():
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="skipped",
                    metadata={"reason": "File already exists"},
                )

            # Convert to markdown
            markdown, metadata = await convert_audio_to_markdown(
                file_path=str(file_path),
                model=model,
                language=language,
            )

            # Get unique output path
            output_file = expected_path
            if output_file.exists():
                counter = 1
                while output_file.exists():
                    output_file = expected_path.parent / f"{expected_path.stem}_{counter}.md"
                    counter += 1

            # Save to file
            success = await save_markdown_file(str(output_file), markdown)

            if not success:
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="Failed to write file",
                )

            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=str(output_file),
                metadata={
                    "file_size_mb": item.metadata["file_size_mb"],
                    "word_count": metadata.get("word_count", 0),
                },
            )

        except Exception as e:
            logger.error(f"Error processing audio file {item.source}: {e}")
            return BatchResult(
                item_id=item.id,
                success=False,
                error=str(e),
            )

    # Create batch processor
    processor = BatchProcessor(
        batch_id=batch_id,
        items=items,
        process_fn=process_audio,
        concurrency=concurrency,
        output_dir=str(output_path),
        skip_existing=skip_existing,
        operation_type="audio_batch",
    )

    # Run batch
    summary = await processor.run()

    logger.info(
        f"Batch complete: {summary.successful}/{summary.total_items} successful"
    )

    return summary


async def process_document_batch(
    input_dir: str,
    output_dir: Optional[str] = None,
    enable_ocr: bool = True,
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 3,
    skip_existing: bool = True,
    batch_id: Optional[str] = None,
) -> BatchSummary:
    """
    Process directory of documents in batch.

    Args:
        input_dir: Directory containing documents
        output_dir: Directory for markdown files (default: same as input_dir)
        enable_ocr: Enable OCR for scanned documents
        pattern: Glob pattern for file matching
        recursive: Search subdirectories
        concurrency: Number of concurrent conversions
        skip_existing: Skip documents with existing markdown
        batch_id: Optional batch ID

    Returns:
        BatchSummary with processing results
    """
    # Default output to input directory
    output_path = Path(output_dir) if output_dir else Path(input_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Scan for document files
    files = scan_directory(input_dir, pattern, recursive, file_type="document")

    if not files:
        raise ValueError(f"No document files found in {input_dir}")

    # Convert to BatchItems
    items = []
    for file_path in files:
        # Generate output filename
        output_file = output_path / f"{file_path.stem}.md"

        items.append(
            BatchItem(
                id=file_path.name,
                source=str(file_path),
                metadata={
                    "expected_output": str(output_file),
                    "file_size_mb": file_path.stat().st_size / 1024 / 1024,
                },
            )
        )

    # Process function for single document
    async def process_document(item: BatchItem) -> BatchResult:
        """Process single document file."""
        try:
            file_path = Path(item.source)
            expected_path = Path(item.metadata["expected_output"])

            # Check if should skip
            if skip_existing and expected_path.exists():
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="skipped",
                    metadata={"reason": "File already exists"},
                )

            # Convert to markdown
            markdown, metadata = await convert_document_to_markdown(
                file_path=str(file_path),
                enable_ocr=enable_ocr,
            )

            # Get unique output path
            output_file = expected_path
            if output_file.exists():
                counter = 1
                while output_file.exists():
                    output_file = expected_path.parent / f"{expected_path.stem}_{counter}.md"
                    counter += 1

            # Save to file
            success = await save_markdown_file(str(output_file), markdown)

            if not success:
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="Failed to write file",
                )

            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=str(output_file),
                metadata={
                    "file_size_mb": item.metadata["file_size_mb"],
                    "word_count": metadata.get("word_count", 0),
                },
            )

        except Exception as e:
            logger.error(f"Error processing document {item.source}: {e}")
            return BatchResult(
                item_id=item.id,
                success=False,
                error=str(e),
            )

    # Create batch processor
    processor = BatchProcessor(
        batch_id=batch_id,
        items=items,
        process_fn=process_document,
        concurrency=concurrency,
        output_dir=str(output_path),
        skip_existing=skip_existing,
        operation_type="document_batch",
    )

    # Run batch
    summary = await processor.run()

    logger.info(
        f"Batch complete: {summary.successful}/{summary.total_items} successful"
    )

    return summary
