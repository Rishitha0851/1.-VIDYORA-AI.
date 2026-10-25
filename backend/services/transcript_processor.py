"""
VIDYORA AI - Transcript Processing and Chunking Service

Provides deterministic text cleaning, artifact stripping, and contextual
chunking for video transcripts with exact source timestamp preservation.
"""

import re
from typing import List, Tuple

from models import TranscriptChunk, TranscriptSegment

# Regex patterns for non-speech noise annotations commonly found in captions
NOISE_PATTERN = re.compile(
    r"\[(?:music|applause|laughter|cheering|silence|inaudible|giggles|groan|sigh)\]"
    r"|\((?:music|applause|laughter|cheering|silence|inaudible)\)"
    r"|[♪♫#]+",
    re.IGNORECASE,
)

# Common typographical replacements
APOSTROPHE_PATTERN = re.compile(r"[’‘`]")
DOUBLE_QUOTE_PATTERN = re.compile(r"[“”]")
WHITESPACE_PATTERN = re.compile(r"\s+")
SENTENCE_END_PATTERN = re.compile(r"[.!?][\"')\]]?$")


def clean_segment_text(raw_text: str) -> str:
    """
    Normalizes transcript segment text while preserving original meaning.
    
    Operations:
      1. Strips non-speech audio markers ([Music], [Applause], ♪, etc.).
      2. Normalizes directional quotes and apostrophes.
      3. Collapses tabs, newlines, and multiple spaces into a single space.
      4. Strips leading and trailing whitespace.
    """
    if not raw_text:
        return ""

    # 1. Remove non-speech audio markers
    cleaned = NOISE_PATTERN.sub(" ", raw_text)

    # 2. Standardize quotation marks and apostrophes
    cleaned = APOSTROPHE_PATTERN.sub("'", cleaned)
    cleaned = DOUBLE_QUOTE_PATTERN.sub('"', cleaned)

    # 3. Collapse multiple whitespace characters into a single space
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned).strip()

    return cleaned


def clean_segments(raw_segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
    """
    Normalizes a list of raw segments, stripping noise markers and safely
    dropping segments that contain no meaningful speech content.
    
    Preserves original timestamps (`start` and `duration`) for all retained segments.
    """
    cleaned_list: List[TranscriptSegment] = []

    for seg in raw_segments:
        cleaned_text = clean_segment_text(seg.text)
        # Drop segments that contain no audible text after cleaning
        if not cleaned_text:
            continue

        # Guard against negative durations
        safe_duration = max(0.0, round(seg.duration, 2))
        safe_start = max(0.0, round(seg.start, 2))

        cleaned_list.append(
            TranscriptSegment(
                text=cleaned_text,
                start=safe_start,
                duration=safe_duration,
            )
        )

    return cleaned_list


def is_sentence_boundary(text: str) -> bool:
    """Checks whether the text ends with a sentence boundary (. ! ?)."""
    return bool(SENTENCE_END_PATTERN.search(text.strip()))


def chunk_segments(
    video_id: str,
    segments: List[TranscriptSegment],
    target_words: int = 200,
    max_words: int = 350,
    target_duration_sec: float = 90.0,
    max_duration_sec: float = 180.0,
) -> List[TranscriptChunk]:
    """
    Groups contiguous cleaned segments into deterministic, contextual chunks.
    
    Design Rules:
      - Uses target ranges (150–250 words / 60–120s) as preferred bounds.
      - Prefers breaking at natural sentence boundaries (. ? !) near target size.
      - Enforces hard upper bounds (max_words=350, max_duration=180s) to prevent
        unbounded chunks when speech lacks punctuation (common in ASR).
      - Never splits an individual segment across chunks.
      - Indexes segment_start_index and segment_end_index as zero-based,
        inclusive indices into the provided `segments` list.
      - Accurately computes duration = end_time - start_time.
    """
    if not segments:
        return []

    chunks: List[TranscriptChunk] = []
    chunk_index = 0

    current_segments: List[TranscriptSegment] = []
    current_start_idx = 0
    current_word_count = 0

    for idx, seg in enumerate(segments):
        seg_words = len(seg.text.split())
        current_segments.append(seg)
        current_word_count += seg_words

        # Compute current time span from start of chunk to end of current segment
        chunk_start = current_segments[0].start
        chunk_end = max(s.start + s.duration for s in current_segments)
        chunk_duration = chunk_end - chunk_start

        reached_target = (
            current_word_count >= target_words or chunk_duration >= target_duration_sec
        )
        is_sentence_end = is_sentence_boundary(seg.text)
        exceeded_max = (
            current_word_count >= max_words or chunk_duration >= max_duration_sec
        )
        is_last_segment = (idx == len(segments) - 1)

        # Decide whether to close this chunk:
        # 1. We reached target and hit a sentence boundary.
        # 2. We exceeded maximum allowable thresholds (preventing runaway chunks).
        # 3. We have reached the final segment of the video transcript.
        should_close = (
            (reached_target and is_sentence_end)
            or exceeded_max
            or is_last_segment
        )

        if should_close and current_segments:
            chunk_text = " ".join(s.text for s in current_segments).strip()
            actual_words = len(chunk_text.split())

            start_time = round(current_segments[0].start, 2)
            end_time = round(max(s.start + s.duration for s in current_segments), 2)
            # Ensure duration is strictly non-negative
            duration = round(max(0.0, end_time - start_time), 2)

            chunks.append(
                TranscriptChunk(
                    chunk_id=f"{video_id}_chunk_{chunk_index:03d}",
                    chunk_index=chunk_index,
                    video_id=video_id,
                    text=chunk_text,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    word_count=actual_words,
                    segment_start_index=current_start_idx,
                    segment_end_index=idx,
                )
            )

            # Advance state for next chunk
            chunk_index += 1
            current_segments = []
            current_start_idx = idx + 1
            current_word_count = 0

    return chunks


def process_transcript_data(
    video_id: str,
    raw_segments: List[TranscriptSegment],
) -> Tuple[List[TranscriptSegment], List[TranscriptChunk]]:
    """
    End-to-end pipeline: cleans raw segments, generates knowledge chunks,
    and returns (cleaned_segments, chunks).
    """
    cleaned = clean_segments(raw_segments)
    chunks = chunk_segments(video_id, cleaned)
    return cleaned, chunks
