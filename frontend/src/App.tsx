import { useState } from 'react'
import WelcomeBanner from './components/WelcomeBanner'
import BackendStatus from './components/BackendStatus'
import VideoInput from './components/VideoInput'

export default function App() {
  // State to hold the submitted video URL across the application
  const [currentVideoUrl, setCurrentVideoUrl] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 selection:bg-indigo-500 selection:text-white">
      <main className="w-full flex flex-col items-center justify-center space-y-6">
        {/* Step 3 Component: Welcome Banner */}
        <WelcomeBanner title="VIDYORA AI: Learn Smarter" />

        {/* Phase 3 Component: Backend Connection Status */}
        <BackendStatus />

        {/* Step 4 Component: Video Input Form */}
        <VideoInput
          onSubmit={(url) => {
            setCurrentVideoUrl(url)
          }}
        />

        {/* Feedback Display: Shows the state stored in parent component */}
        {currentVideoUrl && (
          <div className="w-full max-w-xl bg-slate-900/60 border border-emerald-500/30 rounded-2xl p-5 shadow-lg flex items-center justify-between gap-4 animate-fadeIn">
            <div className="space-y-1 overflow-hidden">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Video Queued for Processing
                </span>
              </div>
              <p className="text-xs text-slate-300 font-mono truncate" title={currentVideoUrl}>
                {currentVideoUrl}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setCurrentVideoUrl(null)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer shrink-0"
            >
              Clear
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
