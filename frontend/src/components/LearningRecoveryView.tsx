import React, { useEffect, useState } from 'react'
import type {
  AskVidyoraResponse,
  ChunkKnowledgeGap,
  RecoveryEvaluationResponse,
  RecoverySessionClientView,
} from '../types/ai'
import {
  askVidyoraApi,
  createRecoverySessionApi,
  fetchLatestChunkRecoverySessionApi,
  submitRecoverySessionApi,
} from '../services/aiApi'

interface LearningRecoveryViewProps {
  videoId: string
  chunk: ChunkKnowledgeGap
  videoUrl?: string
  onClose: () => void
  onReviewInVideo?: (videoUrl: string, timestamp: number) => void
  onRecoveryCompleted?: () => void
  onOpenAskTutor?: (question: string) => void
  onPracticeQuiz?: () => void
  isEmbedded?: boolean
}

export const LearningRecoveryView: React.FC<LearningRecoveryViewProps> = ({
  videoId,
  chunk,
  videoUrl,
  onClose,
  onReviewInVideo,
  onRecoveryCompleted,
  onOpenAskTutor,
  onPracticeQuiz,
  isEmbedded = false,
}) => {
  const [session, setSession] = useState<RecoverySessionClientView | null>(null)
  const [evaluation, setEvaluation] = useState<RecoveryEvaluationResponse | null>(null)
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [forceNewAttempt, setForceNewAttempt] = useState<boolean>(false)

  // Step 2: Understand follow-up state (Ask VIDYORA grounded tutor)
  const [tutorQuestion, setTutorQuestion] = useState<string>('')
  const [isAskingTutor, setIsAskingTutor] = useState<boolean>(false)
  const [tutorResponse, setTutorResponse] = useState<AskVidyoraResponse | null>(null)
  const [tutorError, setTutorError] = useState<string | null>(null)

  // Fetch or initialize recovery session
  useEffect(() => {
    let isMounted = true
    async function loadRecovery() {
      setIsLoading(true)
      setError(null)
      setEvaluation(null)
      setSelectedAnswers({})
      try {
        let resp: RecoverySessionClientView | null = null
        if (!forceNewAttempt) {
          resp = await fetchLatestChunkRecoverySessionApi(videoId, chunk.chunk_id)
        }
        if (!resp) {
          resp = await createRecoverySessionApi({
            videoId,
            chunkId: chunk.chunk_id,
            reuseExisting: !forceNewAttempt,
          })
        }
        if (isMounted && resp) {
          setSession(resp)
          // If session is already evaluated, display evaluation immediately
          if (resp.status === 'EVALUATED' && resp.question_results) {
            setEvaluation({
              session_id: resp.id,
              video_id: resp.video_id,
              chunk_id: resp.chunk_id,
              attempt_number: resp.attempt_number,
              total_questions: resp.question_results.length,
              correct_count: resp.question_results.filter((q) => q.is_correct).length,
              post_recovery_accuracy: resp.post_recovery_accuracy ?? 0,
              pre_recovery_accuracy: resp.pre_recovery_accuracy,
              absolute_improvement: resp.absolute_improvement ?? 0,
              recovery_result: resp.recovery_result ?? 'NOT_RECOVERED',
              result_summary: resp.result_summary ?? '',
              can_retry: resp.can_retry,
              question_results: resp.question_results,
              evaluated_at: resp.evaluated_at ?? new Date().toISOString(),
            })
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Failed to initiate recovery session.'
          setError(msg)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    void loadRecovery()
    return () => {
      isMounted = false
    }
  }, [videoId, chunk.chunk_id, forceNewAttempt])

  const handleRetrySession = () => {
    setForceNewAttempt(true)
  }

  const handleSelectOption = (questionId: string, option: string) => {
    if (evaluation) return // Locked if already submitted
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: option,
    }))
  }

  const handleSubmit = async () => {
    if (!session) return
    setIsSubmitting(true)
    setError(null)

    try {
      const evalResp = await submitRecoverySessionApi({
        sessionId: session.id,
        selectedAnswers,
      })
      setEvaluation(evalResp)
      if (onRecoveryCompleted) {
        onRecoveryCompleted()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to evaluate micro-quiz.'
      setError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReviewClick = (timestamp: number) => {
    if (onReviewInVideo) {
      onReviewInVideo(videoUrl || '', timestamp)
    }
  }

  const handleAskTutor = async (qText: string) => {
    if (!qText.trim() || isAskingTutor) return
    setIsAskingTutor(true)
    setTutorError(null)
    try {
      const fullQuery = `Regarding concept "${session?.explanation_title || 'this section'}" around ${session?.source_timestamp.formatted_time || ''}: ${qText}`
      const resp = await askVidyoraApi({
        videoId,
        question: fullQuery,
      })
      setTutorResponse(resp)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query Ask VIDYORA tutor.'
      setTutorError(msg)
    } finally {
      setIsAskingTutor(false)
    }
  }

  const allAnswered =
    session &&
    session.micro_quiz.length > 0 &&
    session.micro_quiz.every((q) => Boolean(selectedAnswers[q.id]))

  // Helper for status badge styling
  const getResultBadgeStyle = (result: string) => {
    switch (result) {
      case 'RECOVERED':
        return {
          bg: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
          indicator: 'bg-emerald-400',
          label: 'RECOVERED',
        }
      case 'IMPROVED':
        return {
          bg: 'bg-amber-500/15 border-amber-500/40 text-amber-300',
          indicator: 'bg-amber-400',
          label: 'IMPROVED',
        }
      case 'NOT_RECOVERED':
        return {
          bg: 'bg-rose-500/15 border-rose-500/40 text-rose-300',
          indicator: 'bg-rose-400',
          label: 'NOT RECOVERED',
        }
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return {
          bg: 'bg-slate-800 border-slate-700 text-slate-300',
          indicator: 'bg-slate-400',
          label: 'INSUFFICIENT EVIDENCE',
        }
    }
  }

  const content = (
    <div className={`relative w-full ${isEmbedded ? 'bg-slate-900 border border-slate-800 rounded-2xl shadow-xl' : 'max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl my-auto max-h-[92vh]'} overflow-hidden flex flex-col text-slate-200 text-xs`}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-950/80 shrink-0">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-base">🎯</span>
            <h3 className="text-sm font-bold text-white tracking-wide">
              Targeted Learning Recovery
            </h3>
            {session && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 font-semibold font-mono">
                Attempt {session.attempt_number} of 2
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400">
            Source-grounded remediation focused on your identified conceptual hurdle.
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer text-xs flex items-center gap-1.5"
          title="Close recovery and return to knowledge gaps"
        >
          <span>←</span>
          <span>{isEmbedded ? 'Back to Gaps' : 'Close'}</span>
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="p-5 space-y-5 overflow-y-auto flex-1">
          {/* Loading State */}
          {isLoading && (
            <div className="p-12 text-center space-y-3">
              <div className="w-9 h-9 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto"></div>
              <p className="text-xs text-indigo-300 font-semibold">
                Synthesizing targeted explanation and micro-quiz...
              </p>
              <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                Grounded strictly in lecture segment {chunk.source_timestamp.formatted_time}. Gemini generates explanation; backend evaluates deterministically.
              </p>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <span>⚠️</span>
                <span>Recovery Engine Notice</span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">{error}</p>
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleRetrySession}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs transition cursor-pointer"
                >
                  Retry Recovery
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition cursor-pointer"
                >
                  Back to Knowledge Gaps
                </button>
              </div>
            </div>
          )}

          {/* Loaded Session View */}
          {session && !isLoading && (
            <>
              {/* Concept & Diagnostic Context Banner */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                      Flagged Concept Segment
                    </span>
                    <h4 className="text-xs font-bold text-white">
                      {session.explanation_title || `Concept #${session.chunk_index + 1}`}
                    </h4>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300">
                      Before Score: <strong className="text-rose-400">{Math.round(session.pre_recovery_accuracy)}%</strong>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleReviewClick(session.source_timestamp.timestamp)}
                      className="px-2.5 py-1 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 text-[11px] font-medium transition cursor-pointer flex items-center gap-1.5"
                      title="Jump to video timestamp"
                    >
                      <span>⏱️</span>
                      <span>Review in Video ({session.source_timestamp.formatted_time})</span>
                    </button>
                  </div>
                </div>

                <div className="text-[11px] text-slate-300 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/60 space-y-1">
                  <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider block">
                    Why This Concept Was Flagged
                  </span>
                  <p className="leading-snug">{session.originating_evidence}</p>
                </div>
              </div>

              {/* Step 1: Review - Targeted Explanation */}
              {session.targeted_explanation && (
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <span>📖</span>
                    <span>Step 1: Review (Source-Grounded Explanation)</span>
                  </div>
                  <div className="text-slate-300 text-xs leading-relaxed space-y-2 whitespace-pre-line">
                    {session.targeted_explanation}
                  </div>

                  {session.worked_example && (
                    <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-800/40 text-indigo-200 text-xs space-y-1">
                      <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block">
                        💡 Concrete Worked Example
                      </span>
                      <p className="leading-relaxed">{session.worked_example}</p>
                    </div>
                  )}

                  {session.key_takeaway && (
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs flex items-start gap-2">
                      <span className="text-amber-400 font-bold">⭐</span>
                      <p className="text-slate-300">
                        <strong className="text-white">Key Takeaway:</strong> {session.key_takeaway}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Step 2: Understand - Ask Follow-up Questions (Ask VIDYORA Tutor) */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/90 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-wider">
                    <span>💬</span>
                    <span>Step 2: Understand (Ask Tutor Follow-ups)</span>
                  </div>
                  {onOpenAskTutor && (
                    <button
                      type="button"
                      onClick={() =>
                        onOpenAskTutor(
                          tutorQuestion ||
                            `Can you clarify the concept "${session.explanation_title || 'this section'}" covered around ${session.source_timestamp.formatted_time}?`
                        )
                      }
                      className="text-[11px] text-indigo-400 hover:text-indigo-300 transition cursor-pointer flex items-center gap-1 font-medium"
                      title="Open full conversation in Ask VIDYORA"
                    >
                      <span>Open in Chat Suite</span>
                      <span>↗</span>
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 leading-snug">
                  Ask targeted questions to clear any confusion before attempting the practice micro-quiz. Responses are strictly grounded in this lecture's transcript.
                </p>

                {/* Suggested prompt chips */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {[
                    'Can you provide an intuitive real-world analogy?',
                    'What common misconceptions should I avoid?',
                    'Why is this concept crucial in this lecture?',
                  ].map((promptText) => (
                    <button
                      key={promptText}
                      type="button"
                      onClick={() => {
                        setTutorQuestion(promptText)
                        void handleAskTutor(promptText)
                      }}
                      disabled={isAskingTutor}
                      className="px-2.5 py-1 rounded-md bg-indigo-950/40 hover:bg-indigo-900/50 text-indigo-300 border border-indigo-800/40 text-[10px] transition cursor-pointer text-left font-medium"
                    >
                      "{promptText}"
                    </button>
                  ))}
                </div>

                {/* Interactive input bar */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    id="input-tutor-question"
                    type="text"
                    value={tutorQuestion}
                    onChange={(e) => setTutorQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !isAskingTutor && tutorQuestion.trim()) {
                        void handleAskTutor(tutorQuestion)
                      }
                    }}
                    placeholder={`Ask a question about ${session.explanation_title || 'this concept'}...`}
                    className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    id="btn-tutor-ask"
                    type="button"
                    onClick={() => void handleAskTutor(tutorQuestion)}
                    disabled={isAskingTutor || !tutorQuestion.trim()}
                    className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold text-xs transition cursor-pointer flex items-center gap-1.5 shrink-0"
                  >
                    {isAskingTutor ? (
                      <>
                        <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                        <span>Asking...</span>
                      </>
                    ) : (
                      <span>Ask Tutor</span>
                    )}
                  </button>
                </div>

                {/* Tutor error notice */}
                {tutorError && (
                  <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                    {tutorError}
                  </div>
                )}

                {/* Grounded Tutor Answer */}
                {tutorResponse && (
                  <div className="p-3.5 rounded-lg bg-slate-900/90 border border-indigo-500/40 space-y-2 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-semibold text-indigo-300 flex items-center gap-1.5">
                        <span>🤖</span>
                        <span>Ask VIDYORA Response:</span>
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">{tutorResponse.model_used}</span>
                    </div>
                    <p className="text-slate-200 leading-relaxed whitespace-pre-line text-[11px]">
                      {tutorResponse.answer}
                    </p>

                    {/* Citations & Timestamps */}
                    {tutorResponse.sources && tutorResponse.sources.length > 0 && (
                      <div className="pt-2 border-t border-slate-800 space-y-1.5">
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                          Verified Transcript Citations:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {tutorResponse.sources.map((src) => (
                            <button
                              key={src.chunk_id}
                              type="button"
                              onClick={() => handleReviewClick(src.start_time)}
                              className="px-2 py-0.5 rounded bg-indigo-950/60 hover:bg-indigo-900/80 text-indigo-300 border border-indigo-700/50 text-[10px] font-mono transition cursor-pointer flex items-center gap-1"
                              title={src.text}
                            >
                              <span>⏱️ {src.source_formatted_start}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Evaluation Result View (Displayed after submission) */}
              {evaluation ? (
                <div className="p-5 rounded-xl bg-slate-950/90 border border-slate-800 space-y-5">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                        Step 4 & 5: Reassess & Measure Improvement
                      </span>
                      <h4 className="text-sm font-bold text-white">
                        {session.explanation_title}
                      </h4>
                    </div>

                    <div className="flex items-center gap-2">
                      {(() => {
                        const style = getResultBadgeStyle(evaluation.recovery_result)
                        return (
                          <span
                            className={`px-3 py-1 rounded-full border text-xs font-bold flex items-center gap-2 ${style.bg}`}
                          >
                            <span className={`w-2 h-2 rounded-full ${style.indicator}`}></span>
                            <span>{style.label}</span>
                          </span>
                        )
                      })()}
                    </div>
                  </div>

                  {/* Summary Callout */}
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                    {evaluation.result_summary}
                  </p>

                  {/* Performance Comparison Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                    <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                        Before Score
                      </span>
                      <span className="text-base font-bold text-rose-400">
                        {Math.round(evaluation.pre_recovery_accuracy)}%
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                        Recovery Quiz
                      </span>
                      <span className="text-base font-bold text-white font-mono">
                        {evaluation.correct_count} / {evaluation.total_questions}
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                        After Score
                      </span>
                      <span className="text-base font-bold text-emerald-400">
                        {Math.round(evaluation.post_recovery_accuracy)}%
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                      <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                        Improvement
                      </span>
                      <span className="text-base font-bold text-indigo-400">
                        {evaluation.absolute_improvement >= 0 ? `+${evaluation.absolute_improvement}%` : `${evaluation.absolute_improvement}%`}
                      </span>
                    </div>
                  </div>

                  {/* Question-by-Question Review */}
                  <div className="space-y-3 pt-2">
                    <h5 className="text-xs font-bold text-white uppercase tracking-wider">
                      Question Review & Rationales
                    </h5>
                    {evaluation.question_results.map((qr, idx) => (
                      <div
                        key={qr.question_id}
                        className={`p-3.5 rounded-lg border space-y-2 ${
                          qr.is_correct
                            ? 'bg-emerald-950/20 border-emerald-800/40'
                            : 'bg-rose-950/20 border-rose-800/40'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="font-semibold text-white text-xs">
                            {idx + 1}. {qr.question}
                          </p>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              qr.is_correct
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-rose-500/20 text-rose-300'
                            }`}
                          >
                            {qr.is_correct ? '✓ Correct' : '✗ Incorrect'}
                          </span>
                        </div>

                        <div className="text-[11px] space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400">Your Answer:</span>
                            <span
                              className={
                                qr.is_correct ? 'text-emerald-300 font-medium' : 'text-rose-300 font-medium'
                              }
                            >
                              {qr.selected_answer || '(No answer provided)'}
                            </span>
                          </div>
                          {!qr.is_correct && (
                            <div className="flex items-center gap-2">
                              <span className="text-slate-400">Correct Answer:</span>
                              <span className="text-emerald-300 font-medium">{qr.correct_answer}</span>
                            </div>
                          )}
                        </div>

                        <p className="text-[11px] text-slate-300 leading-snug bg-slate-900/60 p-2 rounded border border-slate-800/60">
                          <strong className="text-slate-200">Explanation:</strong> {qr.explanation}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Actions Post-Evaluation */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => handleReviewClick(session.source_timestamp.timestamp)}
                      className="px-3.5 py-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 font-medium text-xs transition cursor-pointer flex items-center gap-1.5"
                    >
                      <span>⏱️</span>
                      <span>Review Lecture Moment ({session.source_timestamp.formatted_time})</span>
                    </button>

                    <div className="flex items-center gap-2 flex-wrap">
                      {onPracticeQuiz && (
                        <button
                          type="button"
                          onClick={onPracticeQuiz}
                          className="px-3.5 py-2 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 font-medium text-xs transition cursor-pointer flex items-center gap-1.5"
                          title="Take the full lecture quiz to reassess your mastery"
                        >
                          <span>🎯</span>
                          <span>Reassess on Quiz</span>
                        </button>
                      )}
                      {evaluation.can_retry && (
                        <button
                          type="button"
                          onClick={handleRetrySession}
                          className="px-3.5 py-2 rounded-lg bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 font-medium text-xs transition cursor-pointer"
                        >
                          Try Recovery Again (Attempt 2)
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs transition cursor-pointer"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* Micro-Quiz Form (Before Submission) */
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-indigo-400 font-bold text-xs uppercase tracking-wider">
                          ✍️ Step 3: Practice (Targeted Micro-Assessment)
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          ({session.micro_quiz.length} Questions)
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Answer all questions to deterministically evaluate conceptual recovery.
                      </p>
                    </div>
                  </div>

                  {/* Question Cards */}
                  <div className="space-y-4">
                    {session.micro_quiz.map((q, idx) => (
                      <div
                        key={q.id}
                        className="p-3.5 rounded-xl bg-slate-900 border border-slate-800/80 space-y-2.5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-xs font-semibold text-white leading-snug">
                            <span className="text-indigo-400 font-mono mr-1.5">{idx + 1}.</span>
                            {q.question}
                          </p>
                          <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                            {q.difficulty}
                          </span>
                        </div>

                        {/* 4 Options */}
                        <div className="space-y-1.5 pt-1">
                          {q.options.map((opt) => {
                            const isSelected = selectedAnswers[q.id] === opt
                            return (
                              <button
                                key={opt}
                                type="button"
                                onClick={() => handleSelectOption(q.id, opt)}
                                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition border flex items-center gap-2.5 cursor-pointer ${
                                  isSelected
                                    ? 'bg-indigo-600/25 border-indigo-500 text-white font-medium shadow-sm shadow-indigo-950/30'
                                    : 'bg-slate-950/50 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/50'
                                }`}
                              >
                                <span
                                  className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${
                                    isSelected
                                      ? 'border-indigo-400 bg-indigo-500 text-white text-[9px]'
                                      : 'border-slate-600'
                                  }`}
                                >
                                  {isSelected && '✓'}
                                </span>
                                <span className="leading-snug">{opt}</span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Submission Action Bar */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                    <span className="text-[11px] text-slate-400">
                      {allAnswered
                        ? 'All questions answered.'
                        : `Please answer all ${session.micro_quiz.length} questions to submit.`}
                    </span>

                    <button
                      id="btn-submit-recovery"
                      type="button"
                      disabled={!allAnswered || isSubmitting}
                      onClick={handleSubmit}
                      className={`px-5 py-2 rounded-lg font-bold text-xs transition flex items-center gap-2 cursor-pointer ${
                        allAnswered && !isSubmitting
                          ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-950/40'
                          : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
                      }`}
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                          <span>Evaluating...</span>
                        </>
                      ) : (
                        <span>Submit for Evaluation →</span>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    )

    if (isEmbedded) {
      return content
    }

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md overflow-y-auto">
        {content}
      </div>
    )
  }

export default LearningRecoveryView
