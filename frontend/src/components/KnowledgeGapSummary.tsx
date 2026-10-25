import React from 'react'
import type { VideoKnowledgeGapSummary } from '../types/ai'

interface KnowledgeGapSummaryProps {
  summary: VideoKnowledgeGapSummary
  weakChunkCount: number
  activeFilter: string
  onFilterChange: (filter: 'ALL' | 'WEAK' | 'DEVELOPING' | 'STRONG') => void
}

export const KnowledgeGapSummary: React.FC<KnowledgeGapSummaryProps> = ({
  summary,
  weakChunkCount,
  activeFilter,
  onFilterChange,
}) => {
  const accuracyPct = Math.round(summary.overall_accuracy * 100)

  return (
    <div className="space-y-3">
      {/* Top Banner with Diagnosis & Primary Action Cue */}
      <div className={`p-4 rounded-xl border transition ${
        weakChunkCount > 0
          ? 'bg-rose-950/20 border-rose-500/30 text-rose-200'
          : summary.assessed_chunks === 0
          ? 'bg-slate-900/60 border-slate-800 text-slate-300'
          : 'bg-emerald-950/20 border-emerald-500/30 text-emerald-200'
      }`}>
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-base">
                {weakChunkCount > 0 ? '⚠️' : summary.assessed_chunks === 0 ? 'ℹ️' : '🎯'}
              </span>
              <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                {weakChunkCount > 0
                  ? `${weakChunkCount} Concept${weakChunkCount > 1 ? 's' : ''} Need Revision`
                  : summary.assessed_chunks === 0
                  ? 'No Assessment Data Recorded'
                  : 'All Assessed Concepts Demonstrated Mastery'}
              </h3>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-300">
              {weakChunkCount > 0
                ? 'Repeated quiz misconceptions identified. Review the source lecture segments highlighted below before attempting remediation.'
                : summary.assessed_chunks === 0
                ? 'Take the video quiz to generate your evidence-grounded knowledge gap profile.'
                : 'Great work! You have shown consistent accuracy across the tested segments of this lecture.'}
            </p>

            {((summary.recovered_chunks_count ?? 0) > 0 || (summary.recovery_in_progress_count ?? 0) > 0) && (
              <div className="flex items-center gap-3 pt-2 text-[11px] font-medium border-t border-slate-800/80 flex-wrap">
                {(summary.recovered_chunks_count ?? 0) > 0 && (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <span>✨</span>
                    <span>{summary.recovered_chunks_count} concept{summary.recovered_chunks_count! > 1 ? 's' : ''} recovered</span>
                  </span>
                )}
                {(summary.recovery_in_progress_count ?? 0) > 0 && (
                  <span className="text-amber-400 flex items-center gap-1">
                    <span>🔄</span>
                    <span>{summary.recovery_in_progress_count} in recovery</span>
                  </span>
                )}
              </div>
            )}
          </div>

          {summary.assessed_chunks > 0 && (
            <div className="text-right shrink-0">
              <span className="text-2xl font-black font-mono text-white block">
                {accuracyPct}%
              </span>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Assessed Accuracy
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Metric Cards Row (Clickable as Quick Filter Controls) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {/* 1. Needs Revision (WEAK) - Highest Visual Priority */}
        <button
          type="button"
          onClick={() => onFilterChange('WEAK')}
          className={`p-3 rounded-xl border text-left transition cursor-pointer relative overflow-hidden group ${
            activeFilter === 'WEAK'
              ? 'bg-rose-500/15 border-rose-500 ring-1 ring-rose-500/50'
              : 'bg-slate-900/70 border-slate-800/80 hover:border-rose-500/40 hover:bg-slate-900'
          }`}
          aria-label={`Filter by Needs Revision: ${summary.weak_chunks_count} concepts`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wider text-rose-400">
              Needs Revision
            </span>
            <span className="h-2 w-2 rounded-full bg-rose-500"></span>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold font-mono text-white">
              {summary.weak_chunks_count}
            </span>
            <span className="text-[10px] text-slate-400">concepts</span>
          </div>
        </button>

        {/* 2. Developing */}
        <button
          type="button"
          onClick={() => onFilterChange('DEVELOPING')}
          className={`p-3 rounded-xl border text-left transition cursor-pointer group ${
            activeFilter === 'DEVELOPING'
              ? 'bg-amber-500/15 border-amber-500 ring-1 ring-amber-500/50'
              : 'bg-slate-900/70 border-slate-800/80 hover:border-amber-500/40 hover:bg-slate-900'
          }`}
          aria-label={`Filter by Developing: ${summary.developing_chunks_count} concepts`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wider text-amber-400">
              Developing
            </span>
            <span className="h-2 w-2 rounded-full bg-amber-500"></span>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold font-mono text-white">
              {summary.developing_chunks_count}
            </span>
            <span className="text-[10px] text-slate-400">concepts</span>
          </div>
        </button>

        {/* 3. Strong */}
        <button
          type="button"
          onClick={() => onFilterChange('STRONG')}
          className={`p-3 rounded-xl border text-left transition cursor-pointer group ${
            activeFilter === 'STRONG'
              ? 'bg-emerald-500/15 border-emerald-500 ring-1 ring-emerald-500/50'
              : 'bg-slate-900/70 border-slate-800/80 hover:border-emerald-500/40 hover:bg-slate-900'
          }`}
          aria-label={`Filter by Strong: ${summary.strong_chunks_count} concepts`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400">
              Strong
            </span>
            <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold font-mono text-white">
              {summary.strong_chunks_count}
            </span>
            <span className="text-[10px] text-slate-400">concepts</span>
          </div>
        </button>

        {/* 4. Unassessed / Insufficient Data */}
        <div className="p-3 rounded-xl border bg-slate-900/40 border-slate-800/60 text-left">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
              Unassessed
            </span>
            <span className="h-2 w-2 rounded-full bg-slate-600"></span>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold font-mono text-slate-300">
              {summary.insufficient_data_count}
            </span>
            <span className="text-[10px] text-slate-500">of {summary.total_chunks}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default KnowledgeGapSummary
