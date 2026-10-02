import { useState, useEffect, useCallback } from 'react'

/** Backend Health API Response Structure */
interface HealthResponse {
  status: string
  service: string
  version: string
}

/** Component status states */
type ConnectionStatus = 'loading' | 'success' | 'error'

interface BackendStatusProps {
  /** Optional custom health check endpoint URL */
  endpoint?: string
}

export default function BackendStatus({
  endpoint = 'http://127.0.0.1:8000/health',
}: BackendStatusProps) {
  // 1. React State hooks for tracking connection status, data, and errors
  const [status, setStatus] = useState<ConnectionStatus>('loading')
  const [data, setData] = useState<HealthResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // 2. Asynchronous function to fetch health status from FastAPI backend
  const checkConnection = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setErrorMessage(null)

    try {
      const response = await fetch(endpoint, { signal })

      if (!response.ok) {
        throw new Error(`Server responded with HTTP status ${response.status} (${response.statusText})`)
      }

      const result: HealthResponse = await response.json()
      setData(result)
      setStatus('success')
    } catch (error) {
      if (signal?.aborted) return
      setStatus('error')
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Backend is unavailable. Make sure FastAPI server is running on port 8000.'
      )
    }
  }, [endpoint])

  // 3. useEffect hook to trigger health check on initial mount or when endpoint changes
  useEffect(() => {
    const controller = new AbortController()
    
    // Perform fetch when component mounts or endpoint updates
    const fetchData = async () => {
      try {
        const response = await fetch(endpoint, { signal: controller.signal })
        if (!response.ok) {
          throw new Error(`Server responded with HTTP status ${response.status} (${response.statusText})`)
        }
        const result: HealthResponse = await response.json()
        setData(result)
        setStatus('success')
      } catch (error) {
        if (controller.signal.aborted) return
        setStatus('error')
        setErrorMessage(
          error instanceof Error
            ? error.message
            : 'Backend is unavailable. Make sure FastAPI server is running on port 8000.'
        )
      }
    }

    fetchData()

    return () => {
      controller.abort()
    }
  }, [endpoint])

  return (
    <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between gap-4">
      {/* Status Details */}
      <div className="flex items-center gap-3 overflow-hidden">
        {/* Loading State */}
        {status === 'loading' && (
          <>
            <span className="relative flex h-3 w-3 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
            </span>
            <div className="space-y-0.5">
              <p className="text-xs font-semibold text-slate-200">Checking backend connection...</p>
              <p className="text-[11px] text-slate-500">Reaching FastAPI health endpoint ({endpoint})</p>
            </div>
          </>
        )}

        {/* Success State */}
        {status === 'success' && (
          <>
            <span className="relative flex h-3 w-3 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold text-emerald-400">Backend Connected</p>
                {data?.version && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                    v{data.version}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400">{data?.service || 'FastAPI Service Online'}</p>
            </div>
          </>
        )}

        {/* Error State */}
        {status === 'error' && (
          <>
            <span className="relative flex h-3 w-3 shrink-0">
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
            </span>
            <div className="space-y-0.5 overflow-hidden">
              <p className="text-xs font-semibold text-rose-400">Backend Unavailable</p>
              <p className="text-[11px] text-slate-400 truncate" title={errorMessage || ''}>
                {errorMessage || 'Unable to connect to backend server'}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Manual Retry Button */}
      <button
        type="button"
        onClick={() => checkConnection()}
        disabled={status === 'loading'}
        className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white transition cursor-pointer shrink-0 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-700/50"
      >
        {status === 'loading' ? 'Checking...' : 'Retry'}
      </button>
    </div>
  )
}
