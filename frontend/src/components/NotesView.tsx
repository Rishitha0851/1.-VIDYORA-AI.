import React from 'react'
import type { StructuredNotes } from '../types/ai'

interface NotesViewProps {
  notes: StructuredNotes
  modelUsed?: string
  chunkCount?: number
  onTimestampClick?: (seconds: number) => void
}

export const NotesView: React.FC<NotesViewProps> = ({
  notes,
  modelUsed,
  chunkCount,
  onTimestampClick,
}) => {
  return (
    <div className="space-y-5 text-xs">
      {/* Model & Source Meta Header */}
      <div className="flex items-center justify-between bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-indigo-400"></span>
          <span>
            Synthesized from <strong className="text-slate-200">{chunkCount ?? 'all'}</strong> knowledge chunks
          </span>
        </div>
        {modelUsed && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 font-medium">
            {modelUsed}
          </span>
        )}
      </div>

      {/* 1. Header & Introduction */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/80 space-y-2">
        <h2 className="text-base font-bold text-white tracking-tight">
          {notes.topic_title}
        </h2>
        <p className="text-slate-300 leading-relaxed text-xs">
          {notes.introduction}
        </p>

        {notes.main_concepts && notes.main_concepts.length > 0 && (
          <div className="pt-2 flex flex-wrap gap-1.5">
            {notes.main_concepts.map((concept, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[10px] font-medium"
              >
                {concept}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 2. Structured Sections */}
      {notes.sections && notes.sections.length > 0 && (
        <div className="space-y-3">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Lecture Sections & Breakdown ({notes.sections.length})
          </span>
          <div className="space-y-3">
            {notes.sections.map((section, idx) => (
              <div
                key={idx}
                className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold text-slate-100 text-xs">
                    {idx + 1}. {section.title}
                  </h3>
                  {section.formatted_time && (
                    <button
                      type="button"
                      onClick={() => section.start_time !== null && section.start_time !== undefined && onTimestampClick?.(section.start_time)}
                      className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-950 text-indigo-400 border border-slate-800 hover:border-indigo-600 transition cursor-pointer"
                    >
                      {section.formatted_time}
                    </button>
                  )}
                </div>

                <p className="text-slate-300 text-xs leading-relaxed">
                  {section.summary}
                </p>

                {section.key_points && section.key_points.length > 0 && (
                  <ul className="space-y-1 pt-1 border-t border-slate-800/50">
                    {section.key_points.map((pt, pIdx) => (
                      <li key={pIdx} className="flex items-start gap-2 text-slate-400 text-[11px]">
                        <span className="text-indigo-400 font-bold shrink-0">•</span>
                        <span className="leading-snug">{pt}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Key Terminology Glossary */}
      {notes.terminology && notes.terminology.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Key Terminology Glossary
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {notes.terminology.map((item, idx) => (
              <div
                key={idx}
                className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-indigo-300 text-[11px]">
                    {item.term}
                  </span>
                  {item.context && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-900 text-slate-400">
                      {item.context}
                    </span>
                  )}
                </div>
                <p className="text-slate-400 text-[11px] leading-snug">
                  {item.definition}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Examples Mentioned in Video */}
      {notes.examples && notes.examples.length > 0 && (
        <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 space-y-1.5">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Real-World Examples Cited
          </span>
          <ul className="space-y-1.5">
            {notes.examples.map((ex, idx) => (
              <li key={idx} className="flex items-start gap-2 text-slate-300 text-xs">
                <span className="text-indigo-400 shrink-0 font-medium">💡</span>
                <span className="leading-relaxed">{ex}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. Key Study Takeaways */}
      {notes.key_takeaways && notes.key_takeaways.length > 0 && (
        <div className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/80 space-y-1.5">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Summary Takeaways
          </span>
          <ul className="space-y-1.5">
            {notes.key_takeaways.map((takeaway, idx) => (
              <li key={idx} className="flex items-start gap-2 text-slate-300 text-xs">
                <span className="text-emerald-400 font-bold shrink-0">✓</span>
                <span className="leading-snug">{takeaway}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 6. Milestone Timestamps */}
      {notes.relevant_timestamps && notes.relevant_timestamps.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
            Key Milestone Moments
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {notes.relevant_timestamps.map((ts, idx) => (
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

export default NotesView
