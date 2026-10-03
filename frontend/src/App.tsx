import { useState } from 'react'
import WelcomeBanner from './components/WelcomeBanner'
import BackendStatus from './components/BackendStatus'
import VideoInput from './components/VideoInput'

/** Lifecycle processing states supported by VIDYORA AI */
export type VideoProcessingStatus =
  | 'submitted'
  | 'validating'
  | 'accepted'
  | 'processing'
  | 'completed'
  | 'failed'

/** Supported video platforms */
export type VideoPlatform = 'youtube' | 'direct' | 'unknown'

/** Time-aligned transcript segment */
export interface TranscriptSegment {
  text: string
  start: number
  duration: number
}

/** Structured video transcript entity */
export interface VideoTranscript {
  video_id: string
  language: string
  is_generated: boolean
  full_text: string
  segments: TranscriptSegment[]
  segment_count: number
}

/** Structured metadata entity representing a video */
export interface VideoMetadata {
  id: string
  url: string
  platform: VideoPlatform
  title: string | null
  status: VideoProcessingStatus
  created_at: string
  updated_at: string
  error_message?: string | null
  transcript?: VideoTranscript | null
}

/** Structured API response from FastAPI POST /api/videos/process */
export interface VideoProcessResponse {
  status: VideoProcessingStatus
  message: string
  video: VideoMetadata
  // Backward compatibility fields
  video_url?: string
  received_at?: string
  video_id?: string | null
}


