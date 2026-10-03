import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from models import (
    VideoMetadata,
    VideoPlatform,
    VideoProcessingStatus,
    VideoProcessRequest,
    VideoProcessResponse,
)

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
    description="Validates URL, constructs video metadata, and transitions status to ACCEPTED for future transcript extraction.",
)
def process_video(request: VideoProcessRequest):
    """
    Endpoint to receive, validate, and initialize metadata for educational videos.
    Assigns the initial lifecycle state of ACCEPTED.
    """
    platform, video_id = detect_platform(request.url)
    now = datetime.now(timezone.utc).isoformat()

    # Instantiate the structured VideoMetadata model
    metadata = VideoMetadata(
        id=video_id,
        url=request.url,
        platform=platform,
        title=None,  # Reserved for metadata/oEmbed title extraction in future milestone
        status=VideoProcessingStatus.ACCEPTED,
        created_at=now,
        updated_at=now,
        error_message=None,
    )

    return VideoProcessResponse(
        status=VideoProcessingStatus.ACCEPTED,
        message="Video URL validated and registered. Metadata initialized in ACCEPTED state.",
        video=metadata,
    )
