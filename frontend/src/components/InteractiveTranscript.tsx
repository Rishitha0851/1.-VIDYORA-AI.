import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { TranscriptChunk, TranscriptSegment } from '../types/ai'
import { formatTime } from '../utils/formatTime'

interface InteractiveTranscriptProps {
  segments: TranscriptSegment[]
  currentTime: number
  onSeek: (seconds: number) => void
  chunks?: TranscriptChunk[]
  className?: string
}

export const InteractiveTranscript: React.FC<InteractiveTranscriptProps> = ({
  segments,
  currentTime,
  onSeek,
  className = '',
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [autoScroll, setAutoScroll] = useState<boolean>(true)
  const containerRef = useRef<HTMLDivElement>(null)
  const activeItemRef = useRef<HTMLDivElement>(null)

  // Identify index of currently active segment based on current video time
  const activeIndex = useMemo(() => {
    if (!segments || segments.length === 0) return -1
    // 1. Direct hit within segment duration (with small 0.25s buffer)
    const exact = segments.findIndex(
      (seg) => currentTime >= seg.start && currentTime < seg.start + Math.max(seg.duration, 0.4) + 0.25
    )
    if (exact !== -1) return exact

    // 2. Resilience: if briefly between segments, keep the last segment if within 1.5s
    let candidate = -1
    for (let i = 0; i < segments.length; i++) {
      if (segments[i].start <= currentTime) {
        candidate = i
      } else {
        break
      }
    }
    if (candidate !== -1) {
      const seg = segments[candidate]
      if (currentTime <= seg.start + Math.max(seg.duration, 0.5) + 1.5) {
        return candidate
      }
    }
    return -1
  }, [segments, currentTime])

  // Auto-scroll the active segment smoothly into center view
  useEffect(() => {
    if (!autoScroll || activeIndex === -1 || !activeItemRef.current || !containerRef.current) {
      return
    }

    const container = containerRef.current
    const activeEl = activeItemRef.current

    // Calculate relative offset to scroll active element to vertical center
    const containerTop = container.scrollTop
    const containerHeight = container.clientHeight
    const elementTop = activeEl.offsetTop
    const elementHeight = activeEl.clientHeight

    const targetScrollTop = elementTop - containerHeight / 2 + elementHeight / 2

    // Only scroll if outside the comfortable center zone
    if (Math.abs(containerTop - targetScrollTop) > 60) {
      container.scrollTo({
        top: Math.max(0, targetScrollTop),
        behavior: 'smooth',
      })
    }
  }, [activeIndex, autoScroll])

  // Filter segments if user entered a search query
  const filteredSegments = useMemo(() => {
    if (!searchQuery.trim()) return segments
    const query = searchQuery.toLowerCase().trim()
    return segments.filter((seg) => seg.text.toLowerCase().includes(query))
  }, [segments, searchQuery])

  return (
    <div className={`flex flex-col bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg ${className}`}>
      {/* Header with Search and Auto-Scroll Toggle */}
      <div className="p-3.5 bg-slate-950/80 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <span className="text-sm">📜</span>
          <div>
            <h3 className="text-xs font-bold text-white tracking-wide">
              Synchronized Transcript
            </h3>
            <p className="text-[10px] text-slate-400">
              {segments.length} spoken segments • Click any timestamp to jump
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Auto-scroll toggle */}
          <button
            type="button"
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition cursor-pointer flex items-center gap-1.5 border focus:outline-none focus:ring-2 focus:ring-indigo-500/50 ${
              autoScroll
                ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40 shadow-sm shadow-indigo-950'
                : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
            title="Keep currently spoken text visible automatically"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${autoScroll ? 'bg-indigo-400 animate-pulse' : 'bg-slate-500'}`}></span>
            <span>Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="px-3.5 py-2 bg-slate-950/40 border-b border-slate-800/50">
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search spoken dialogue (e.g. backpropagation, learning rate)..."
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-8 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
          />
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 text-xs">
            🔍
          </span>
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Scrollable Transcript List */}
      <div
        ref={containerRef}
        className="relative max-h-96 sm:max-h-[28rem] overflow-y-auto p-3 space-y-1.5 divide-y divide-slate-800/30"
      >
        {filteredSegments.length > 0 ? (
          filteredSegments.map((seg, idx) => {
            const originalIndex = segments.indexOf(seg)
            const isActive = originalIndex === activeIndex

            return (
              <div
                key={originalIndex >= 0 ? originalIndex : idx}
                ref={isActive ? activeItemRef : null}
                onClick={() => onSeek(seg.start)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSeek(seg.start)
                  }
                }}
                className={`pt-1.5 first:pt-0 flex items-start gap-2.5 p-2 rounded-xl transition cursor-pointer text-xs group focus:outline-none focus:ring-2 focus:ring-indigo-500/50 ${
                  isActive
                    ? 'bg-indigo-950/60 border border-indigo-500/50 shadow-md shadow-indigo-950/30 text-white'
                    : 'hover:bg-slate-800/50 text-slate-300 border border-transparent'
                }`}
              >
                {/* Timestamp Button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onSeek(seg.start)
                  }}
                  className={`font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md shrink-0 transition focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-950 text-indigo-400 border border-slate-800 group-hover:border-indigo-500/60 group-hover:text-indigo-300'
                  }`}
                  title={`Jump to ${formatTime(seg.start)}`}
                >
                  {formatTime(seg.start)}
                </button>

                {/* Spoken Dialogue Text */}
                <div className="flex-1 min-w-0">
                  <p className={`leading-relaxed text-xs ${isActive ? 'font-medium text-slate-100' : 'text-slate-300'}`}>
                    {seg.text}
                  </p>
                </div>

                {/* Active Indicator Wave */}
                {isActive && (
                  <span className="shrink-0 flex items-center gap-0.5 text-indigo-400 text-xs animate-pulse" title="Currently speaking">
                    <span>🔊</span>
                  </span>
                )}
              </div>
            )
          })
        ) : (
          <div className="p-8 text-center text-slate-500 text-xs">
            No dialogue matching "{searchQuery}"
          </div>
        )}
      </div>
    </div>
  )
}

export default InteractiveTranscript