export default function App() {
  // State for real API response, loading indicator, and server errors
  const [processedVideo, setProcessedVideo] = useState<VideoProcessResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [showTranscriptPreview, setShowTranscriptPreview] = useState<boolean>(false)

  // Handle video URL submission to FastAPI backend
  const handleVideoSubmit = async (url: string) => {
    setIsSubmitting(true)
    setSubmissionError(null)
    setProcessedVideo(null)
    setShowTranscriptPreview(false)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/videos/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        let errorDetail = `Request failed with HTTP status ${response.status}`
        try {
          const errorData = await response.json()
          if (errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              errorDetail = errorData.detail
                .map((d: { msg?: string }) => d.msg || 'Validation error')
                .join(', ')
            } else if (typeof errorData.detail === 'string') {
              errorDetail = errorData.detail
            }
          }
        } catch {
          // Keep default errorDetail if response is not JSON
        }
        throw new Error(errorDetail)
      }

      const result: VideoProcessResponse = await response.json()
      setProcessedVideo(result)
    } catch (error) {
      setSubmissionError(
        error instanceof Error
          ? error.message
          : 'Failed to connect to backend service. Please ensure FastAPI is running.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClear = () => {
    setProcessedVideo(null)
    setSubmissionError(null)
    setShowTranscriptPreview(false)
  }

  // Safe accessor resolving structured metadata with fallback to flat fields
  const video: VideoMetadata | null = processedVideo?.video ?? (processedVideo ? {
    id: processedVideo.video_id ?? 'unknown',
    url: processedVideo.video_url ?? '',
    platform: 'unknown' as VideoPlatform,
    title: null,
    status: processedVideo.status,
    created_at: processedVideo.received_at ?? '',
    updated_at: processedVideo.received_at ?? '',
  } : null)

  const formatPlatformLabel = (platform: VideoPlatform): string => {
    switch (platform) {
      case 'youtube':
        return 'YouTube'
      case 'direct':
        return 'Direct Stream'
      case 'unknown':
      default:
        return 'Web Source'
    }
  }

  const formatTimestamp = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 selection:bg-indigo-500 selection:text-white">
      <main className="w-full flex flex-col items-center justify-center space-y-6">
        {/* Welcome Banner */}
        <WelcomeBanner title="VIDYORA AI: Learn Smarter" />

        {/* Backend Connection Status */}
        <BackendStatus />

        {/* Video Input Form with Backend Integration */}
        <VideoInput
          onSubmit={handleVideoSubmit}
          isLoading={isSubmitting}
          serverError={submissionError}
          onClearError={() => setSubmissionError(null)}
        />

        {/* Real Backend Feedback Display with Structured Metadata & Transcript */}
        {processedVideo && video && (
          <div className={`w-full max-w-xl bg-slate-900 border rounded-2xl p-5 shadow-xl space-y-4 animate-fadeIn ${
            video.status === 'completed'
              ? 'border-emerald-500/40 shadow-emerald-500/5'
              : video.status === 'failed'
              ? 'border-rose-500/40 shadow-rose-500/5'
              : 'border-indigo-500/40 shadow-indigo-500/5'
          }`}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${
                  video.status === 'completed'
                    ? 'bg-emerald-400 animate-pulse'
                    : video.status === 'failed'
                    ? 'bg-rose-400'
                    : 'bg-indigo-400 animate-pulse'
                }`}></span>
                <span className={`text-xs font-semibold uppercase tracking-wider ${
                  video.status === 'completed'
                    ? 'text-emerald-400'
                    : video.status === 'failed'
                    ? 'text-rose-400'
                    : 'text-indigo-400'
                }`}>
                  Status: {video.status}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                  {formatPlatformLabel(video.platform)}
                </span>
              </div>

              <button
                type="button"
                onClick={handleClear}
                className="px-3 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer shrink-0"
              >
                Clear
              </button>
            </div>

            {/* Video Title if Available */}
            {video.title && (
              <h3 className="text-sm font-semibold text-slate-100 leading-snug line-clamp-2">
                {video.title}
              </h3>
            )}

            <p className="text-xs text-slate-300">
              {processedVideo.message}
            </p>

            {/* Error Message if Failed */}
            {video.error_message && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
                {video.error_message}
              </div>
            )}

            {/* Metadata Card */}
            <div className="bg-slate-950 rounded-xl p-3.5 border border-slate-800/80 space-y-2.5">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[10px] uppercase font-semibold text-slate-500 block">Video Identifier</span>
                  <span className="font-mono text-xs text-indigo-400 font-medium break-all">{video.id}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-semibold text-slate-500 block">Registered At</span>
                  <span className="text-slate-300 text-xs font-mono">
                    {new Date(video.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-[10px] uppercase font-semibold text-slate-500 block">Original URL</span>
                <p className="text-xs text-slate-300 font-mono truncate" title={video.url}>
                  {video.url}
                </p>
              </div>

              {/* Transcript Details if Extracted */}
              {video.transcript && (
                <div className="pt-2 border-t border-slate-900 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[10px] uppercase font-semibold text-slate-500">Transcript Details</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono font-medium">
                        {video.transcript.language.toUpperCase()}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                        {video.transcript.is_generated ? 'Auto ASR' : 'Manual Captions'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-400 bg-slate-900/60 px-2.5 py-1.5 rounded-lg border border-slate-800/60">
                    <span><strong>{video.transcript.segment_count}</strong> timed segments</span>
                    <span><strong>{video.transcript.full_text.split(/\s+/).filter(Boolean).length}</strong> words</span>
                    <button
                      type="button"
                      onClick={() => setShowTranscriptPreview(!showTranscriptPreview)}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium underline underline-offset-2 cursor-pointer ml-2"
                    >
                      {showTranscriptPreview ? 'Hide Snippets' : 'Preview Snippets'}
                    </button>
                  </div>

                  {/* Expandable Time-Aligned Segments Preview */}
                  {showTranscriptPreview && (
                    <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1 pt-1 text-xs">
                      {video.transcript.segments.slice(0, 12).map((seg, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2 bg-slate-900/40 p-2 rounded border border-slate-800/40 text-[11px]"
                        >
                          <span className="font-mono text-indigo-400 shrink-0 font-medium">
                            {formatTimestamp(seg.start)}
                          </span>
                          <span className="text-slate-300 leading-relaxed">
                            {seg.text}
                          </span>
                        </div>
                      ))}
                      {video.transcript.segment_count > 12 && (
                        <p className="text-[10px] text-slate-500 text-center italic pt-1">
                          + {video.transcript.segment_count - 12} more segments captured
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
