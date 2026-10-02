import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# 1. Initialize the FastAPI application instance
app = FastAPI(
    title="VIDYORA AI API",
    description="Backend services for VIDYORA AI - AI-powered adaptive video learning platform",
    version="0.1.0",
)

# 2. Configure CORS (Cross-Origin Resource Sharing)
# The React development server runs at http://localhost:5173 or http://127.0.0.1:5173.
# We explicitly whitelist our local frontend origins.
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
# Pydantic Schemas / Request & Response Models
# ---------------------------------------------------------------------------

class VideoProcessRequest(BaseModel):
    """Request payload for submitting an educational video URL."""
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Video URL cannot be empty.")

        # Validate URL scheme and structure (http:// or https://)
        url_pattern = re.compile(
            r'^(https?:\/\/)'                     # http:// or https://
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'     # domain name
            r'(:\d+)?(\/.*)?$',                    # optional port and path
            re.IGNORECASE
        )
        if not url_pattern.match(trimmed):
            raise ValueError("Please provide a valid HTTP or HTTPS URL (e.g., https://www.youtube.com/watch?v=...).")

        return trimmed


class VideoProcessResponse(BaseModel):
    """Structured response confirming receipt and validation of the video URL."""
    status: str
    message: str
    video_url: str
    received_at: str
    video_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID if present in the URL."""
    patterns = [
        r"(?:v=|\/embed\/|\/watch\?v=|\/shorts\/|^youtu\.be\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"(?:v%3D)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


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
    description="Validates and registers an educational video URL for downstream transcript extraction and AI analysis.",
)
def process_video(request: VideoProcessRequest):
    """
    Endpoint to receive and validate educational video URLs.
    Validates input format and returns structured receipt acknowledgement.
    (Transcript extraction and AI processing will be executed in subsequent phases).
    """
    video_id = extract_video_id(request.url)

    return VideoProcessResponse(
        status="received",
        message="Video URL successfully received and queued for transcript extraction.",
        video_url=request.url,
        video_id=video_id,
        received_at=datetime.now(timezone.utc).isoformat(),
    )
