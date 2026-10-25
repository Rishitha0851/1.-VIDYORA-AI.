"""
VIDYORA AI - Transcript Extraction Service

Encapsulates all logic for extracting, parsing, and structuring time-aligned
spoken transcripts from YouTube and educational video platforms.
Uses a resilient dual-strategy approach: YouTubeTranscriptApi as primary
with YouTube oEmbed for rapid, bot-resilient metadata retrieval, plus
yt-dlp as a robust secondary fallback.
"""

import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

import yt_dlp
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from models import TranscriptSegment, VideoTranscript
from services.transcript_processor import process_transcript_data

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


def fetch_youtube_title_oembed(video_id: str) -> Optional[str]:
    """
    Fetches official video title via YouTube's public oEmbed API.
    Fast, lightweight (~100ms), and not subject to automated bot blocks.
    """
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("title")
    except Exception as e:
        logger.debug("oEmbed title fetch failed for %s: %s", video_id, e)
        return None


def extract_via_transcript_api(video_id: str) -> Optional[tuple[List[TranscriptSegment], str, bool]]:
    """
    Extracts transcript snippets using YouTubeTranscriptApi with priority:
    1. Manual English captions (en, en-US, en-GB)
    2. Auto-generated English captions
    3. Any available transcript track
    Returns tuple of (segments, language_code, is_generated) or None.
    """
    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)

        # 1. Manual English
        selected_track = None
        for t in transcript_list:
            if t.language_code in ("en", "en-US", "en-GB") and not t.is_generated:
                selected_track = t
                break

        # 2. Auto-generated English
        if not selected_track:
            for t in transcript_list:
                if t.language_code in ("en", "en-US", "en-GB"):
                    selected_track = t
                    break

        # 3. Any available track
        if not selected_track:
            selected_track = next(iter(transcript_list), None)

        if not selected_track:
            return None

        raw_snippets = selected_track.fetch()
        segments: List[TranscriptSegment] = []
        for s in raw_snippets:
            clean_text = s.text.replace("\n", " ").strip()
            if clean_text:
                segments.append(
                    TranscriptSegment(
                        text=clean_text,
                        start=round(float(s.start), 2),
                        duration=round(float(s.duration), 2),
                    )
                )

        return segments, selected_track.language_code, selected_track.is_generated

    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception as e:
        logger.warning("YouTubeTranscriptApi extraction error for %s: %s", video_id, e)
        return None


def extract_via_ytdlp(video_id: str, url: str) -> Optional[tuple[Optional[str], List[TranscriptSegment], str, bool]]:
    """
    Secondary fallback using yt-dlp with mobile client emulation.
    """
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            title = info.get("title")
            subtitles = info.get("subtitles") or {}
            auto_captions = info.get("automatic_captions") or {}

            is_generated = False
            selected_track = None
            selected_lang = "en"

            for lang_code in ["en", "en-US", "en-GB"]:
                if lang_code in subtitles:
                    selected_track = subtitles[lang_code]
                    selected_lang = lang_code
                    is_generated = False
                    break

            if not selected_track and subtitles:
                selected_lang = next(iter(subtitles.keys()))
                selected_track = subtitles[selected_lang]
                is_generated = False

            if not selected_track:
                for lang_code in ["en", "en-US", "en-GB"]:
                    if lang_code in auto_captions:
                        selected_track = auto_captions[lang_code]
                        selected_lang = lang_code
                        is_generated = True
                        break

            if not selected_track and auto_captions:
                selected_lang = next(iter(auto_captions.keys()))
                selected_track = auto_captions[selected_lang]
                is_generated = True

            if not selected_track:
                return title, [], selected_lang, is_generated

            json3_entry = next((f for f in selected_track if f.get("ext") == "json3"), None)
            if not json3_entry or "url" not in json3_entry:
                return title, [], selected_lang, is_generated

            caption_req = urllib.request.Request(
                json3_entry["url"],
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(caption_req, timeout=10) as resp:
                caption_json = json.loads(resp.read().decode("utf-8"))

            events = caption_json.get("events") or []
            segments: List[TranscriptSegment] = []
            for event in events:
                segs = event.get("segs")
                if not segs:
                    continue
                text_part = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
                if not text_part:
                    continue
                start_sec = round(event.get("tStartMs", 0) / 1000.0, 2)
                duration_sec = round(event.get("dDurationMs", 0) / 1000.0, 2)
                segments.append(
                    TranscriptSegment(
                        text=text_part,
                        start=start_sec,
                        duration=duration_sec,
                    )
                )

            return title, segments, selected_lang, is_generated

    except Exception as e:
        logger.warning("yt-dlp fallback extraction error for %s: %s", video_id, e)
        return None


def extract_youtube_transcript(video_id: str, url: str) -> TranscriptExtractionResult:
    """
    Extracts structured time-aligned transcript and video title from YouTube.
    Combines oEmbed + YouTubeTranscriptApi with yt-dlp fallback.
    """
    # 1. Fetch title via fast oEmbed
    title = fetch_youtube_title_oembed(video_id)

    # 2. Primary extraction via YouTubeTranscriptApi (avoids 429 timedtext block)
    api_result = extract_via_transcript_api(video_id)
    if api_result and api_result[0]:
        segments, lang, is_generated = api_result
        full_text = " ".join(s.text for s in segments)
        cleaned_segments, chunks = process_transcript_data(video_id, segments)

        transcript = VideoTranscript(
            video_id=video_id,
            language=lang,
            is_generated=is_generated,
            full_text=full_text,
            segments=segments,
            segment_count=len(segments),
            cleaned_segments=cleaned_segments,
            cleaned_segment_count=len(cleaned_segments),
            chunks=chunks,
            chunk_count=len(chunks),
        )

        return TranscriptExtractionResult(
            success=True,
            title=title,
            transcript=transcript,
        )

    # 3. Secondary fallback via yt-dlp
    fallback = extract_via_ytdlp(video_id, url)
    if fallback:
        fb_title, segments, lang, is_generated = fallback
        if not title:
            title = fb_title

        if segments:
            full_text = " ".join(s.text for s in segments)
            cleaned_segments, chunks = process_transcript_data(video_id, segments)

            transcript = VideoTranscript(
                video_id=video_id,
                language=lang,
                is_generated=is_generated,
                full_text=full_text,
                segments=segments,
                segment_count=len(segments),
                cleaned_segments=cleaned_segments,
                cleaned_segment_count=len(cleaned_segments),
                chunks=chunks,
                chunk_count=len(chunks),
            )

            return TranscriptExtractionResult(
                success=True,
                title=title,
                transcript=transcript,
            )

    return TranscriptExtractionResult(
        success=False,
        title=title,
        error_message="No transcript or captions available for this video.",
    )
