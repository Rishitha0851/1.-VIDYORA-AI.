import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator, computed_field


# ---------------------------------------------------------------------------
# Enums: Video Platform and Processing Lifecycle States
# ---------------------------------------------------------------------------

class VideoPlatform(str, Enum):
    """Supported video platforms for VIDYORA AI knowledge extraction."""
    YOUTUBE = "youtube"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class VideoProcessingStatus(str, Enum):
    """
    Explicit lifecycle states for video processing.
    
    Valid Transitions:
      SUBMITTED -> VALIDATING -> ACCEPTED -> PROCESSING -> COMPLETED
                                         \-> FAILED     \-> FAILED
    """
    SUBMITTED = "submitted"      # Initial URL receipt
    VALIDATING = "validating"    # Syntax and accessibility checks in progress
    ACCEPTED = "accepted"        # Validated and registered; queued for transcript extraction
    PROCESSING = "processing"    # Downstream AI / transcript extraction actively running
    COMPLETED = "completed"      # Notes, chunks, and assessments successfully generated
    FAILED = "failed"            # Error encountered during validation or extraction


# ---------------------------------------------------------------------------
# Pydantic Schemas / Data Models
# ---------------------------------------------------------------------------

class TranscriptSegment(BaseModel):
    """
    A single time-aligned caption snippet from the educational video.
    
    Fields:
      - text: Spoken text content within this interval.
      - start: Timestamp in seconds indicating when this segment begins.
      - duration: Duration of this segment in seconds.
    """
    text: str
    start: float
    duration: float


class VideoTranscript(BaseModel):
    """
    Structured transcript data representing the spoken educational content.
    
    Fields:
      - video_id: Unique video identifier.
      - language: Language code (e.g., 'en').
      - is_generated: True if automatically generated (ASR), False if manual creator captions.
      - full_text: Continuous aggregated spoken text.
      - segments: Ordered list of time-aligned caption segments.
      - segment_count: Total number of transcript segments.
    """
    video_id: str
    language: str
    is_generated: bool
    full_text: str
    segments: list[TranscriptSegment]
    segment_count: int


class VideoMetadata(BaseModel):
    """
    Structured metadata representing an educational video entity in VIDYORA AI.
    
    Fields:
      - id: Unique video identifier (e.g. YouTube 11-char ID or generated token).
      - url: The original normalized video URL.
      - platform: Detected platform (e.g., youtube, direct, unknown).
      - title: Video title (extracted via YouTube metadata or oEmbed).
      - status: Current lifecycle state.
      - created_at: UTC timestamp when the video was first submitted.
      - updated_at: UTC timestamp when metadata/status was last modified.
      - error_message: Descriptive explanation if status is FAILED.
      - transcript: Structured time-aligned transcript if successfully extracted.
    """
    id: str
    url: str
    platform: VideoPlatform
    title: Optional[str] = None
    status: VideoProcessingStatus
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    transcript: Optional[VideoTranscript] = None


class VideoProcessRequest(BaseModel):
    """Request payload for submitting an educational video URL."""
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Video URL cannot be empty.")

        # Validate URL scheme (http/https) and standard hostname structure
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
    """
    Structured API response returned to the client upon video submission.
    Encapsulates lifecycle status, user message, and full video metadata.
    Includes backward-compatible computed fields for legacy clients.
    """
    status: VideoProcessingStatus
    message: str
    video: VideoMetadata

    @computed_field
    @property
    def video_url(self) -> str:
        return self.video.url

    @computed_field
    @property
    def video_id(self) -> Optional[str]:
        return self.video.id

    @computed_field
    @property
    def received_at(self) -> str:
        return self.video.created_at
