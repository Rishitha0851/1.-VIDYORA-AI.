import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import type {
  VideoPlayerHandle,
  VideoPlayerProps,
  YTPlayerInstance,
} from '../types/player'
import { formatTime } from '../utils/formatTime'

let apiLoadingPromise: Promise<void> | null = null

/** Ensures the official YouTube IFrame Player API script is loaded once */
function ensureYouTubeIframeApi(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()

  if (window.YT && window.YT.Player) {
    return Promise.resolve()
  }

  if (apiLoadingPromise) {
    return apiLoadingPromise
  }

  apiLoadingPromise = new Promise((resolve) => {
    // If the script tag already exists in document
    const existingScript = document.getElementById('youtube-iframe-api')
    if (existingScript) {
      const checkInterval = setInterval(() => {
        if (window.YT && window.YT.Player) {
          clearInterval(checkInterval)
          resolve()
        }
      }, 50)
      return
    }

    // Set up global callback
    const prevCallback = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      if (prevCallback) prevCallback()
      resolve()
    }

    const script = document.createElement('script')
    script.id = 'youtube-iframe-api'
    script.src = 'https://www.youtube.com/iframe_api'
    script.async = true
    script.onerror = () => {
      apiLoadingPromise = null
    }
    document.head.appendChild(script)
  })

  return apiLoadingPromise
}

