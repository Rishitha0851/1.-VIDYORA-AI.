import React, { useMemo, useState } from 'react'
import type { ChunkKnowledgeGap, VideoKnowledgeGapsResponse } from '../types/ai'
import { KnowledgeGapSummary } from './KnowledgeGapSummary'
import { KnowledgeGapCard } from './KnowledgeGapCard'
import { KnowledgeGapFilters, type FilterCategory } from './KnowledgeGapFilters'
import { LearningRecoveryView } from './LearningRecoveryView'

interface KnowledgeGapViewProps {
  knowledgeGaps: VideoKnowledgeGapsResponse | null
  isLoading: boolean
  error: string | null
  onRetry: () => void
  videoUrl?: string
  videoId?: string
  onReviewInVideo?: (videoUrl: string, timestamp: number) => void
  onRecoveryCompleted?: () => void
  onStartRecovery?: (gap: ChunkKnowledgeGap) => void
  onAskTutor?: (gap: ChunkKnowledgeGap) => void
  onPracticeQuiz?: () => void
}

export const KnowledgeGapView: React.FC<KnowledgeGapViewProps> = ({
  knowledgeGaps,
  isLoading,
  error,
  onRetry,
  videoUrl,
  videoId,
  onReviewInVideo,
  onRecoveryCompleted,
  onStartRecovery,
  onAskTutor,
  onPracticeQuiz,
}) => {
  const [activeFilter, setActiveFilter] = useState<FilterCategory>('ALL')
  const [activeRecoveryChunk, setActiveRecoveryChunk] = useState<ChunkKnowledgeGap | null>(null)

  // Filtered gaps list based strictly on backend classifications
  const filteredGaps = useMemo(() => {
    if (!knowledgeGaps?.gaps) return []
    if (activeFilter === 'ALL') return knowledgeGaps.gaps
    return knowledgeGaps.gaps.filter((gap) => gap.classification === activeFilter)
  }, [knowledgeGaps, activeFilter])

  // 1. Loading State
  if (isLoading) {
    return (
      <div className="p-8 text-center space-y-3 bg-slate-950/60 rounded-xl border border-slate-800 animate-pulse">
        <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto"></div>
        <p className="text-xs text-indigo-300 font-medium">
          Synthesizing deterministic learner knowledge gaps...
        </p>
        <p className="text-[10px] text-slate-500">
          Aggregating historical quiz attempts and analyzing concept-level trajectories
        </p>
      </div>
    )
  }

  // 2. Error State
  if (error) {
    return (
      <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-2">
        <div className="flex items-center gap-2 font-semibold">
          <span>⚠️</span>
          <span>Failed to Load Knowledge Gaps</span>
        </div>
        <p className="text-slate-300">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-medium text-xs transition cursor-pointer"
        >
          Retry
        </button>
      </div>
    )
  }

  // 3. No Data / Not loaded
  if (!knowledgeGaps) {
    return (
      <div className="p-8 text-center space-y-2 bg-slate-950/40 rounded-xl border border-slate-800/60">
        <span className="text-2xl">📊</span>
        <p className="text-xs text-slate-300 font-medium">No Knowledge Gap Profile Available</p>
        <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
          Complete a quiz assessment to generate your personalized knowledge gap profile.
        </p>
      </div>
    )
  }

  const { summary, gaps, weak_chunk_ids } = knowledgeGaps

  // 4. Insufficient Assessment Data State
  if (summary.assessed_chunks === 0) {
    return (
      <div className="space-y-4">
        <KnowledgeGapSummary
          summary={summary}
          weakChunkCount={0}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
        />
        <div className="p-6 text-center space-y-2 bg-slate-950/50 rounded-xl border border-slate-800/80">
          <span className="text-2xl block">📝</span>
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">
            Insufficient Quiz History
          </h4>
          <p className="text-[11px] text-slate-400 max-w-md mx-auto leading-relaxed">
            You need at least 2 quiz observations per concept before VIDYORA can calculate reliable,
            evidence-grounded knowledge gap classifications. Take the interactive quiz to begin tracking your progress.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 text-xs">
      {/* Learner Knowledge Gap Summary Header */}
      <KnowledgeGapSummary
        summary={summary}
        weakChunkCount={weak_chunk_ids.length}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
      />

      {/* Filter Controls */}
      <KnowledgeGapFilters
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        gaps={gaps}
      />

      {/* Filtered Concept Cards */}
      <div className="space-y-2.5">
        {filteredGaps.length > 0 ? (
          filteredGaps.map((gap) => (
            <KnowledgeGapCard
              key={gap.chunk_id}
              gap={gap}
              onReviewInVideo={onReviewInVideo}
              videoUrl={videoUrl}
              onAskTutor={onAskTutor}
              onPracticeQuiz={onPracticeQuiz}
              onStartRecovery={(g) => {
                if (onStartRecovery) {
                  onStartRecovery(g)
                } else {
                  setActiveRecoveryChunk(g)
                }
              }}
            />
          ))
        ) : (
          <div className="p-6 text-center bg-slate-950/40 rounded-xl border border-slate-800/60 text-slate-400 text-xs">
            No concepts match the <span className="font-semibold text-white">"{activeFilter}"</span> filter.
          </div>
        )}
      </div>

      {/* Targeted Learning Recovery Engine Modal */}
      {activeRecoveryChunk && (videoId || knowledgeGaps?.video_id) && (
        <LearningRecoveryView
          videoId={videoId || knowledgeGaps.video_id}
          chunk={activeRecoveryChunk}
          videoUrl={videoUrl}
          onClose={() => setActiveRecoveryChunk(null)}
          onReviewInVideo={onReviewInVideo}
          onPracticeQuiz={onPracticeQuiz}
          onRecoveryCompleted={() => {
            if (onRecoveryCompleted) {
              onRecoveryCompleted()
            }
          }}
        />
      )}
    </div>
  )
}

export default KnowledgeGapView
