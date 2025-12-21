"""Conversion endpoints for single-file conversions."""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from gobbler_core.converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_youtube_to_markdown,
)
from gobbler_mcp.config import get_config
from gobbler_mcp.converters import convert_webpage_with_selector
from gobbler_mcp.utils import get_metrics_callback, save_markdown_file, validate_output_path

from ..auth import verify_api_key
from ..models import (
    AudioConvertRequest,
    ConversionMetadata,
    ConversionResponse,
    ConversionType,
    DocumentConvertRequest,
    WebpageConvertRequest,
    YouTubeConvertRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/convert", tags=["convert"])


@router.post("/youtube", response_model=ConversionResponse)
async def convert_youtube(
    request: YouTubeConvertRequest,
    api_key: str = Depends(verify_api_key),
) -> ConversionResponse:
    """Convert YouTube video to markdown.

    Extract YouTube video transcript and convert to clean markdown format.
    Uses official YouTube transcript API for fast, accurate results.

    Args:
        request: YouTube conversion parameters
        api_key: API key for authentication

    Returns:
        ConversionResponse with markdown content or error

    Raises:
        HTTPException: If conversion fails
    """
    try:
        # Convert to markdown
        markdown, metadata = await convert_youtube_to_markdown(
            video_url=str(request.video_url),
            include_timestamps=request.include_timestamps,
            language=request.language,
        )

        # Handle output file
        file_path = None
        if request.output_file:
            error = validate_output_path(request.output_file)
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

            success = await save_markdown_file(request.output_file, markdown)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to write file: {request.output_file}",
                )
            file_path = request.output_file

        return ConversionResponse(
            success=True,
            markdown=markdown if not file_path else None,
            metadata=ConversionMetadata(
                source=str(request.video_url),
                conversion_type=ConversionType.YOUTUBE,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            ),
            file_path=file_path,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except VideoUnavailable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found: The video may be private, deleted, or the URL is incorrect.",
        )
    except TranscriptsDisabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transcript available for this video.",
        )
    except NoTranscriptFound as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript not available in language '{request.language}': {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in convert_youtube: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract transcript: {str(e)}",
        )


@router.post("/audio", response_model=ConversionResponse)
async def convert_audio(
    request: AudioConvertRequest,
    api_key: str = Depends(verify_api_key),
) -> ConversionResponse:
    """Transcribe audio/video file to markdown.

    Transcribe audio and video files to text using OpenAI Whisper.
    Supports multiple audio/video formats with automatic format detection.

    Args:
        request: Audio conversion parameters
        api_key: API key for authentication

    Returns:
        ConversionResponse with markdown content or error

    Raises:
        HTTPException: If conversion fails
    """
    try:
        # Convert to markdown
        markdown, metadata = await convert_audio_to_markdown(
            file_path=request.file_path,
            model=request.model,
            language=request.language,
        )

        # Handle output file
        file_path = None
        if request.output_file:
            error = validate_output_path(request.output_file)
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

            success = await save_markdown_file(request.output_file, markdown)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to write file: {request.output_file}",
                )
            file_path = request.output_file

        return ConversionResponse(
            success=True,
            markdown=markdown if not file_path else None,
            metadata=ConversionMetadata(
                source=request.file_path,
                conversion_type=ConversionType.AUDIO,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            ),
            file_path=file_path,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in convert_audio: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transcribe audio: {str(e)}",
        )


@router.post("/document", response_model=ConversionResponse)
async def convert_document(
    request: DocumentConvertRequest,
    api_key: str = Depends(verify_api_key),
) -> ConversionResponse:
    """Convert document to markdown.

    Convert document files (PDF, DOCX, PPTX, XLSX) to clean markdown format.
    Preserves structure including tables, headings, lists, and code blocks.

    Args:
        request: Document conversion parameters
        api_key: API key for authentication

    Returns:
        ConversionResponse with markdown content or error

    Raises:
        HTTPException: If conversion fails
    """
    try:
        # Get service configuration
        config = get_config()
        service_url = config.get_service_url("docling")
        metrics_callback = get_metrics_callback()

        # Convert to markdown
        markdown, metadata = await convert_document_to_markdown(
            file_path=request.file_path,
            enable_ocr=request.enable_ocr,
            service_url=service_url,
            metrics_callback=metrics_callback,
        )

        # Handle output file
        file_path = None
        if request.output_file:
            error = validate_output_path(request.output_file)
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

            success = await save_markdown_file(request.output_file, markdown)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to write file: {request.output_file}",
                )
            file_path = request.output_file

        return ConversionResponse(
            success=True,
            markdown=markdown if not file_path else None,
            metadata=ConversionMetadata(
                source=request.file_path,
                conversion_type=ConversionType.DOCUMENT,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            ),
            file_path=file_path,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        error_msg = str(e)
        if "not yet implemented" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docling service unavailable",
        )
    except Exception as e:
        logger.error(f"Unexpected error in convert_document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert document: {str(e)}",
        )


@router.post("/webpage", response_model=ConversionResponse)
async def convert_webpage(
    request: WebpageConvertRequest,
    api_key: str = Depends(verify_api_key),
) -> ConversionResponse:
    """Convert webpage to markdown.

    Convert web page content to clean markdown format. Fetches HTML via Crawl4AI
    and converts to structured markdown, preserving document structure.

    Args:
        request: Webpage conversion parameters
        api_key: API key for authentication

    Returns:
        ConversionResponse with markdown content or error

    Raises:
        HTTPException: If conversion fails
    """
    try:
        # Validate selector combination
        if request.css_selector and request.xpath:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot specify both css_selector and xpath",
            )

        # Use selector-based conversion if selectors provided
        if request.css_selector or request.xpath:
            markdown, metadata = await convert_webpage_with_selector(
                url=str(request.url),
                css_selector=request.css_selector,
                xpath=request.xpath,
                include_images=request.include_images,
                extract_links=request.extract_links,
                session_id=request.session_id,
                bypass_cache=request.bypass_cache,
                timeout=request.timeout,
            )
        else:
            # Basic webpage conversion
            markdown, metadata = await convert_webpage_to_markdown(
                url=str(request.url),
                include_images=request.include_images,
                timeout=request.timeout,
            )

        # Handle output file
        file_path = None
        if request.output_file:
            error = validate_output_path(request.output_file)
            if error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

            success = await save_markdown_file(request.output_file, markdown)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to write file: {request.output_file}",
                )
            file_path = request.output_file

        return ConversionResponse(
            success=True,
            markdown=markdown if not file_path else None,
            metadata=ConversionMetadata(
                source=str(request.url),
                conversion_type=ConversionType.WEBPAGE,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            ),
            file_path=file_path,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawl4AI service unavailable",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Connection timeout after {request.timeout} seconds",
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Page not found at {request.url}",
            )
        elif status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Server error at {request.url}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"HTTP {status_code}: Failed to fetch {request.url}",
            )
    except RuntimeError as e:
        error_msg = str(e)
        if "not yet implemented" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawl4AI error: {error_msg}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in convert_webpage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert webpage: {str(e)}",
        )