/** Extracts a clean 11-character YouTube video ID from a raw ID or full URL */
function extractYouTubeId(input: string): string {
  if (!input) return ''
  const trimmed = input.trim()
  if (/^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return trimmed
  }
  const match = trimmed.match(/(?:v=|\/embed\/|\/watch\?v=|\/shorts\/|^youtu\.be\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
  return match ? match[1] : trimmed
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  (
    {
      videoId,
      title,
      originalUrl,
      onTimeUpdate,
      onStateChange,
      className = '',
      activeConceptLabel,
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null)
    const playerInstanceRef = useRef<YTPlayerInstance | null>(null)
    const timerRef = useRef<number | null>(null)
    const pendingSeekRef = useRef<number | null>(null)

    // Normalize input video ID (with fallback to originalUrl if videoId was internal/custom)
    const cleanVideoId = useMemo(() => {
      const fromId = extractYouTubeId(videoId)
      if (fromId && /^[a-zA-Z0-9_-]{11}$/.test(fromId)) return fromId
      if (originalUrl) {
        const fromUrl = extractYouTubeId(originalUrl)
        if (fromUrl && /^[a-zA-Z0-9_-]{11}$/.test(fromUrl)) return fromUrl
      }
      return fromId || ''
    }, [videoId, originalUrl])

    // Component state
    const [isReady, setIsReady] = useState<boolean>(false)
    const [isPlaying, setIsPlaying] = useState<boolean>(false)
    const [currentTime, setCurrentTime] = useState<number>(0)
    const [duration, setDuration] = useState<number>(0)
    const [playbackRate, setPlaybackRate] = useState<number>(1)
    const [playerError, setPlayerError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [isMuted, setIsMuted] = useState<boolean>(false)
    const [recentSeekToast, setRecentSeekToast] = useState<string | null>(null)

    // Clear seek feedback toast after a brief duration
    useEffect(() => {
      if (!recentSeekToast) return
      const timer = setTimeout(() => setRecentSeekToast(null), 2400)
      return () => clearTimeout(timer)
    }, [recentSeekToast])

    // Stop time polling timer
    const stopTimeTracking = useCallback(() => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }, [])

    // Poll current time when playing (~250ms interval)
    const startTimeTracking = useCallback(() => {
      stopTimeTracking()
      timerRef.current = window.setInterval(() => {
        const player = playerInstanceRef.current
        if (!player) return
        try {
          const current = player.getCurrentTime() || 0
          const total = player.getDuration() || 0
          setCurrentTime(current)
          if (total > 0) setDuration(total)
          onTimeUpdate?.(current, total)
        } catch {
          // Ignore transient errors when frame is navigating
        }
      }, 250)
    }, [onTimeUpdate, stopTimeTracking])

    // Imperative handle exposed to parent components
    useImperativeHandle(
      ref,
      () => ({
        seekTo: (seconds: number, shouldPlay = true) => {
          const player = playerInstanceRef.current
          const clamped = Math.max(0, Math.min(seconds, duration || seconds + 10))
          if (!player || !isReady) {
            // Buffer seek until player finishes initializing
            pendingSeekRef.current = clamped
            setCurrentTime(clamped)
            setRecentSeekToast(`Jumped to ${formatTime(clamped)}`)
            return
          }
          try {
            player.seekTo(clamped, true)
            setCurrentTime(clamped)
            setRecentSeekToast(`Jumped to ${formatTime(clamped)}`)
            if (shouldPlay) {
              player.playVideo()
              setIsPlaying(true)
              startTimeTracking()
            }
          } catch {
            // Player may still be buffering
          }
        },
        play: () => {
          playerInstanceRef.current?.playVideo()
        },
        pause: () => {
          playerInstanceRef.current?.pauseVideo()
        },
        togglePlay: () => {
          if (isPlaying) {
            playerInstanceRef.current?.pauseVideo()
          } else {
            playerInstanceRef.current?.playVideo()
          }
        },
        getCurrentTime: () => currentTime,
        getDuration: () => duration,
        isPlaying: () => isPlaying,
      }),
      [currentTime, duration, isPlaying, isReady, startTimeTracking]
    )

    // Initialize or reload YouTube player instance
    useEffect(() => {
      let isCancelled = false
      queueMicrotask(() => {
        if (!isCancelled) {
          setIsLoading(true)
          setIsReady(false)
          setPlayerError(null)
        }
      })
      stopTimeTracking()

      // Destroy old instance if present
      if (playerInstanceRef.current) {
        try {
          playerInstanceRef.current.destroy()
        } catch {
          // Ignore cleanup errors
        }
        playerInstanceRef.current = null
      }

      if (!cleanVideoId) {
        queueMicrotask(() => {
          if (!isCancelled) setIsLoading(false)
        })
        return
      }

      ensureYouTubeIframeApi()
        .then(() => {
          if (isCancelled || !containerRef.current) return

          // Create a child element to be replaced by the iframe
          const playerElement = document.createElement('div')
          containerRef.current.innerHTML = ''
          containerRef.current.appendChild(playerElement)

          const player = new window.YT!.Player(playerElement, {
            videoId: cleanVideoId,
            width: '100%',
            height: '100%',
            playerVars: {
              autoplay: 0,
              controls: 1, // Keep native controls for accessibility, captions & quality
              modestbranding: 1,
              rel: 0,
              enablejsapi: 1,
              origin: window.location.origin,
              playsinline: 1,
              fs: 1,
            },
            events: {
              onReady: (event) => {
                if (isCancelled) return
                setIsLoading(false)
                setIsReady(true)
                try {
                  const dur = event.target.getDuration() || 0
                  setDuration(dur)
                  setIsMuted(event.target.isMuted())
                  onTimeUpdate?.(0, dur)
                  onStateChange?.(false, 'ready')

                  // If a seek was queued before player was ready, execute immediately
                  if (pendingSeekRef.current !== null) {
                    const targetSeconds = pendingSeekRef.current
                    pendingSeekRef.current = null
                    event.target.seekTo(targetSeconds, true)
                    setCurrentTime(targetSeconds)
                    event.target.playVideo()
                    setIsPlaying(true)
                    startTimeTracking()
                  }
                } catch {
                  // Ignore initial query errors
                }
              },
              onStateChange: (event) => {
                if (isCancelled) return
                const playerState = event.data
                const YTStates = window.YT?.PlayerState

                try {
                  const current = event.target.getCurrentTime() || 0
                  const total = event.target.getDuration() || 0
                  setCurrentTime(current)
                  if (total > 0) setDuration(total)
                  onTimeUpdate?.(current, total)
                } catch {
                  // Ignore frame query errors
                }

                if (YTStates && playerState === YTStates.PLAYING) {
                  setIsPlaying(true)
                  startTimeTracking()
                  onStateChange?.(true, 'playing')
                } else if (YTStates && playerState === YTStates.PAUSED) {
                  setIsPlaying(false)
                  stopTimeTracking()
                  onStateChange?.(false, 'paused')
                } else if (YTStates && playerState === YTStates.BUFFERING) {
                  onStateChange?.(false, 'buffering')
                } else if (YTStates && playerState === YTStates.ENDED) {
                  setIsPlaying(false)
                  stopTimeTracking()
                  onStateChange?.(false, 'ended')
                }
              },
              onError: (event) => {
                if (isCancelled) return
                setIsLoading(false)
                stopTimeTracking()
                const code = event.data
                let message = "We couldn't load this YouTube video."
                if (code === 2) {
                  message = 'The video identifier is invalid or contains malformed parameters.'
                } else if (code === 100) {
                  message = 'This video was not found (it may have been removed or marked private).'
                } else if (code === 101 || code === 150) {
                  message =
                    'The creator has disabled embedded playback for this video. You can still watch it directly on YouTube while using the study tools below.'
                }
                setPlayerError(message)
              },
            },
          })

          playerInstanceRef.current = player
        })
        .catch((err) => {
          if (!isCancelled) {
            setIsLoading(false)
            setPlayerError('Failed to load the YouTube player script. Please check your internet connection.')
            console.error('YouTube API load error:', err)
          }
        })

      return () => {
        isCancelled = true
        stopTimeTracking()
        if (playerInstanceRef.current) {
          try {
            playerInstanceRef.current.destroy()
          } catch {
            // Ignore unmount error
          }
          playerInstanceRef.current = null
        }
      }
    }, [cleanVideoId, onStateChange, onTimeUpdate, startTimeTracking, stopTimeTracking])

    // Controls handlers
    const handleTogglePlay = () => {
      const player = playerInstanceRef.current
      if (!player) return
      if (isPlaying) {
        player.pauseVideo()
      } else {
        player.playVideo()
      }
    }

    const handleSkip = (offsetSeconds: number) => {
      const player = playerInstanceRef.current
      if (!player) return
      const target = Math.max(0, Math.min(currentTime + offsetSeconds, duration))
      player.seekTo(target, true)
      setCurrentTime(target)
      setRecentSeekToast(`${offsetSeconds > 0 ? '+10s' : '-10s'} (${formatTime(target)})`)
    }

    const handleScrubberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const target = parseFloat(e.target.value)
      setCurrentTime(target)
      const player = playerInstanceRef.current
      if (player) {
        player.seekTo(target, true)
        setRecentSeekToast(`Seek: ${formatTime(target)}`)
      }
    }

    const handleSpeedChange = (rate: number) => {
      const player = playerInstanceRef.current
      if (player) {
        player.setPlaybackRate(rate)
        setPlaybackRate(rate)
      }
    }

    const handleToggleMute = () => {
      const player = playerInstanceRef.current
      if (!player) return
      if (isMuted) {
        player.unMute()
        setIsMuted(false)
      } else {
        player.mute()
        setIsMuted(true)
      }
    }

    const youtubeDirectUrl = originalUrl || (cleanVideoId ? `https://www.youtube.com/watch?v=${cleanVideoId}` : '#')

    return (
      <div className={`flex flex-col bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl ${className}`}>
        {/* 1. Video Container & IFrame Embed */}
        <div
          className="relative aspect-video w-full bg-slate-950 overflow-hidden group"
          aria-label={title || 'Lecture video player'}
        >
          {/* Container holding the YouTube IFrame */}
          <div ref={containerRef} className="w-full h-full" />

          {/* Loading Skeleton */}
          {isLoading && !playerError && (
            <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center space-y-3 z-10">
              <div className="w-10 h-10 rounded-full border-3 border-indigo-500 border-t-transparent animate-spin"></div>
              <p className="text-xs text-slate-300 font-medium">Connecting to YouTube lecture...</p>
              <p className="text-[10px] text-slate-500 font-mono">{videoId}</p>
            </div>
          )}

          {/* Seek Feedback Toast Overlay */}
          {recentSeekToast && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-3 py-1.5 rounded-full bg-indigo-600/90 text-white text-xs font-semibold shadow-lg backdrop-blur-md animate-fadeIn flex items-center gap-1.5 pointer-events-none">
              <span>⏱️</span>
              <span>{recentSeekToast}</span>
            </div>
          )}

          {/* Error State Overlay */}
          {playerError && (
            <div className="absolute inset-0 bg-slate-950/95 flex flex-col items-center justify-center p-6 text-center space-y-3 z-20">
              <div className="w-12 h-12 rounded-full bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-xl">
                ⚠️
              </div>
              <div className="space-y-1 max-w-md">
                <h4 className="text-sm font-bold text-white">Playback Restriction</h4>
                <p className="text-xs text-slate-300 leading-relaxed">{playerError}</p>
              </div>
              <div className="flex items-center gap-2 pt-2">
                <a
                  href={youtubeDirectUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-semibold text-xs transition cursor-pointer flex items-center gap-1.5 shadow-md shadow-red-950"
                >
                  <span>▶</span>
                  <span>Watch on YouTube</span>
                  <span>↗</span>
                </a>
                <button
                  type="button"
                  onClick={() => {
                    setIsLoading(true)
                    setPlayerError(null)
                    playerInstanceRef.current?.destroy()
                    playerInstanceRef.current = null
                    ensureYouTubeIframeApi().then(() => {
                      // re-mount handled via state
                    })
                  }}
                  className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer"
                >
                  Retry
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 2. Vidyora Companion Playback & Navigation Bar */}
        <div className="p-3.5 bg-slate-950/90 border-t border-slate-800/80 space-y-2.5">
          {/* Active Lecture Concept Banner */}
          {activeConceptLabel && (
            <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-indigo-950/40 border border-indigo-500/30 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse shrink-0"></span>
                <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider shrink-0">
                  Current Concept:
                </span>
                <span className="text-slate-200 font-medium truncate text-xs">
                  {activeConceptLabel}
                </span>
              </div>
              <span className="font-mono text-[10px] text-indigo-300 shrink-0 bg-indigo-900/60 px-1.5 py-0.5 rounded">
                {formatTime(currentTime)}
              </span>
            </div>
          )}

          {/* Interactive Scrubber / Progress Bar */}
          <div className="space-y-1">
            <div className="relative flex items-center">
              <input
                type="range"
                min={0}
                max={duration > 0 ? duration : 100}
                step={0.5}
                value={currentTime}
                onChange={handleScrubberChange}
                disabled={!isReady || duration === 0}
                aria-label="Seek video progress"
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:accent-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition"
              />
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 px-0.5">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Quick Action Controls */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
            {/* Play, Pause, and Skip buttons */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleTogglePlay}
                disabled={!isReady}
                aria-label={isPlaying ? 'Pause lecture' : 'Play lecture'}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-semibold text-xs transition cursor-pointer shadow-md shadow-indigo-950 flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>{isPlaying ? '⏸' : '▶'}</span>
                <span>{isPlaying ? 'Pause' : 'Play'}</span>
              </button>

              <button
                type="button"
                onClick={() => handleSkip(-10)}
                disabled={!isReady}
                aria-label="Rewind 10 seconds"
                className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-mono transition cursor-pointer disabled:opacity-50"
                title="Rewind 10 seconds"
              >
                -10s
              </button>

              <button
                type="button"
                onClick={() => handleSkip(10)}
                disabled={!isReady}
                aria-label="Forward 10 seconds"
                className="p-1.5 px-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-mono transition cursor-pointer disabled:opacity-50"
                title="Forward 10 seconds"
              >
                +10s
              </button>

              <button
                type="button"
                onClick={handleToggleMute}
                disabled={!isReady}
                aria-label={isMuted ? 'Unmute' : 'Mute'}
                className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-xs transition cursor-pointer disabled:opacity-50"
                title={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted ? '🔇' : '🔊'}
              </button>
            </div>

            {/* Playback speed selector */}
            <div className="flex items-center gap-1">
              <span className="text-[10px] uppercase font-semibold text-slate-500 mr-1">Speed</span>
              {[0.75, 1, 1.25, 1.5, 2].map((rate) => (
                <button
                  key={rate}
                  type="button"
                  onClick={() => handleSpeedChange(rate)}
                  disabled={!isReady}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium transition cursor-pointer ${
                    playbackRate === rate
                      ? 'bg-indigo-600 text-white font-bold'
                      : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }
)

VideoPlayer.displayName = 'VideoPlayer'

export default VideoPlayer
