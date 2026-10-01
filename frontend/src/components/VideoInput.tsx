import { useState, type FormEvent } from 'react'

interface VideoInputProps {
  /** Callback fired when a valid URL is submitted */
  onSubmit: (url: string) => void
  /** Optional loading state to disable input during processing */
  isLoading?: boolean
}

export default function VideoInput({ onSubmit, isLoading = false }: VideoInputProps) {
  // 1. Local state for what the user is typing
  const [url, setUrl] = useState<string>('')

  // 2. Local state for validation error messages
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // 3. Simple URL validation function
  const validateUrl = (value: string): boolean => {
    if (!value.trim()) {
      setErrorMessage('Please enter a video URL to begin.')
      return false
    }

    try {
      const parsed = new URL(value.trim())
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        setErrorMessage('URL must begin with http:// or https://')
        return false
      }
      return true
    } catch {
      setErrorMessage('Please enter a valid URL (e.g., https://www.youtube.com/watch?v=...)')
      return false
    }
  }

  // 4. Form submit handler
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    // Prevent the default browser behavior (which would reload the page)
    e.preventDefault()

    const trimmedUrl = url.trim()

    if (validateUrl(trimmedUrl)) {
      setErrorMessage(null)
      onSubmit(trimmedUrl)
    }
  }

  return (
    <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Import Educational Video</h2>
        <p className="text-xs text-slate-400 mt-1">
          Paste a YouTube lecture or educational video link to begin generating structured learning notes.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              // Clear error as soon as user types
              if (errorMessage) setErrorMessage(null)
            }}
            placeholder="https://www.youtube.com/watch?v=..."
            disabled={isLoading}
            className="flex-1 bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 outline-none transition disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={isLoading}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-medium text-sm rounded-xl transition shadow-md shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap"
          >
            {isLoading ? 'Processing...' : 'Analyze Video'}
          </button>
        </div>

        {/* Validation Error Message */}
        {errorMessage && (
          <p className="text-xs text-rose-400 flex items-center gap-1.5 animate-fadeIn">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
            {errorMessage}
          </p>
        )}
      </form>
    </div>
  )
}
