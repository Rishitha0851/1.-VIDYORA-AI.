import React from 'react'
import type { VideoSummary } from '../types/ai'

interface SummaryViewProps {
  summary: VideoSummary
  modelUsed?: string
  chunkCount?: number
  onTimestampClick?: (seconds: number) => void
}

export const SummaryView: React.FC<SummaryViewProps> = ({
  summary,
  modelUsed,
  chunkCount,
  onTimestampClick,
}) => {
  return (
    <div className="space-y-4 text-xs">
      {/* Model & Source Meta Header */}
      <div className="flex items-center justify-between bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400"></span>
          <span>
            Grounded in <strong className="text-slate-200">{chunkCount ?? 'all'}</strong> knowledge chunks
          </span>
        </div>
        {modelUsed && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 font-medium">
            {modelUsed}
          </span>
        )}
      </div>

      {/* 1. Executive Overview */}
      <div className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/80 space-y-1.5">
        <div className="flex items-center gap-1.5 text-indigo-400 font-semibold uppercase tracking-wider text-[10px]">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          </svg>
          <span>Executive Overview</span>
        </div>
        <p className="text-slate-200 leading-relaxed text-xs">
          {summary.overview}
        </p>
      </div>

      {/* 2. Beginner-Friendly Explanation (ELI5) */}
      {summary.beginner_explanation && (
        <div className="bg-gradient-to-br from-amber-500/10 via-slate-900/90 to-slate-900 p-3.5 rounded-xl border border-amber-500/20 space-y-1.5">
          <div className="flex items-center gap-1.5 text-amber-400 font-semibold uppercase tracking-wider text-[10px]">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span>Beginner-Friendly Intuition</span>
          </div>
          <p className="text-amber-100/90 leading-relaxed text-xs italic">
            "{summary.beginner_explanation}"
          </p>
        </div>
      )}

      {/* 3. Core Concepts Grid */}
      {summary.main_concepts && summary.main_concepts.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Core Concepts Explained
          </span>
          <div className="flex flex-wrap gap-1.5">
            {summary.main_concepts.map((concept, idx) => (
              <span
                key={idx}
                className="px-2.5 py-1 rounded-md bg-slate-950 text-indigo-300 border border-slate-800 text-[11px] font-medium"
              >
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 4. Actionable Takeaways */}
      {summary.takeaways && summary.takeaways.length > 0 && (
        <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 space-y-2">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Key Takeaways
          </span>
          <ul className="space-y-1.5">
            {summary.takeaways.map((takeaway, idx) => (
              <li key={idx} className="flex items-start gap-2 text-slate-300 text-xs">
                <span className="text-emerald-400 font-bold shrink-0">✓</span>
                <span className="leading-snug">{takeaway}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. Source Timestamps */}
      {summary.source_timestamps && summary.source_timestamps.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Video Source Timestamps
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {summary.source_timestamps.map((ts, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onTimestampClick?.(ts.timestamp)}
                className="flex items-center gap-2 p-2 rounded-lg bg-slate-950 hover:bg-slate-800/70 border border-slate-800 transition text-left cursor-pointer group"
              >
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800/60 group-hover:bg-indigo-900 group-hover:text-indigo-200 transition">
                  {ts.formatted_time}
                </span>
                <span className="text-slate-300 text-[11px] truncate group-hover:text-white transition">
                  {ts.label}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default SummaryView
