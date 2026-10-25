import React, { useEffect, useState } from 'react'
import type {
  QuizAttemptHistoryItem,
  QuizClientView,
  QuizDifficulty,
  QuizEvaluationResponse,
} from '../types/ai'
import { fetchQuizAttemptsApi } from '../services/aiApi'

interface QuizViewProps {
  quiz: QuizClientView
  evaluation: QuizEvaluationResponse | null
  isSubmitting: boolean
  submissionError: string | null
  modelUsed?: string
  chunkCount?: number
  onSubmitAnswers: (selectedAnswers: Record<string, string>) => void
  onRetakeQuiz: () => void
  onRegenerateQuiz?: () => void
  onTimestampClick?: (seconds: number) => void
}

export const QuizView: React.FC<QuizViewProps> = ({
  quiz,
  evaluation,
  isSubmitting,
  submissionError,
  modelUsed,
  chunkCount,
  onSubmitAnswers,
  onRetakeQuiz,
  onRegenerateQuiz,
  onTimestampClick,
}) => {
  // Local state for learner's selected answers (question_id -> chosen option string)
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({})
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0)
  const [showConfirmIncomplete, setShowConfirmIncomplete] = useState<boolean>(false)

  // Step 13 Phase 4: Historical quiz attempts loaded from PostgreSQL
  const [historyAttempts, setHistoryAttempts] = useState<QuizAttemptHistoryItem[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false)
  const [showHistory, setShowHistory] = useState<boolean>(false)

  useEffect(() => {
    let isMounted = true
    if (!quiz.quiz_id) return

    queueMicrotask(() => {
      if (isMounted) setIsLoadingHistory(true)
    })
    fetchQuizAttemptsApi(quiz.quiz_id)
      .then((res) => {
        if (isMounted) {
          setHistoryAttempts(res.attempts)
        }
      })
      .catch(() => {
        // Gracefully maintain empty history on failure
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingHistory(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [quiz.quiz_id, evaluation])

  const questions = quiz.questions
  const currentQuestion = questions[currentQuestionIndex]
  const totalQuestions = questions.length
  const answeredCount = Object.keys(selectedAnswers).filter((k) => selectedAnswers[k]).length
  const isAllAnswered = answeredCount === totalQuestions

  const handleSelectOption = (questionId: string, option: string) => {
    if (evaluation || isSubmitting) return
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: option,
    }))
    setShowConfirmIncomplete(false)
  }

  const handleNext = () => {
    if (currentQuestionIndex < totalQuestions - 1) {
      setCurrentQuestionIndex((prev) => prev + 1)
    }
  }

  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1)
    }
  }

  const handleSubmit = () => {
    if (isSubmitting) return
    if (!isAllAnswered && !showConfirmIncomplete) {
      setShowConfirmIncomplete(true)
      return
    }
    setShowConfirmIncomplete(false)
    onSubmitAnswers(selectedAnswers)
  }

  const handleRetake = () => {
    setSelectedAnswers({})
    setCurrentQuestionIndex(0)
    setShowConfirmIncomplete(false)
    onRetakeQuiz()
  }

  const renderDifficultyBadge = (difficulty: QuizDifficulty) => {
    switch (difficulty) {
      case 'easy':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 uppercase tracking-wider">
            Easy
          </span>
        )
      case 'hard':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/60 uppercase tracking-wider">
            Hard
          </span>
        )
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/60 uppercase tracking-wider">
            Medium
          </span>
        )
    }
  }

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Header Meta Bar */}
      <div className="flex items-center justify-between bg-slate-950/80 px-3.5 py-2 rounded-xl border border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-indigo-400 animate-pulse"></span>
          <span>
            Quiz grounded in <strong className="text-slate-200">{chunkCount ?? 'all'}</strong> knowledge chunks
          </span>
        </div>
        <div className="flex items-center gap-2">
          {modelUsed && (
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 font-medium">
              {modelUsed}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800 font-mono text-[10px]">
            {totalQuestions} Questions
          </span>
        </div>
      </div>

      {/* Step 13 Phase 4: Quiz Attempt History Section */}
      <div className="bg-slate-950/80 border border-slate-800/90 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <span>📊</span>
              <span>Learner Attempt History</span>
            </span>
            <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono text-[10px]">
              {historyAttempts.length} {historyAttempts.length === 1 ? 'attempt' : 'attempts'}
            </span>
          </div>

          <button
            type="button"
            onClick={() => setShowHistory((prev) => !prev)}
            className="text-[11px] font-medium text-indigo-400 hover:text-indigo-300 transition cursor-pointer flex items-center gap-1"
          >
            <span>{showHistory ? 'Hide Progression ▲' : 'View Progression ▼'}</span>
          </button>
        </div>

        {showHistory && (
          <div className="pt-2 border-t border-slate-800/80 space-y-2 animate-fadeIn">
            {isLoadingHistory && (
              <p className="text-[11px] text-slate-400 py-1 flex items-center gap-2">
                <span className="animate-spin text-xs">⌛</span>
                <span>Retrieving attempt history from PostgreSQL...</span>
              </p>
            )}
            {!isLoadingHistory && historyAttempts.length === 0 && (
              <p className="text-[11px] text-slate-500 py-1">
                No previous attempts recorded yet. Submit your answers to log your first attempt.
              </p>
            )}
            {!isLoadingHistory && historyAttempts.length > 0 && (
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {historyAttempts.map((att, idx) => (
                  <div
                    key={att.attempt_id}
                    className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 flex items-center justify-between text-[11px]"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-200">
                          Attempt #{historyAttempts.length - idx}
                        </span>
                        <span
                          className={`px-1.5 py-0.2 rounded text-[10px] font-semibold uppercase ${
                            att.performance_tier === 'Strong'
                              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
                              : att.performance_tier === 'Developing'
                              ? 'bg-amber-950/60 text-amber-400 border border-amber-800/60'
                              : 'bg-rose-950/60 text-rose-400 border border-rose-800/60'
                          }`}
                        >
                          {att.performance_tier}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400">
                        {new Date(att.submitted_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="text-right">
                      <span className="font-mono text-xs font-bold text-white">
                        {att.score_percentage}%
                      </span>
                      <p className="text-[10px] text-slate-400 font-mono">
                        {att.score}/{att.total_questions} correct
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>


      {/* Submission Error Banner */}
      {submissionError && (
        <div className="bg-rose-950/40 border border-rose-800/80 text-rose-300 p-3 rounded-xl flex items-start gap-2.5">
          <span className="text-base shrink-0">⚠️</span>
          <div>
            <p className="font-semibold text-rose-200">Evaluation Error</p>
            <p className="text-[11px] text-rose-300/90">{submissionError}</p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* VIEW A: EVALUATED RESULTS & ADAPTIVE FEEDBACK                       */}
      {/* ------------------------------------------------------------------ */}
      {evaluation ? (
        <div className="space-y-4">
          {/* Score & Tier Hero Card */}
          <div
            className={`p-4 rounded-2xl border shadow-xl relative overflow-hidden ${
              evaluation.performance_tier === 'Strong'
                ? 'bg-gradient-to-br from-emerald-950/30 via-slate-900 to-slate-950 border-emerald-500/30'
                : evaluation.performance_tier === 'Developing'
                ? 'bg-gradient-to-br from-amber-950/30 via-slate-900 to-slate-950 border-amber-500/30'
                : 'bg-gradient-to-br from-rose-950/30 via-slate-900 to-slate-950 border-rose-500/30'
            }`}
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-lg">
                    {evaluation.performance_tier === 'Strong' ? '🏆' : evaluation.performance_tier === 'Developing' ? '⚡' : '📚'}
                  </span>
                  <span
                    className={`text-xs uppercase tracking-wider font-bold px-2 py-0.5 rounded-full border ${
                      evaluation.performance_tier === 'Strong'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : evaluation.performance_tier === 'Developing'
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {evaluation.performance_tier}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white tracking-tight">
                  Quiz Completed!
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed max-w-xl">
                  {evaluation.performance_summary}
                </p>
              </div>

              {/* Big Score Display */}
              <div className="flex md:flex-col items-baseline md:items-end justify-between border-t md:border-t-0 pt-3 md:pt-0 border-slate-800">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-black text-white font-mono">
                    {evaluation.score_percentage}%
                  </span>
                </div>
                <span className="text-slate-400 text-[11px] font-mono">
                  {evaluation.correct_count} of {evaluation.total_questions} correct
                </span>
              </div>
            </div>

            {/* Weak Concepts / Chunks Review Alert */}
            {evaluation.weak_chunk_ids && evaluation.weak_chunk_ids.length > 0 && (
              <div className="mt-3.5 pt-3 border-t border-slate-800/80 flex items-start gap-2 text-[11px] text-amber-300/90">
                <span className="shrink-0 text-amber-400">💡</span>
                <div>
                  <span className="font-semibold text-amber-200">Recommended Review: </span>
                  <span>
                    Questions missed relate to {evaluation.weak_chunk_ids.length} lecture concept section{evaluation.weak_chunk_ids.length > 1 ? 's' : ''}. Use the source timestamp buttons below or the Gaps tab to review the exact moments in the video.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between gap-3 pt-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Detailed Question Review ({evaluation.question_results.length})
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRetake}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs transition cursor-pointer border border-slate-700/60"
              >
                🔄 Retake Quiz
              </button>
              {onRegenerateQuiz && (
                <button
                  type="button"
                  onClick={onRegenerateQuiz}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition cursor-pointer shadow-sm shadow-indigo-600/20"
                >
                  ✨ Generate New Quiz
                </button>
              )}
            </div>
          </div>

          {/* Question-by-Question Review Cards */}
          <div className="space-y-3">
            {evaluation.question_results.map((res, idx) => (
              <div
                key={res.question_id || idx}
                className={`p-4 rounded-xl border space-y-3 transition ${
                  res.is_correct
                    ? 'bg-slate-900/60 border-emerald-500/25'
                    : 'bg-slate-900/60 border-rose-500/25'
                }`}
              >
                {/* Question Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                        res.is_correct
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                      }`}
                    >
                      {res.is_correct ? '✓' : '✗'}
                    </span>
                    <div>
                      <span className="text-[10px] text-slate-400 font-mono block">Question {idx + 1}</span>
                      <h4 className="text-xs font-semibold text-slate-100 leading-snug">{res.question}</h4>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {renderDifficultyBadge(res.difficulty)}
                    {res.source_timestamp && (
                      <button
                        type="button"
                        onClick={() => onTimestampClick?.(res.source_timestamp.timestamp)}
                        className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-950 text-indigo-400 border border-slate-800 hover:border-indigo-600 transition cursor-pointer"
                        title={res.source_timestamp.label}
                      >
                        ⏱ {res.source_timestamp.formatted_time}
                      </button>
                    )}
                  </div>
                </div>

                {/* Answers Breakdown */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                  {/* Learner's Selected Answer */}
                  <div
                    className={`p-2.5 rounded-lg border flex flex-col justify-between ${
                      res.is_correct
                        ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-200'
                        : 'bg-rose-950/20 border-rose-800/40 text-rose-200'
                    }`}
                  >
                    <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                      Your Answer:
                    </span>
                    <span className="font-medium">
                      {res.selected_answer || <em className="text-slate-500 italic">No answer submitted</em>}
                    </span>
                  </div>

                  {/* Authoritative Correct Answer */}
                  <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-emerald-200 flex flex-col justify-between">
                    <span className="text-[10px] uppercase font-semibold text-emerald-400 block mb-1">
                      Correct Answer:
                    </span>
                    <span className="font-medium text-emerald-100 font-semibold">{res.correct_answer}</span>
                  </div>
                </div>

                {/* Explanation Card */}
                {res.explanation && (
                  <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800/80 space-y-1">
                    <div className="flex items-center gap-1.5 text-indigo-400 font-semibold text-[10px] uppercase tracking-wider">
                      <span>💡 Educational Explanation</span>
                    </div>
                    <p className="text-slate-300 text-xs leading-relaxed">{res.explanation}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* ------------------------------------------------------------------ */
        /* VIEW B: ACTIVE QUIZ ANSWERING EXPERIENCE                            */
        /* ------------------------------------------------------------------ */
        <div className="space-y-4">
          {/* Question Navigation Bar & Progress */}
          <div className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono text-slate-400 block">
                  QUESTION {currentQuestionIndex + 1} OF {totalQuestions}
                </span>
                <h3 className="text-xs font-semibold text-white">
                  {quiz.title}
                </h3>
              </div>
              <div className="text-right">
                <span className="text-[11px] font-mono text-indigo-400 font-medium">
                  {answeredCount} of {totalQuestions} answered
                </span>
              </div>
            </div>

            {/* Question Quick-Jump Pills */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1">
              {questions.map((q, idx) => {
                const isAnswered = Boolean(selectedAnswers[q.id])
                const isCurrent = idx === currentQuestionIndex
                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => setCurrentQuestionIndex(idx)}
                    className={`h-7 w-7 rounded-lg text-[11px] font-mono font-bold transition cursor-pointer flex items-center justify-center border ${
                      isCurrent
                        ? 'bg-indigo-600 text-white border-indigo-400 shadow-md shadow-indigo-600/30 ring-2 ring-indigo-400/40'
                        : isAnswered
                        ? 'bg-slate-800 text-emerald-400 border-emerald-600/50'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {idx + 1}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Current Question Card */}
          {currentQuestion && (
            <div className="bg-slate-900/90 p-4 rounded-2xl border border-slate-800/90 space-y-4 shadow-xl">
              {/* Question Header & Meta */}
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-100 leading-snug">
                  {currentQuestionIndex + 1}. {currentQuestion.question}
                </span>
                <div className="flex items-center gap-1.5 shrink-0">
                  {renderDifficultyBadge(currentQuestion.difficulty)}
                  {currentQuestion.source_timestamp && (
                    <button
                      type="button"
                      onClick={() => onTimestampClick?.(currentQuestion.source_timestamp.timestamp)}
                      className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-950 text-indigo-400 border border-slate-800 hover:border-indigo-600 transition cursor-pointer"
                      title={currentQuestion.source_timestamp.label}
                    >
                      ⏱ {currentQuestion.source_timestamp.formatted_time}
                    </button>
                  )}
                </div>
              </div>

              {/* 4 Options Grid */}
              <div className="space-y-2 pt-1">
                {currentQuestion.options.map((option, optIdx) => {
                  const isSelected = selectedAnswers[currentQuestion.id] === option
                  const letter = String.fromCharCode(65 + optIdx)
                  return (
                    <button
                      key={optIdx}
                      type="button"
                      onClick={() => handleSelectOption(currentQuestion.id, option)}
                      className={`w-full text-left p-3 rounded-xl border flex items-center gap-3 transition cursor-pointer group ${
                        isSelected
                          ? 'bg-indigo-600/20 border-indigo-500 text-white ring-1 ring-indigo-500'
                          : 'bg-slate-950/70 border-slate-800/90 text-slate-300 hover:bg-slate-800/60 hover:text-white hover:border-slate-700'
                      }`}
                    >
                      <span
                        className={`h-6 w-6 rounded-lg text-xs font-mono font-bold flex items-center justify-center shrink-0 border transition ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-400 shadow-sm'
                            : 'bg-slate-900 text-slate-400 border-slate-700 group-hover:border-slate-500'
                        }`}
                      >
                        {letter}
                      </span>
                      <span className="leading-snug text-xs flex-1">{option}</span>
                    </button>
                  )
                })}
              </div>

              {/* Warning for uncompleted questions when attempting to submit */}
              {showConfirmIncomplete && (
                <div className="bg-amber-950/40 border border-amber-600/50 p-3 rounded-xl text-amber-200 text-xs flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span>⚠️</span>
                    <span>
                      You have <strong>{totalQuestions - answeredCount}</strong> unanswered question(s). Submit anyway?
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSubmitAnswers(selectedAnswers)}
                    className="px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg text-xs transition cursor-pointer"
                  >
                    Confirm Submit
                  </button>
                </div>
              )}

              {/* Controls Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={handlePrevious}
                  disabled={currentQuestionIndex === 0}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
                >
                  ← Previous
                </button>

                <div className="flex items-center gap-2">
                  {currentQuestionIndex < totalQuestions - 1 ? (
                    <button
                      type="button"
                      onClick={handleNext}
                      className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs transition cursor-pointer"
                    >
                      Next →
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white font-semibold text-xs shadow-md shadow-emerald-700/20 disabled:opacity-50 disabled:cursor-not-allowed transition cursor-pointer flex items-center gap-2"
                  >
                    {isSubmitting ? (
                      <>
                        <svg className="animate-spin h-3 w-3 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Grading Quiz...</span>
                      </>
                    ) : (
                      <span>Submit Quiz</span>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
