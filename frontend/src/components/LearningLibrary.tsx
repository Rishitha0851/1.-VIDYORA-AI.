import React, { useEffect, useState } from 'react'
import type { VideoListItem } from '../types/ai'
import { fetchPersistedVideosApi } from '../services/aiApi'

interface LearningLibraryProps {
  onSelectVideo: (videoId: string) => void
  currentVideoId?: string | null
  isLoadingWorkspace?: boolean
}

export const LearningLibrary: React.FC<LearningLibraryProps> = ({
  onSelectVideo,
  currentVideoId,
  isLoadingWorkspace = false,
}) => {
  const [videos, setVideos] = useState<VideoListItem[]>([])
  const [isLoadingList, setIsLoadingList] = useState<boolean>(false)
  const [listError, setListError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState<boolean>(false)

  const loadVideos = async () => {
    setIsLoadingList(true)
    setListError(null)
    try {
      const data = await fetchPersistedVideosApi()
      setVideos(data.videos)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not fetch saved videos.'
      setListError(msg)
    } finally {
      setIsLoadingList(false)
    }
  }

  useEffect(() => {
    let isMounted = true
    const load = async () => {
      queueMicrotask(() => {
        if (isMounted) {
          setIsLoadingList(true)
          setListError(null)
        }
      })
      try {
        const data = await fetchPersistedVideosApi()
        if (isMounted) {
          setVideos(data.videos)
        }
      } catch (err) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Could not fetch saved videos.'
          setListError(msg)
        }
      } finally {
        if (isMounted) {
          setIsLoadingList(false)
        }
      }
    }
    load()
    return () => {
      isMounted = false
    }
  }, [])

  const formatDate = (isoString: string): string => {
    try {
      const d = new Date(isoString)
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  return (
    <div className="w-full max-w-2xl bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-lg space-y-3 transition">
      {/* Library Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-sm text-indigo-400">
            📚
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              Persistent Learning Library
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                {videos.length} {videos.length === 1 ? 'lecture' : 'lectures'}
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Reload saved workspaces directly from PostgreSQL without reprocessing
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadVideos}
            disabled={isLoadingList}
            title="Refresh library"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition text-xs cursor-pointer disabled:opacity-50"
          >
            🔄
          </button>
          <button
            type="button"
            onClick={() => setIsOpen((prev) => !prev)}
            className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 font-medium text-xs transition cursor-pointer flex items-center gap-1.5"
          >
            <span>{isOpen ? 'Hide Library' : 'Browse Videos'}</span>
            <span className="text-[10px]">{isOpen ? '▲' : '▼'}</span>
          </button>
        </div>
      </div>

      {/* Expandable Library Body */}
      {isOpen && (
        <div className="pt-2 border-t border-slate-800/80 space-y-3 animate-fadeIn">
          {listError && (
            <div className="bg-rose-950/40 border border-rose-800/80 text-rose-300 p-2.5 rounded-xl text-xs flex items-center justify-between">
              <span>⚠️ {listError}</span>
              <button
                type="button"
                onClick={loadVideos}
                className="underline text-[11px] hover:text-white"
              >
                Retry
              </button>
            </div>
          )}

          {isLoadingList && (
            <div className="flex items-center justify-center py-6 gap-2 text-slate-400 text-xs">
              <span className="animate-spin text-indigo-400">⌛</span>
              <span>Loading saved learning records from database...</span>
            </div>
          )}

          {!isLoadingList && videos.length === 0 && !listError && (
            <div className="text-center py-6 text-slate-400 text-xs bg-slate-950/40 rounded-xl border border-slate-800/50">
              <p className="font-medium text-slate-300">No persisted lectures found yet.</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Process an educational video above to store its transcript, chunks, and assessments.
              </p>
            </div>
          )}

          {!isLoadingList && videos.length > 0 && (
            <div className="grid grid-cols-1 gap-2.5 max-h-80 overflow-y-auto pr-1">
              {videos.map((vid) => {
                const isSelected = vid.video_id === currentVideoId

                return (
                  <div
                    key={vid.video_id}
                    className={`p-3 rounded-xl border transition flex flex-col md:flex-row md:items-center justify-between gap-3 ${
                      isSelected
                        ? 'bg-indigo-950/30 border-indigo-500/50 shadow-sm'
                        : 'bg-slate-950/60 hover:bg-slate-950 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700">
                          {vid.platform}
                        </span>
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded font-semibold uppercase tracking-wider ${
                            vid.status === 'completed'
                              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
                              : 'bg-rose-950/60 text-rose-400 border border-rose-800/60'
                          }`}
                        >
                          {vid.status}
                        </span>
                        <span className="text-[11px] text-slate-400">
                          {formatDate(vid.created_at)}
                        </span>
                      </div>

                      <h4 className="text-xs font-semibold text-slate-100 truncate">
                        {vid.title || `Video ID: ${vid.video_id}`}
                      </h4>

                      {/* Content Badges */}
                      <div className="flex items-center gap-3 text-[10px] text-slate-400 font-mono">
                        <span>📝 {vid.chunk_count} chunks</span>
                        <span>💬 {vid.segment_count} segments</span>
                        {vid.has_quiz && (
                          <span className="text-emerald-400 font-sans font-medium">
                            ✓ Quiz ready
                          </span>
                        )}
                        {vid.has_flashcards && (
                          <span className="text-indigo-400 font-sans font-medium">
                            ✓ Cards ready
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onSelectVideo(vid.video_id)}
                        disabled={isLoadingWorkspace}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer flex items-center gap-1.5 ${
                          isSelected
                            ? 'bg-emerald-600 text-white font-semibold shadow-sm'
                            : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm shadow-indigo-600/20'
                        }`}
                      >
                        {isLoadingWorkspace && isSelected ? (
                          <>
                            <span className="animate-spin text-xs">⌛</span>
                            <span>Restoring...</span>
                          </>
                        ) : isSelected ? (
                          <>
                            <span>✓ Active</span>
                          </>
                        ) : (
                          <>
                            <span>⚡ Load Workspace</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
