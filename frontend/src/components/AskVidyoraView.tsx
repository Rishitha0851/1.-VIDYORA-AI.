import React, { useEffect, useRef, useState } from 'react'
import type { AskVidyoraResponse } from '../types/ai'
import { askVidyoraApi, clearChatHistoryApi, fetchChatHistoryApi } from '../services/aiApi'

interface AskVidyoraViewProps {
  videoId: string
  videoTitle?: string | null
  onTimestampClick?: (seconds: number) => void
  initialQuestion?: string
}

const EXAMPLE_QUESTIONS = [
  'What are the core concepts explained in this lecture?',
  'Can you summarize the main takeaway with timestamps?',
  'What key formula or terminology was introduced?',
  'What real-world examples did the instructor share?',
]

export const AskVidyoraView: React.FC<AskVidyoraViewProps> = ({
  videoId,
  videoTitle,
  onTimestampClick,
  initialQuestion,
}) => {
  const [messages, setMessages] = useState<AskVidyoraResponse[]>([])
  const [question, setQuestion] = useState<string>(initialQuestion || '')
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true)
  const [isSending, setIsSending] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFailedQuestion, setLastFailedQuestion] = useState<string | null>(null)
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({})
  const [showClearConfirm, setShowClearConfirm] = useState<boolean>(false)
  const [isClearing, setIsClearing] = useState<boolean>(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Sync initialQuestion when navigating from a gap card
  useEffect(() => {
    if (initialQuestion && initialQuestion.trim().length > 0) {
      const timer = setTimeout(() => {
        setQuestion(initialQuestion)
        textareaRef.current?.focus()
      }, 0)
      return () => clearTimeout(timer)
    }
  }, [initialQuestion])

  // Scroll to bottom smoothly whenever messages update or during generation
  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }

  // Load persistent chat history on mount or when videoId changes
  useEffect(() => {
    let isMounted = true

    const loadHistory = async () => {
      setIsLoadingHistory(true)
      setError(null)
      try {
        const data = await fetchChatHistoryApi(videoId)
        if (isMounted) {
          setMessages(data.messages || [])
        }
      } catch (err) {
        if (isMounted) {
          console.warn('Failed to load chat history:', err)
        }
      } finally {
        if (isMounted) {
          setIsLoadingHistory(false)
          setTimeout(() => scrollToBottom('auto'), 100)
        }
      }
    }

    loadHistory()

    return () => {
      isMounted = false
    }
  }, [videoId])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isSending])

  const handleSendQuestion = async (textToSend?: string) => {
    const q = (textToSend ?? question).trim()
    if (!q || isSending) return

    setIsSending(true)
    setError(null)
    setLastFailedQuestion(null)
    setQuestion('')

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    try {
      const response = await askVidyoraApi({
        videoId,
        question: q,
      })
      setMessages((prev) => [...prev, response])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get answer from Ask VIDYORA.'
      setError(msg)
      setLastFailedQuestion(q)
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendQuestion()
    }
  }

  const handleClearHistory = async () => {
    setIsClearing(true)
    try {
      await clearChatHistoryApi(videoId)
      setMessages([])
      setShowClearConfirm(false)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to clear chat history.'
      setError(msg)
    } finally {
      setIsClearing(false)
    }
  }

  const toggleSourceExpand = (id: string) => {
    setExpandedSources((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  // Formatter for markdown-lite (bullet points, bold text, inline code)
  const renderFormattedAnswer = (text: string) => {
    const paragraphs = text.split('\n\n')
    return (
      <div className="space-y-2 text-slate-200 text-xs leading-relaxed">
        {paragraphs.map((p, pIdx) => {
          // Check for bullet lists
          if (p.includes('\n* ') || p.includes('\n- ') || p.startsWith('* ') || p.startsWith('- ')) {
            const lines = p.split('\n')
            return (
              <ul key={pIdx} className="space-y-1 my-1.5 pl-3 list-disc list-outside marker:text-indigo-400">
                {lines.map((l, lIdx) => {
                  const cleaned = l.replace(/^[*-]\s+/, '').trim()
                  if (!cleaned) return null
                  return <li key={lIdx}>{formatInlineTokens(cleaned)}</li>
                })}
              </ul>
            )
          }

          // Check for numbered lists
          if (/^\d+\.\s/.test(p)) {
            const lines = p.split('\n')
            return (
              <ol key={pIdx} className="space-y-1 my-1.5 pl-3 list-decimal list-outside marker:text-indigo-400">
                {lines.map((l, lIdx) => {
                  const cleaned = l.replace(/^\d+\.\s+/, '').trim()
                  if (!cleaned) return null
                  return <li key={lIdx}>{formatInlineTokens(cleaned)}</li>
                })}
              </ol>
            )
          }

          return <p key={pIdx}>{formatInlineTokens(p)}</p>
        })}
      </div>
    )
  }

  const formatInlineTokens = (str: string) => {
    // Regex for bold **text** and `code`
    const parts = str.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="text-white font-semibold">
            {part.slice(2, -2)}
          </strong>
        )
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={i}
            className="font-mono text-[11px] bg-slate-950 px-1 py-0.5 rounded text-indigo-300 border border-slate-800"
          >
            {part.slice(1, -1)}
          </code>
        )
      }
      return part
    })
  }

  return (
    <div className="flex flex-col h-[580px] bg-slate-950/40 rounded-2xl border border-slate-800/80 overflow-hidden">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-sm shadow-md shadow-indigo-600/30">
            🤖
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-white tracking-tight">Ask VIDYORA</h3>
              <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-medium">Grounded in Transcript</span>
            </div>
            <p className="text-[10px] text-slate-400 truncate max-w-[240px] sm:max-w-xs">
              {videoTitle || 'Educational Video Lecture'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <span className="text-[10px] text-slate-500 hidden sm:inline">
              {messages.length} Q&A {messages.length === 1 ? 'exchange' : 'exchanges'}
            </span>
          )}

          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => setShowClearConfirm(true)}
              className="text-[11px] text-slate-400 hover:text-rose-400 hover:bg-slate-800 px-2 py-1 rounded-lg transition cursor-pointer"
              title="Clear conversation history for this video"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Confirmation Modal for Clearing History */}
      {showClearConfirm && (
        <div className="p-3 bg-rose-950/60 border-b border-rose-800/60 flex items-center justify-between text-xs text-rose-200 animate-fadeIn">
          <span>Delete all chat messages for this video?</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isClearing}
              onClick={handleClearHistory}
              className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded text-[11px] transition cursor-pointer disabled:opacity-50"
            >
              {isClearing ? 'Clearing...' : 'Yes, Delete'}
            </button>
            <button
              type="button"
              disabled={isClearing}
              onClick={() => setShowClearConfirm(false)}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] transition cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Main Conversation Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoadingHistory ? (
          <div className="flex flex-col items-center justify-center h-full space-y-3 text-center">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400">Loading conversation history...</p>
          </div>
        ) : messages.length === 0 ? (
          /* Empty State with Suggested Prompts */
          <div className="flex flex-col items-center justify-center h-full text-center p-4 space-y-4 animate-fadeIn">
            <div className="w-12 h-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-2xl shadow-inner">
              ✨
            </div>
            <div className="space-y-1 max-w-sm">
              <h4 className="text-sm font-bold text-white">Ask Anything About This Lecture</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ask VIDYORA searches the video's transcript chunks and provides answers strictly grounded in the instructor's words, citing exact timestamps.
              </p>
            </div>

            <div className="w-full max-w-md pt-2 space-y-2">
              <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider block">
                Suggested Questions
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                {EXAMPLE_QUESTIONS.map((eq, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendQuestion(eq)}
                    className="p-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800/80 hover:border-indigo-500/40 text-[11px] text-slate-300 hover:text-white transition cursor-pointer group shadow-sm flex items-start gap-1.5"
                  >
                    <span className="text-indigo-400 text-xs shrink-0 group-hover:translate-x-0.5 transition">💬</span>
                    <span className="leading-snug">{eq}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Messages Feed */
          messages.map((msg, index) => (
            <div key={msg.id || index} className="space-y-3 animate-fadeIn">
              {/* User Question */}
              <div className="flex items-start justify-end gap-2.5 pl-8">
                <div className="bg-indigo-600/20 border border-indigo-500/30 rounded-2xl rounded-tr-sm px-3.5 py-2.5 max-w-[85%] shadow-sm">
                  <div className="flex items-center justify-between gap-3 mb-1">
                    <span className="text-[10px] font-semibold text-indigo-300">You</span>
                    <span className="text-[9px] text-slate-400 font-mono">
                      {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                  <p className="text-xs text-slate-100 whitespace-pre-wrap leading-relaxed">
                    {msg.question}
                  </p>
                </div>
                <div className="w-7 h-7 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xs shrink-0">
                  👤
                </div>
              </div>

              {/* AI Answer & Source Citations */}
              <div className="flex items-start gap-2.5 pr-8">
                <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-xs shrink-0 shadow-md shadow-indigo-600/30">
                  🎓
                </div>
                <div className="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-sm p-3.5 max-w-[92%] space-y-3 shadow-md">
                  {/* Tutor Header */}
                  <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] font-bold text-white">Ask VIDYORA</span>
                      {msg.model_used && (
                        <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-indigo-950 text-indigo-400 border border-indigo-800/50">
                          {msg.model_used}
                        </span>
                      )}
                    </div>
                    {msg.sources && msg.sources.length > 0 ? (
                      <span className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
                        <span>✓</span>
                        <span>{msg.sources.length} {msg.sources.length === 1 ? 'citation' : 'citations'}</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-amber-400 font-medium">
                        No matching chunks
                      </span>
                    )}
                  </div>

                  {/* Formatted Answer */}
                  <div>{renderFormattedAnswer(msg.answer)}</div>

                  {/* Source Citations with Real Timestamps */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="pt-2 border-t border-slate-800/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                          Grounded Citations
                        </span>
                        <span className="text-[10px] text-slate-500">
                          Click timestamp to jump in video
                        </span>
                      </div>

                      <div className="space-y-1.5">
                        {msg.sources.map((src, sIdx) => {
                          const srcKey = `${msg.id || index}_src_${sIdx}`
                          const isExpanded = Boolean(expandedSources[srcKey])

                          return (
                            <div
                              key={src.chunk_id || sIdx}
                              className="bg-slate-950/80 border border-slate-800/90 rounded-xl p-2 text-[11px] space-y-1.5 transition hover:border-indigo-500/30"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-1.5">
                                  {/* Seekable Timestamp Button */}
                                  <button
                                    type="button"
                                    onClick={() => onTimestampClick?.(src.start_time)}
                                    className="flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 rounded-lg bg-indigo-950 text-indigo-300 border border-indigo-800/60 hover:bg-indigo-900 hover:text-white transition cursor-pointer group"
                                    title={`Seek video player to ${src.source_formatted_start}`}
                                  >
                                    <span className="text-indigo-400 group-hover:scale-110 transition">▶</span>
                                    <span>{src.source_formatted_start} - {src.source_formatted_end}</span>
                                  </button>

                                  <span className="text-slate-400 text-[10px]">
                                    Chunk #{src.chunk_index + 1}
                                  </span>
                                </div>

                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950/50 px-1.5 py-0.2 rounded border border-emerald-800/40 font-semibold">
                                    {Math.round(src.similarity * 100)}% match
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => toggleSourceExpand(srcKey)}
                                    className="text-[10px] text-slate-400 hover:text-slate-200 transition cursor-pointer"
                                  >
                                    {isExpanded ? 'Less' : 'Snippet'}
                                  </button>
                                </div>
                              </div>

                              {/* Spoken excerpt preview */}
                              <p className={`text-slate-300 text-[10px] leading-relaxed italic bg-slate-900/40 p-1.5 rounded border border-slate-800/40 ${isExpanded ? '' : 'line-clamp-2'}`}>
                                "{src.text}"
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator while Gemini is generating */}
        {isSending && (
          <div className="flex items-start gap-2.5 animate-fadeIn">
            <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-xs shrink-0 shadow-md">
              🎓
            </div>
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-sm p-3 max-w-[85%] space-y-2">
              <div className="flex items-center gap-2 text-indigo-300 text-xs font-medium">
                <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                <span>Searching transcript chunks & generating grounded answer...</span>
              </div>
              <p className="text-[11px] text-slate-400 italic">
                Ask VIDYORA strictly retrieves verified lecture excerpts to prevent unsupported claims.
              </p>
            </div>
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs flex items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
            {lastFailedQuestion && (
              <button
                type="button"
                onClick={() => handleSendQuestion(lastFailedQuestion)}
                className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded text-[11px] transition cursor-pointer shrink-0"
              >
                Retry
              </button>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Bar */}
      <div className="p-3 bg-slate-900/90 border-t border-slate-800 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSendQuestion()
          }}
          className="flex items-end gap-2"
        >
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              rows={1}
              value={question}
              onChange={(e) => {
                setQuestion(e.target.value)
                // Auto-adjust height up to 4 lines
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about this lecture... (Enter to send)"
              disabled={isSending}
              className="w-full resize-none rounded-xl bg-slate-950 border border-slate-800 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={isSending || !question.trim()}
            className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer flex items-center gap-1.5 shrink-0"
          >
            {isSending ? (
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <span>Ask</span>
            )}
            <span>→</span>
          </button>
        </form>
        <div className="flex items-center justify-between pt-1.5 px-1 text-[10px] text-slate-500">
          <span>Shift+Enter for newline</span>
          <span>Answers strictly grounded in video transcript</span>
        </div>
      </div>
    </div>
  )
}

export default AskVidyoraView
