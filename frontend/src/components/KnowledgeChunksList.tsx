import React, { useMemo } from 'react'
import type { TranscriptChunk } from '../types/ai'
import { formatTime } from '../utils/formatTime'

interface KnowledgeChunksListProps {
  chunks: TranscriptChunk[]
  currentTime: number
  onSeek: (seconds: number) => void
  className?: string
}

export const KnowledgeChunksList: React.FC<KnowledgeChunksListProps> = ({
  chunks,
  currentTime,
  onSeek,
  className = '',
}) => {
  // Find currently active chunk
  const activeChunkId = useMemo(() => {
    if (!chunks || chunks.length === 0) return null
    const active = chunks.find(
      (c) => currentTime >= c.start_time && currentTime <= c.end_time
    )
    return active ? active.chunk_id : null
  }, [chunks, currentTime])

  return (
    <div className={`flex flex-col bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg ${className}`}>
      {/* Header */}
      <div className="p-3.5 bg-slate-950/80 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm">🧩</span>
          <div>
            <h3 className="text-xs font-bold text-white tracking-wide">
              Knowledge Chunks ({chunks.length})
            </h3>
            <p className="text-[10px] text-slate-400">
              Cohesive conceptual paragraphs grounded in lecture segments
            </p>
          </div>
        </div>
      </div>

      {/* Chunks List */}
      <div className="max-h-96 sm:max-h-[28rem] overflow-y-auto p-3.5 space-y-3">
        {chunks && chunks.length > 0 ? (
          chunks.map((chunk) => {
            const isActive = chunk.chunk_id === activeChunkId

            return (
              <div
                key={chunk.chunk_id}
                className={`p-3.5 rounded-xl border transition space-y-2 ${
                  isActive
                    ? 'bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950/30'
                    : 'bg-slate-950/60 border-slate-800/70 hover:border-slate-700'
                }`}
              >
                {/* Chunk Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-indigo-400">
                      Chunk #{chunk.chunk_index + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => onSeek(chunk.start_time)}
                      className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-indigo-300 border border-slate-800 hover:border-indigo-600 transition cursor-pointer"
                      title={`Jump to ${formatTime(chunk.start_time)}`}
                    >
                      {formatTime(chunk.start_time)} – {formatTime(chunk.end_time)}
                    </button>
                    {isActive && (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span>Now Playing</span>
                      </span>
                    )}
                  </div>

                  {/* Watch this section action */}
                  <button
                    type="button"
                    onClick={() => onSeek(chunk.start_time)}
                    className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-sm group"
                    title={`Watch section starting at ${formatTime(chunk.start_time)}`}
                  >
                    <span className="text-[10px] group-hover:scale-110 transition">▶</span>
                    <span>Watch this section</span>
                  </button>
                </div>

                {/* Chunk Text Content */}
                <p className="text-slate-200 text-xs leading-relaxed">
                  {chunk.text}
                </p>

                {/* Metadata Footer */}
                <div className="flex items-center gap-3 text-[10px] text-slate-500 font-mono pt-1 border-t border-slate-900">
                  <span>{chunk.word_count} words</span>
                  <span>•</span>
                  <span>{Math.round(chunk.duration)}s duration</span>
                  <span>•</span>
                  <span>Segments {chunk.segment_start_index}–{chunk.segment_end_index}</span>
                </div>
              </div>
            )
          })
        ) : (
          <p className="text-slate-500 italic text-center py-8 text-xs">
            No knowledge chunks available.
          </p>
        )}
      </div>
    </div>
  )
}

export default KnowledgeChunksList
