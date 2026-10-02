import { useState } from 'react'
import WelcomeBanner from './components/WelcomeBanner'
import BackendStatus from './components/BackendStatus'
import VideoInput from './components/VideoInput'

/** Structured response from FastAPI POST /api/videos/process */
export interface VideoProcessResponse {
  status: string
  message: string
  video_url: string
  received_at: string
  video_id: string | null
}

export default function App() {
  // State for real API response, loading indicator, and server errors
  const [processedVideo, setProcessedVideo] = useState<VideoProcessResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // Handle video URL submission to FastAPI backend
  const handleVideoSubmit = async (url: string) => {
    setIsSubmitting(true)
    setSubmissionError(null)
    setProcessedVideo(null)

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

        {/* Real Backend Feedback Display */}
        {processedVideo && (
          <div className="w-full max-w-xl bg-slate-900 border border-emerald-500/30 rounded-2xl p-5 shadow-xl space-y-3 animate-fadeIn">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Video Registered & Queued
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

            <p className="text-xs text-slate-300">
              {processedVideo.message}
            </p>

            <div className="bg-slate-950 rounded-xl p-3 border border-slate-800/80 space-y-1">
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Submitted URL</span>
                {processedVideo.video_id && (
                  <span className="font-mono text-indigo-400">ID: {processedVideo.video_id}</span>
                )}
              </div>
              <p className="text-xs text-slate-200 font-mono truncate" title={processedVideo.video_url}>
                {processedVideo.video_url}
              </p>
              <p className="text-[10px] text-slate-500 pt-1">
                Timestamp: {new Date(processedVideo.received_at).toLocaleTimeString()}
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
