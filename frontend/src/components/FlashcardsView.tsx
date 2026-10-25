import React, { useState } from 'react'
import type {
  GeneratedFlashcards,
  Flashcard,
  QuizDifficulty,
} from '../types/ai'

interface FlashcardsViewProps {
  flashcards: GeneratedFlashcards
  modelUsed?: string
  chunkCount?: number
  onRegenerateFlashcards?: () => void
  onTimestampClick?: (seconds: number) => void
}

export const FlashcardsView: React.FC<FlashcardsViewProps> = ({
  flashcards,
  modelUsed,
  chunkCount,
  onRegenerateFlashcards,
  onTimestampClick,
}) => {
  const [currentIndex, setCurrentIndex] = useState<number>(0)
  const [isFlipped, setIsFlipped] = useState<boolean>(false)
  const [shuffledCards, setShuffledCards] = useState<Flashcard[]>(flashcards.cards)
  const [isShuffled, setIsShuffled] = useState<boolean>(false)

  const cards = isShuffled ? shuffledCards : flashcards.cards
  const totalCards = cards.length
  const currentCard = cards[currentIndex]

  const handleNext = () => {
    if (currentIndex < totalCards - 1) {
      setIsFlipped(false)
      setCurrentIndex((prev) => prev + 1)
    }
  }

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setIsFlipped(false)
      setCurrentIndex((prev) => prev - 1)
    }
  }

  const handleToggleFlip = () => {
    setIsFlipped((prev) => !prev)
  }

  const handleToggleShuffle = () => {
    if (!isShuffled) {
      const copy = [...flashcards.cards]
      for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[copy[i], copy[j]] = [copy[j], copy[i]]
      }
      setShuffledCards(copy)
      setIsShuffled(true)
    } else {
      setIsShuffled(false)
    }
    setIsFlipped(false)
    setCurrentIndex(0)
  }

  const handleReset = () => {
    setIsFlipped(false)
    setCurrentIndex(0)
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

  if (!currentCard || totalCards === 0) {
    return (
      <div className="bg-slate-900/60 p-6 rounded-xl border border-slate-800 text-center text-slate-400">
        <p>No flashcards available in this deck.</p>
      </div>
    )
  }

  const progressPercent = Math.round(((currentIndex + 1) / totalCards) * 100)

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Header Meta Bar */}
      <div className="flex items-center justify-between bg-slate-950/80 px-3.5 py-2 rounded-xl border border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-indigo-400"></span>
          <span>
            Deck synthesized from <strong className="text-slate-200">{chunkCount ?? 'all'}</strong> knowledge chunks
          </span>
        </div>
        <div className="flex items-center gap-2">
          {modelUsed && (
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 font-medium">
              {modelUsed}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800 font-mono text-[10px]">
            {totalCards} Cards
          </span>
        </div>
      </div>

      {/* 2. Deck Topic & Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900/60 px-4 py-3 rounded-xl border border-slate-800/80">
        <div>
          <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider block">
            Active Recall Deck
          </span>
          <h3 className="text-xs font-semibold text-white tracking-tight">
            {flashcards.topic}
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleToggleShuffle}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition cursor-pointer border ${
              isShuffled
                ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white'
            }`}
            title="Randomize card order"
          >
            🔀 {isShuffled ? 'Shuffled' : 'Shuffle'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-medium border border-slate-700 transition cursor-pointer"
            title="Return to first card"
          >
            ↺ Reset
          </button>
          {onRegenerateFlashcards && (
            <button
              type="button"
              onClick={onRegenerateFlashcards}
              className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-[11px] transition cursor-pointer shadow-sm shadow-indigo-600/20"
            >
              ✨ Regenerate Deck
            </button>
          )}
        </div>
      </div>

      {/* 3. Progress Bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <span>Card {currentIndex + 1} of {totalCards}</span>
          <span>{progressPercent}% Complete</span>
        </div>
        <div className="h-1.5 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 transition-all duration-300 rounded-full"
            style={{ width: `${progressPercent}%` }}
          ></div>
        </div>
      </div>

      {/* 4. Interactive Flashcard */}
      <div
        onClick={handleToggleFlip}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            handleToggleFlip()
          }
        }}
        className={`w-full min-h-[240px] p-6 rounded-2xl border transition-all duration-300 cursor-pointer select-none flex flex-col justify-between shadow-xl relative overflow-hidden group ${
          isFlipped
            ? 'bg-gradient-to-br from-indigo-950/40 via-slate-900 to-slate-950 border-indigo-500/40 hover:border-indigo-400/60'
            : 'bg-gradient-to-br from-slate-900/90 via-slate-900 to-slate-950 border-slate-800 hover:border-slate-700'
        }`}
      >
        {/* Top Card Meta */}
        <div className="flex items-center justify-between gap-3 text-slate-400 text-[11px]">
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                isFlipped
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                  : 'bg-slate-800 text-slate-300 border border-slate-700'
              }`}
            >
              {isFlipped ? 'Answer Side' : 'Concept Prompt'}
            </span>
            {renderDifficultyBadge(currentCard.difficulty)}
          </div>

          <div className="flex items-center gap-2">
            {currentCard.source_timestamp && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onTimestampClick?.(currentCard.source_timestamp.timestamp)
                }}
                className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-950 text-indigo-400 border border-slate-800 hover:border-indigo-600 transition cursor-pointer"
                title={currentCard.source_timestamp.label}
              >
                ⏱ {currentCard.source_timestamp.formatted_time}
              </button>
            )}
          </div>
        </div>

        {/* Center Card Content */}
        <div className="my-auto py-4 space-y-2">
          {isFlipped ? (
            <div className="space-y-1.5 animate-fadeIn">
              <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider block">
                Answer / Core Principle
              </span>
              <p className="text-sm md:text-base font-medium text-slate-100 leading-relaxed">
                {currentCard.back}
              </p>
            </div>
          ) : (
            <div className="space-y-1.5">
              <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider block">
                Question / Term
              </span>
              <h4 className="text-sm md:text-base font-bold text-white leading-snug">
                {currentCard.front}
              </h4>
            </div>
          )}
        </div>

        {/* Bottom Card Hint */}
        <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-800/60">
          <span className="italic flex items-center gap-1.5 text-slate-400 group-hover:text-indigo-300 transition">
            <span>🔄</span> Click or press Space to {isFlipped ? 'flip back' : 'reveal answer'}
          </span>
          <span className="font-mono text-[10px] text-slate-400">
            {currentIndex + 1} / {totalCards}
          </span>
        </div>
      </div>

      {/* 5. Navigation Controls */}
      <div className="flex items-center justify-between gap-3 pt-1">
        <button
          type="button"
          onClick={handlePrevious}
          disabled={currentIndex === 0}
          className="flex-1 sm:flex-none px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 font-medium text-xs border border-slate-800 hover:border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
        >
          ← Previous Card
        </button>

        <button
          type="button"
          onClick={handleToggleFlip}
          className="flex-1 sm:flex-none px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 hover:text-white font-medium text-xs border border-slate-700/80 transition cursor-pointer"
        >
          {isFlipped ? 'Hide Answer' : 'Reveal Answer'}
        </button>

        <button
          type="button"
          onClick={handleNext}
          disabled={currentIndex === totalCards - 1}
          className="flex-1 sm:flex-none px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 font-medium text-xs border border-slate-800 hover:border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
        >
          Next Card →
        </button>
      </div>
    </div>
  )
}
