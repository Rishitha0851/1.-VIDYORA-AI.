"""
VIDYORA AI - Transcript Extraction Service

Encapsulates all logic for extracting, parsing, and structuring time-aligned
spoken transcripts from YouTube and educational video platforms.
"""

import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Optional

import yt_dlp

from models import TranscriptSegment, VideoTranscript

logger = logging.getLogger(__name__)


@dataclass
class TranscriptExtractionResult:
    """
    Result container for transcript extraction operations.
    """
    success: bool
    title: Optional[str] = None
    transcript: Optional[VideoTranscript] = None
    error_message: Optional[str] = None


def extract_youtube_transcript(video_id: str, url: str) -> TranscriptExtractionResult:
    """
    Extracts structured time-aligned transcript and video title from YouTube.
    
    Uses yt-dlp with mobile client emulation to reliably access public caption
    tracks (manual and auto-generated) without requiring API keys or being
    blocked by desktop bot checks.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return TranscriptExtractionResult(
                    success=False,
                    error_message="Could not retrieve video information from YouTube.",
                )

            title = info.get('title')
            subtitles = info.get('subtitles') or {}
            auto_captions = info.get('automatic_captions') or {}

            # Prioritize manual subtitles over auto-generated captions
            is_generated = False
            selected_track = None
            selected_lang = 'en'

            # 1. Search for manual English captions
            for lang_code in ['en', 'en-US', 'en-GB']:
                if lang_code in subtitles:
                    selected_track = subtitles[lang_code]
                    selected_lang = lang_code
                    is_generated = False
                    break

            # 2. Fall back to any manual subtitle track
            if not selected_track and subtitles:
                selected_lang = next(iter(subtitles.keys()))
                selected_track = subtitles[selected_lang]
                is_generated = False

            # 3. Fall back to auto-generated English captions
            if not selected_track:
                for lang_code in ['en', 'en-US', 'en-GB']:
                    if lang_code in auto_captions:
                        selected_track = auto_captions[lang_code]
                        selected_lang = lang_code
                        is_generated = True
                        break

            # 4. Fall back to any auto-generated caption track
            if not selected_track and auto_captions:
                selected_lang = next(iter(auto_captions.keys()))
                selected_track = auto_captions[selected_lang]
                is_generated = True

            if not selected_track:
                return TranscriptExtractionResult(
                    success=False,
                    title=title,
                    error_message="No transcript or captions available for this video.",
                )

            # Find json3 format URL (contains structured millisecond timestamps)
            json3_entry = next((f for f in selected_track if f.get('ext') == 'json3'), None)
            if not json3_entry or 'url' not in json3_entry:
                # If json3 isn't available, check for vtt / other formats
                return TranscriptExtractionResult(
                    success=False,
                    title=title,
                    error_message="Caption format incompatible with timestamp extraction.",
                )

            # Fetch and parse the json3 caption stream
            caption_req = urllib.request.Request(
                json3_entry['url'],
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(caption_req, timeout=10) as resp:
                caption_json = json.loads(resp.read().decode('utf-8'))

            events = caption_json.get('events') or []
            segments: list[TranscriptSegment] = []

            for event in events:
                segs = event.get('segs')
                if not segs:
                    continue
                # Assemble text parts within this event
                text_part = ''.join(s.get('utf8', '') for s in segs).replace('\n', ' ').strip()
                if not text_part:
                    continue

                start_sec = round(event.get('tStartMs', 0) / 1000.0, 2)
                duration_sec = round(event.get('dDurationMs', 0) / 1000.0, 2)

                segments.append(TranscriptSegment(
                    text=text_part,
                    start=start_sec,
                    duration=duration_sec,
                ))

            if not segments:
                return TranscriptExtractionResult(
                    success=False,
                    title=title,
                    error_message="Captions were present but contained no readable text segments.",
                )

            full_text = ' '.join(s.text for s in segments)

            transcript = VideoTranscript(
                video_id=video_id,
                language=selected_lang,
                is_generated=is_generated,
                full_text=full_text,
                segments=segments,
                segment_count=len(segments),
            )

            return TranscriptExtractionResult(
                success=True,
                title=title,
                transcript=transcript,
            )

    except yt_dlp.utils.DownloadError as de:
        error_str = str(de)
        if "unavailable" in error_str.lower():
            msg = "This video is unavailable, private, or does not exist."
        elif "sign in" in error_str.lower():
            msg = "YouTube restricted access to this video. Sign-in required."
        else:
            msg = "Failed to access YouTube video. Please verify the URL."
        return TranscriptExtractionResult(success=False, error_message=msg)

    except Exception as e:
        logger.exception("Unexpected error during transcript extraction for %s", video_id)
        return TranscriptExtractionResult(
            success=False,
            error_message=f"Transcript extraction encountered an error: {str(e)}"
        )
