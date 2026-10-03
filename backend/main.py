import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from models import (
    TranscriptSegment,
    VideoMetadata,
    VideoPlatform,
    VideoProcessingStatus,
    VideoProcessRequest,
    VideoProcessResponse,
    VideoTranscript,
)
from services.transcript_service import extract_youtube_transcript

# 1. Initialize the FastAPI application instance
app = FastAPI(
    title="VIDYORA AI API",
    description="Backend services for VIDYORA AI - AI-powered adaptive video learning platform",
    version="0.1.0",
)

# 2. Configure CORS (Cross-Origin Resource Sharing)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Only allow requests from our frontend
    allow_credentials=True,      # Allow cookies / authentication headers if needed later
    allow_methods=["*"],         # Allow all standard HTTP methods (GET, POST, etc.)
    allow_headers=["*"],         # Allow all standard request headers (Content-Type, etc.)
)


# ---------------------------------------------------------------------------
# Helper Functions: Platform Detection and Identifier Resolution
# ---------------------------------------------------------------------------

def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube 11-character video ID if present in the URL."""
    patterns = [
        r"(?:v=|\/embed\/|\/watch\?v=|\/shorts\/|^youtu\.be\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"(?:v%3D)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def detect_platform(url: str) -> tuple[VideoPlatform, str]:
    """
    Detect video platform from URL and generate/extract a unique identifier.
    Returns a tuple of (VideoPlatform, video_id).
    """
    # 1. Check for YouTube
    youtube_id = extract_youtube_id(url)
    if youtube_id:
        return VideoPlatform.YOUTUBE, youtube_id

    # 2. Check for Direct Video Stream / File extensions
    if re.search(r'\.(mp4|webm|mkv|mov|avi)(\?.*)?$', url, re.IGNORECASE):
        file_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
        return VideoPlatform.DIRECT, f"vid_{file_hash}"

    # 3. Fallback for generic educational web sources
    web_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
    return VideoPlatform.UNKNOWN, f"src_{web_hash}"


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

# 3. Root Endpoint (GET /)
@app.get("/", summary="Root API info", tags=["General"])
def read_root():
    """Welcome endpoint providing basic API metadata."""
    return {
        "message": "Welcome to VIDYORA AI API",
        "status": "online",
        "docs_url": "/docs",
    }


# 4. Health Check Endpoint (GET /health)
@app.get("/health", summary="Health check", tags=["General"])
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": "VIDYORA AI Backend",
        "version": "0.1.0",
    }


# 5. Video Processing Submission Endpoint (POST /api/videos/process)
@app.post(
    "/api/videos/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit video URL for processing",
    tags=["Videos"],
    description="Validates URL, constructs video metadata, and executes transcript extraction for YouTube educational videos.",
)
def process_video(request: VideoProcessRequest):
    """
    Endpoint to receive, validate, and process educational videos.
    Extracts time-aligned spoken transcripts for YouTube videos, assigning
    COMPLETED or FAILED lifecycle states based on caption availability.
    """
    platform, video_id = detect_platform(request.url)
    now = datetime.now(timezone.utc).isoformat()

    # If YouTube, execute transcript extraction pipeline
    if platform == VideoPlatform.YOUTUBE:
        result = extract_youtube_transcript(video_id, request.url)
        updated_at = datetime.now(timezone.utc).isoformat()

        if result.success and result.transcript:
            metadata = VideoMetadata(
                id=video_id,
                url=request.url,
                platform=platform,
                title=result.title,
                status=VideoProcessingStatus.COMPLETED,
                created_at=now,
                updated_at=updated_at,
                error_message=None,
                transcript=result.transcript,
            )
            return VideoProcessResponse(
                status=VideoProcessingStatus.COMPLETED,
                message=f"Transcript extracted successfully ({result.transcript.segment_count} segments, {len(result.transcript.full_text.split())} words).",
                video=metadata,
            )
        else:
            metadata = VideoMetadata(
                id=video_id,
                url=request.url,
                platform=platform,
                title=result.title,
                status=VideoProcessingStatus.FAILED,
                created_at=now,
                updated_at=updated_at,
                error_message=result.error_message,
                transcript=None,
            )
            return VideoProcessResponse(
                status=VideoProcessingStatus.FAILED,
                message=result.error_message or "Transcript extraction failed.",
                video=metadata,
            )

    # Fallback for direct stream or unknown web sources
    metadata = VideoMetadata(
        id=video_id,
        url=request.url,
        platform=platform,
        title=None,
        status=VideoProcessingStatus.ACCEPTED,
        created_at=now,
        updated_at=now,
        error_message=None,
        transcript=None,
    )

    return VideoProcessResponse(
        status=VideoProcessingStatus.ACCEPTED,
        message="Video URL validated and registered. Automated transcript extraction is currently enabled for YouTube.",
        video=metadata,
    )

