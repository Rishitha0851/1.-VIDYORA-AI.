import React from 'react'
import type { ChunkKnowledgeGap } from '../types/ai'

interface KnowledgeGapCardProps {
  gap: ChunkKnowledgeGap
  onReviewInVideo?: (videoUrl: string, timestamp: number) => void
  videoUrl?: string
  onStartRecovery?: (gap: ChunkKnowledgeGap) => void
  onAskTutor?: (gap: ChunkKnowledgeGap) => void
  onPracticeQuiz?: () => void
}

export const KnowledgeGapCard: React.FC<KnowledgeGapCardProps> = ({
  gap,
  onReviewInVideo,
  videoUrl,
  onStartRecovery,
  onAskTutor,
  onPracticeQuiz,
}) => {
  const accuracyPct = Math.round(gap.accuracy * 100)

  // Visual cues based strictly on backend classification
  const getBadgeStyle = () => {
    switch (gap.classification) {
      case 'WEAK':
        return {
          container: 'bg-slate-900/90 border-rose-500/40 shadow-sm shadow-rose-950/20',
          badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
          indicator: 'bg-rose-500',
          label: 'Needs Review',
        }
      case 'DEVELOPING':
        return {
          container: 'bg-slate-900/80 border-amber-500/30',
          badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
          indicator: 'bg-amber-500',
          label: 'Developing',
        }
      case 'STRONG':
        return {
          container: 'bg-slate-900/70 border-emerald-500/25',
          badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
          indicator: 'bg-emerald-500',
          label: 'Mastered',
        }
      case 'INSUFFICIENT_DATA':
      default:
        return {
          container: 'bg-slate-900/40 border-slate-800/60 opacity-80',
          badge: 'bg-slate-800 text-slate-400 border-slate-700/60',
          indicator: 'bg-slate-500',
          label: 'Unassessed',
        }
    }
  }

  const getTrendBadge = () => {
    switch (gap.trend) {
      case 'IMPROVING':
        return (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-medium inline-flex items-center gap-1">
            <span>↗</span>
            <span>Improving</span>
          </span>
        )
      case 'DECLINING':
        return (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-800/40 font-medium inline-flex items-center gap-1">
            <span>↘</span>
            <span>Declining</span>
          </span>
        )
      case 'STABLE':
        return (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-medium inline-flex items-center gap-1">
            <span>→</span>
            <span>Stable</span>
          </span>
        )
      case 'INSUFFICIENT_DATA':
      default:
        return null
    }
  }

  const isRecovered = gap.has_recovered || gap.recovery_status === 'improvement_demonstrated'
  const isInProgress = gap.recovery_status === 'recovery_in_progress'

  const style = getBadgeStyle()

  const handleReviewClick = () => {
    if (onReviewInVideo && gap.source_timestamp) {
      onReviewInVideo(videoUrl || '', gap.source_timestamp.timestamp)
    }
  }

  return (
    <div className={`p-4 rounded-xl border space-y-3 transition ${style.container}`}>
      {/* Header: Concept Tag, Badges & Timestamp */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-white">
              {gap.concept_name || `Concept Segment #${gap.chunk_index + 1}`}
            </span>
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border inline-flex items-center gap-1.5 ${style.badge}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${style.indicator}`}></span>
              <span>{style.label}</span>
            </span>

            {/* Recovery Lifecycle Status */}
            {isRecovered && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 font-semibold inline-flex items-center gap-1">
                <span>✨</span>
                <span>Improvement Demonstrated</span>
              </span>
            )}
            {isInProgress && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-300 border border-amber-500/40 font-semibold inline-flex items-center gap-1">
                <span>🔄</span>
                <span>Recovery in Progress</span>
              </span>
            )}

            {/* Empirical Confidence Level */}
            {gap.confidence_level && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-300 border border-slate-700/60 font-mono">
                {gap.confidence_level}
              </span>
            )}

            {getTrendBadge()}
          </div>
          {gap.source_timestamp && (
            <span className="text-[10px] font-mono text-slate-400 block">
              Lecture Moment: {gap.source_timestamp.formatted_time} ({gap.source_timestamp.label})
            </span>
          )}
        </div>

        {/* Action Buttons: Ask Tutor, Practice Quiz, Review in Video, Start Recovery */}
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {onAskTutor && (
            <button
              id={`btn-ask-tutor-${gap.chunk_id}`}
              type="button"
              onClick={() => onAskTutor(gap)}
              className="px-2.5 py-1.5 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition cursor-pointer inline-flex items-center gap-1.5"
              title="Ask VIDYORA tutor about this concept"
            >
              <span>💬</span>
              <span>Ask Tutor</span>
            </button>
          )}

          {onStartRecovery && (gap.classification === 'WEAK' || gap.classification === 'DEVELOPING' || isRecovered || isInProgress) && (
            <button
              id={`btn-start-recovery-${gap.chunk_id}`}
              type="button"
              onClick={() => onStartRecovery(gap)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer inline-flex items-center gap-1.5 shadow-sm ${
                isRecovered
                  ? 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40'
                  : isInProgress
                  ? 'bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40'
                  : 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/40'
              }`}
              title={
                isRecovered
                  ? 'View completed recovery assessment'
                  : isInProgress
                  ? 'Continue active recovery session'
                  : 'Start targeted learning recovery'
              }
            >
              <span>{isRecovered ? '✨' : isInProgress ? '🔄' : '🎯'}</span>
              <span>
                {isRecovered
                  ? 'View Recovery'
                  : isInProgress
                  ? 'Continue Recovery'
                  : 'Start Recovery'}
              </span>
            </button>
          )}

          {onPracticeQuiz && (
            <button
              type="button"
              onClick={onPracticeQuiz}
              className="px-2.5 py-1.5 rounded-lg bg-violet-500/15 hover:bg-violet-500/25 text-violet-300 border border-violet-500/30 text-xs font-medium transition cursor-pointer inline-flex items-center gap-1.5"
              title="Practice full video quiz"
            >
              <span>🎯</span>
              <span>Quiz</span>
            </button>
          )}

          {gap.source_timestamp && (
            <button
              type="button"
              onClick={handleReviewClick}
              className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 text-xs font-medium transition cursor-pointer inline-flex items-center gap-1.5 group"
              title={`Review lecture at ${gap.source_timestamp.formatted_time}`}
            >
              <span>⏱️</span>
              <span>{gap.source_timestamp.formatted_time}</span>
              <span className="text-[10px] text-slate-400 group-hover:translate-x-0.5 transition">↗</span>
            </button>
          )}
        </div>
      </div>

      {/* Concept Summary / Excerpt */}
      {gap.chunk_summary_text && (
        <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          "{gap.chunk_summary_text}"
        </p>
      )}

      {/* Recommended Learning Action */}
      {gap.recommended_action && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-indigo-950/25 border border-indigo-900/40 text-[11px] text-indigo-200">
          <span className="text-indigo-400">💡</span>
          <span><strong className="text-white">Next Step:</strong> {gap.recommended_action}</span>
        </div>
      )}

      {/* Evidence & Diagnosis Details */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
        {/* Metric Summary */}
        <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 space-y-1">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Assessment Record
          </span>
          {gap.total_observations > 0 ? (
            <div className="flex items-center gap-2 flex-wrap text-[11px] font-mono">
              <span className="text-white font-bold">{accuracyPct}% accuracy</span>
              <span className="text-slate-500">•</span>
              <span className="text-emerald-400">{gap.correct_count} correct</span>
              <span className="text-slate-500">•</span>
              <span className="text-rose-400">{gap.incorrect_count} incorrect</span>
              {(gap.unanswered_count ?? 0) > 0 && (
                <>
                  <span className="text-slate-500">•</span>
                  <span className="text-amber-400">{gap.unanswered_count} skipped</span>
                </>
              )}
              <span className="text-slate-500">•</span>
              <span className="text-slate-400">{gap.total_observations} total</span>
            </div>
          ) : (
            <span className="text-slate-500 text-[11px] italic">
              No questions answered yet
            </span>
          )}
        </div>

        {/* Explainable Diagnosis Reason */}
        <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 space-y-1">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Diagnostic Evidence
          </span>
          <p className="text-[11px] text-slate-300 leading-snug">
            {gap.reason}
          </p>
        </div>
      </div>
    </div>
  )
}

export default KnowledgeGapCard
