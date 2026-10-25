import { useEffect, useMemo, useRef, useState } from 'react'
import WelcomeBanner from './components/WelcomeBanner'
import BackendStatus from './components/BackendStatus'
import VideoInput from './components/VideoInput'
import AuthModal from './components/AuthModal'
import { SummaryView } from './components/SummaryView'
import { NotesView } from './components/NotesView'
import { QuizView } from './components/QuizView'
import { FlashcardsView } from './components/FlashcardsView'
import { LearningLibrary } from './components/LearningLibrary'
import { KnowledgeGapView } from './components/KnowledgeGapView'
import { VideoPlayer } from './components/VideoPlayer'
import { AskVidyoraView } from './components/AskVidyoraView'
import { formatTime } from './utils/formatTime'
import type { VideoPlayerHandle } from './types/player'
import type { User } from './types/auth'
import { API_BASE_URL, clearAuthToken, getAuthToken, getCurrentUserApi } from './services/authApi'
import { InteractiveTranscript } from './components/InteractiveTranscript'
import { KnowledgeChunksList } from './components/KnowledgeChunksList'
import { LearningRecoveryView } from './components/LearningRecoveryView'
import type {
  ChunkKnowledgeGap,
  FlashcardsResponse,
  NotesResponse,
  QuizEvaluationResponse,
  QuizResponse,
  SummaryResponse,
  VideoKnowledgeGapsResponse,
  VideoTranscript,
} from './types/ai'
import {
  evaluateQuizApi,
  fetchVideoKnowledgeGapsApi,
  fetchVideoWorkspaceApi,
  generateFlashcardsApi,
  generateNotesApi,
  generateQuizApi,
  generateSummaryApi,
  processVideoApi,
} from './services/aiApi'

/** Lifecycle processing states supported by VIDYORA AI */
export type VideoProcessingStatus =
  | 'submitted'
  | 'validating'
  | 'accepted'
  | 'processing'
  | 'completed'
  | 'failed'

/** Supported video platforms */
export type VideoPlatform = 'youtube' | 'direct' | 'unknown'

/** Structured metadata entity representing a video */
export interface VideoMetadata {
  id: string
  url: string
  platform: VideoPlatform
  title: string | null
  status: VideoProcessingStatus
  created_at: string
  updated_at: string
  error_message?: string | null
  transcript?: VideoTranscript | null
}

/** Structured API response from FastAPI POST /api/videos/process */
export interface VideoProcessResponse {
  status: VideoProcessingStatus
  message: string
  video: VideoMetadata
  // Backward compatibility fields
  video_url?: string
  received_at?: string
  video_id?: string | null
}

export type ActiveContentTab =
  | 'ask'
  | 'notes'
  | 'summary'
  | 'quiz'
  | 'flashcards'
  | 'gaps'
  | 'recovery'

export type LeftCompanionTab = 'transcript' | 'chunks' | 'details'

export default function App() {
  // Authentication State
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [isAuthChecking, setIsAuthChecking] = useState<boolean>(() => Boolean(getAuthToken()))
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false)
  const [authModalInitialMode, setAuthModalInitialMode] = useState<'login' | 'register'>('login')

  // State for video submission
  const [processedVideo, setProcessedVideo] = useState<VideoProcessResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // Interactive Player State & Ref
  const playerRef = useRef<VideoPlayerHandle>(null)
  const playerContainerRef = useRef<HTMLDivElement>(null)
  const [currentTime, setCurrentTime] = useState<number>(0)
  const [, setVideoDuration] = useState<number>(0)
  const [, setIsPlaying] = useState<boolean>(false)

  // Workspace Navigation & Tabs
  const [activeTab, setActiveTab] = useState<ActiveContentTab>('notes')
  const [leftTab, setLeftTab] = useState<LeftCompanionTab>('transcript')
  const [showLibraryModal, setShowLibraryModal] = useState<boolean>(false)
  const [showNewVideoModal, setShowNewVideoModal] = useState<boolean>(false)

  // Session verification on mount
  useEffect(() => {
    const token = getAuthToken()
    if (!token) return

    getCurrentUserApi()
      .then((user) => {
        setCurrentUser(user)
      })
      .catch(() => {
        clearAuthToken()
        setCurrentUser(null)
      })
      .finally(() => {
        setIsAuthChecking(false)
      })
  }, [])

  const handleLogout = () => {
    clearAuthToken()
    setCurrentUser(null)
    setProcessedVideo(null)
    setSummaryData(null)
    setNotesData(null)
    setQuizData(null)
    setFlashcardsData(null)
    setKnowledgeGapsData(null)
    setActiveRecoveryChunk(null)
    setShowLibraryModal(false)
    setShowNewVideoModal(false)
  }

  // AI Summary State
  const [summaryData, setSummaryData] = useState<SummaryResponse | null>(null)
  const [isGeneratingSummary, setIsGeneratingSummary] = useState<boolean>(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  // AI Notes State
  const [notesData, setNotesData] = useState<NotesResponse | null>(null)
  const [isGeneratingNotes, setIsGeneratingNotes] = useState<boolean>(false)
  const [notesError, setNotesError] = useState<string | null>(null)

  // AI Quiz State
  const [quizData, setQuizData] = useState<QuizResponse | null>(null)
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState<boolean>(false)
  const [quizError, setQuizError] = useState<string | null>(null)
  const [quizEvaluation, setQuizEvaluation] = useState<QuizEvaluationResponse | null>(null)
  const [isEvaluatingQuiz, setIsEvaluatingQuiz] = useState<boolean>(false)
  const [evaluationError, setEvaluationError] = useState<string | null>(null)

  // AI Flashcards State
  const [flashcardsData, setFlashcardsData] = useState<FlashcardsResponse | null>(null)
  const [isGeneratingFlashcards, setIsGeneratingFlashcards] = useState<boolean>(false)
  const [flashcardsError, setFlashcardsError] = useState<string | null>(null)

  // Knowledge Gap State
  const [knowledgeGapsData, setKnowledgeGapsData] = useState<VideoKnowledgeGapsResponse | null>(null)
  const [isLoadingGaps, setIsLoadingGaps] = useState<boolean>(false)
  const [gapsError, setGapsError] = useState<string | null>(null)

  // Learning Recovery State
  const [activeRecoveryChunk, setActiveRecoveryChunk] = useState<ChunkKnowledgeGap | null>(null)

  // Persistence State
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState<boolean>(false)
  const [isWorkspaceRestored, setIsWorkspaceRestored] = useState<boolean>(false)

  // Contextual Tutor State (seeding Ask VIDYORA from Gaps or Recovery)
  const [askInitialQuestion, setAskInitialQuestion] = useState<string>('')

  // Handle Ask Tutor about a specific Knowledge Gap
  const handleAskTutorAboutGap = (gap: ChunkKnowledgeGap) => {
    const topicLabel = gap.concept_name || gap.chunk_summary_text || `Concept Segment #${gap.chunk_index + 1}`
    const query = `Can you explain ${topicLabel} covered around ${gap.source_timestamp.formatted_time}?`
    setAskInitialQuestion(query)
    if (gap.source_timestamp?.timestamp !== undefined) {
      handleSeekTo(gap.source_timestamp.timestamp, false)
    }
    setActiveTab('ask')
  }

  const handleAskTutorWithQuestion = (customQuestion: string) => {
    setAskInitialQuestion(customQuestion)
    setActiveTab('ask')
  }

  // Handle seeking the embedded video player
  const handleSeekTo = (seconds: number, shouldPlay = true) => {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds, shouldPlay)
      // Smooth scroll player container into view if on mobile/smaller screens
      playerContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }

  // Handle Review in Video from Knowledge Gaps and Learning Recovery
  const handleReviewInVideo = (_videoUrl: string, timestampSeconds: number) => {
    handleSeekTo(timestampSeconds, true)
  }

  // Handle video URL submission to FastAPI backend
  const handleVideoSubmit = async (url: string) => {
    setIsSubmitting(true)
    setIsWorkspaceRestored(false)
    setSubmissionError(null)
    setProcessedVideo(null)
    setActiveTab('notes')
    setLeftTab('transcript')
    setActiveRecoveryChunk(null)
    setSummaryData(null)
    setSummaryError(null)
    setNotesData(null)
    setNotesError(null)
    setQuizData(null)
    setQuizError(null)
    setQuizEvaluation(null)
    setEvaluationError(null)
    setFlashcardsData(null)
    setFlashcardsError(null)
    setKnowledgeGapsData(null)
    setGapsError(null)
    setShowNewVideoModal(false)

    try {
      const result = await processVideoApi<VideoProcessResponse>(url)
      setProcessedVideo(result)

      if (result.video?.id) {
        handleLoadKnowledgeGaps(result.video.id)
      }
    } catch (error) {
      let friendlyError = `Failed to connect to backend service. Please ensure FastAPI is running on ${API_BASE_URL}.`
      if (error instanceof TypeError && error.message.toLowerCase().includes('fetch')) {
        friendlyError = `Cannot connect to VIDYORA AI backend. Please verify that the FastAPI server is running on ${API_BASE_URL}.`
      } else if (error instanceof Error) {
        if (error.message.toLowerCase().includes('session expired') || error.message.toLowerCase().includes('unauthenticated')) {
          setCurrentUser(null)
          setShowAuthModal(true)
        }
        friendlyError = error.message
      }
      setSubmissionError(friendlyError)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Reload an existing video workspace from PostgreSQL without Gemini
  const handleSelectLibraryVideo = async (videoId: string) => {
    setIsLoadingWorkspace(true)
    setSubmissionError(null)
    setSummaryError(null)
    setNotesError(null)
    setQuizError(null)
    setQuizEvaluation(null)
    setFlashcardsError(null)
    setActiveRecoveryChunk(null)
    setShowLibraryModal(false)

    try {
      const workspace = await fetchVideoWorkspaceApi(videoId)

      const restoredResponse: VideoProcessResponse = {
        status: workspace.video.status,
        message: `Workspace restored from PostgreSQL (${workspace.video.transcript?.chunk_count || 0} chunks, ${workspace.available_quizzes_count} quizzes, ${workspace.available_decks_count} decks). Zero external API calls made.`,
        video: workspace.video,
        video_id: workspace.video.id,
        video_url: workspace.video.url,
        received_at: workspace.video.created_at,
      }

      setProcessedVideo(restoredResponse)
      setIsWorkspaceRestored(true)
      setActiveTab('notes')
      setLeftTab('transcript')

      // Restore persisted quiz if present
      if (workspace.latest_quiz) {
        setQuizData({
          status: 'completed',
          video_id: workspace.video.id,
          quiz: workspace.latest_quiz,
          model_used: 'PostgreSQL (persisted)',
          chunk_count: workspace.video.transcript?.chunk_count || 0,
        })
      } else {
        setQuizData(null)
      }
      setQuizEvaluation(null)

      // Restore persisted flashcards if present
      if (workspace.latest_flashcards) {
        setFlashcardsData({
          status: 'completed',
          video_id: workspace.video.id,
          flashcards: workspace.latest_flashcards,
          model_used: 'PostgreSQL (persisted)',
          chunk_count: workspace.video.transcript?.chunk_count || 0,
        })
      } else {
        setFlashcardsData(null)
      }

      // Restore summary if present
      if (workspace.summary) {
        setSummaryData({
          status: 'completed',
          video_id: workspace.video.id,
          summary: workspace.summary,
          model_used: 'PostgreSQL (persisted)',
          chunk_count: workspace.video.transcript?.chunk_count || 0,
        })
      } else {
        setSummaryData(null)
      }

      // Restore notes if present
      if (workspace.notes) {
        setNotesData({
          status: 'completed',
          video_id: workspace.video.id,
          notes: workspace.notes,
          model_used: 'PostgreSQL (persisted)',
          chunk_count: workspace.video.transcript?.chunk_count || 0,
        })
      } else {
        setNotesData(null)
      }

      // Automatically load persisted knowledge gaps for this video
      handleLoadKnowledgeGaps(workspace.video.id)

    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to reload video workspace from database.'
      setSubmissionError(msg)
    } finally {
      setIsLoadingWorkspace(false)
    }
  }

  const handleClear = () => {
    setProcessedVideo(null)
    setIsWorkspaceRestored(false)
    setSubmissionError(null)
    setActiveTab('notes')
    setLeftTab('transcript')
    setActiveRecoveryChunk(null)
    setSummaryData(null)
    setSummaryError(null)
    setNotesData(null)
    setNotesError(null)
    setQuizData(null)
    setQuizError(null)
    setQuizEvaluation(null)
    setEvaluationError(null)
    setFlashcardsData(null)
    setFlashcardsError(null)
    setKnowledgeGapsData(null)
    setGapsError(null)
  }

  // Safe accessor resolving structured metadata
  const video: VideoMetadata | null = useMemo(() => {
    if (processedVideo?.video) return processedVideo.video
    if (!processedVideo) return null
    return {
      id: processedVideo.video_id ?? 'unknown',
      url: processedVideo.video_url ?? '',
      platform: 'unknown' as VideoPlatform,
      title: null,
      status: processedVideo.status,
      created_at: processedVideo.received_at ?? '',
      updated_at: processedVideo.received_at ?? '',
    }
  }, [processedVideo])

  // Active knowledge chunk based on current video timestamp
  const activeChunk = useMemo(() => {
    if (!video?.transcript?.chunks) return null
    return video.transcript.chunks.find(
      (c) => currentTime >= c.start_time && currentTime <= c.end_time
    )
  }, [video, currentTime])

  const activeConceptLabel = activeChunk
    ? `Chunk #${activeChunk.chunk_index + 1} (${formatTime(activeChunk.start_time)}–${formatTime(activeChunk.end_time)})`
    : null

  // AI Summary Generation Handler
  const handleGenerateSummary = async () => {
    if (!video || !video.transcript?.chunks || video.transcript.chunks.length === 0) return

    setIsGeneratingSummary(true)
    setSummaryError(null)
    setActiveTab('summary')

    try {
      const data = await generateSummaryApi({
        videoId: video.id,
        title: video.title,
        chunks: video.transcript.chunks,
        fullText: video.transcript.full_text,
      })
      setSummaryData(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred during summary generation.'
      setSummaryError(msg)
    } finally {
      setIsGeneratingSummary(false)
    }
  }

  // AI Structured Notes Generation Handler
  const handleGenerateNotes = async () => {
    if (!video || !video.transcript?.chunks || video.transcript.chunks.length === 0) return

    setIsGeneratingNotes(true)
    setNotesError(null)
    setActiveTab('notes')

    try {
      const data = await generateNotesApi({
        videoId: video.id,
        title: video.title,
        chunks: video.transcript.chunks,
        fullText: video.transcript.full_text,
      })
      setNotesData(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred during notes generation.'
      setNotesError(msg)
    } finally {
      setIsGeneratingNotes(false)
    }
  }

  // AI Quiz Generation Handler
  const handleGenerateQuiz = async () => {
    if (!video || !video.transcript?.chunks || video.transcript.chunks.length === 0) return

    setIsGeneratingQuiz(true)
    setQuizError(null)
    setQuizEvaluation(null)
    setEvaluationError(null)
    setActiveTab('quiz')

    try {
      const data = await generateQuizApi({
        videoId: video.id,
        title: video.title,
        chunks: video.transcript.chunks,
        numQuestions: 5,
      })
      setQuizData(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred during quiz generation.'
      setQuizError(msg)
    } finally {
      setIsGeneratingQuiz(false)
    }
  }

  // Quiz Evaluation Handler
  const handleEvaluateQuiz = async (selectedAnswers: Record<string, string>) => {
    if (!quizData?.quiz?.quiz_id) return

    setIsEvaluatingQuiz(true)
    setEvaluationError(null)

    try {
      const result = await evaluateQuizApi({
        quizId: quizData.quiz.quiz_id,
        selectedAnswers,
      })
      setQuizEvaluation(result)
      if (video?.id) {
        handleLoadKnowledgeGaps(video.id)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred during quiz evaluation.'
      setEvaluationError(msg)
    } finally {
      setIsEvaluatingQuiz(false)
    }
  }

  // Retake Quiz
  const handleRetakeQuiz = () => {
    setQuizEvaluation(null)
    setEvaluationError(null)
  }

  // Fetch Deterministic Knowledge Gaps
  const handleLoadKnowledgeGaps = async (videoIdOverride?: string) => {
    const targetVideoId = videoIdOverride || video?.id
    if (!targetVideoId) return

    setIsLoadingGaps(true)
    setGapsError(null)

    try {
      const data = await fetchVideoKnowledgeGapsApi(targetVideoId)
      setKnowledgeGapsData(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve knowledge gaps from backend.'
      setGapsError(msg)
    } finally {
      setIsLoadingGaps(false)
    }
  }

  // AI Flashcards Generation Handler
  const handleGenerateFlashcards = async () => {
    if (!video || !video.transcript?.chunks || video.transcript.chunks.length === 0) return

    setIsGeneratingFlashcards(true)
    setFlashcardsError(null)
    setActiveTab('flashcards')

    try {
      const data = await generateFlashcardsApi({
        videoId: video.id,
        title: video.title,
        chunks: video.transcript.chunks,
        numCards: 6,
      })
      setFlashcardsData(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred during flashcard generation.'
      setFlashcardsError(msg)
    } finally {
      setIsGeneratingFlashcards(false)
    }
  }

  const formatPlatformLabel = (platform: VideoPlatform): string => {
    switch (platform) {
      case 'youtube':
        return 'YouTube'
      case 'direct':
        return 'Direct Stream'
      case 'unknown':
      default:
        return 'Web Source'
    }
  }

  // Whether workspace is in active lecture mode
  const isWorkspaceActive = Boolean(video && video.status === 'completed')

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-start p-3 sm:p-6 selection:bg-indigo-500 selection:text-white">
      {/* =========================================================================
          Top Application Navigation Bar
         ========================================================================= */}
      <header className="w-full max-w-7xl flex flex-wrap items-center justify-between gap-3 pb-4 mb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-md shadow-indigo-600/30 font-bold text-white text-sm">
            V
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-2">
              <span>VIDYORA AI</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                Workspace v0.2
              </span>
            </h1>
            <p className="text-[10px] text-slate-400">
              Interactive Video Learning & Adaptive Retention Platform
            </p>
          </div>
        </div>

        {/* Global Action Bar */}
        <div className="flex items-center gap-2">
          {/* Quick Backend Connectivity Indicator */}
          <BackendStatus />

          {/* Persistent Learning Library Trigger */}
          {currentUser && (
            <button
              type="button"
              onClick={() => setShowLibraryModal(true)}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-slate-200 text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-sm"
              title="Browse previously ingested lectures"
            >
              <span>📚</span>
              <span>Library</span>
            </button>
          )}

          {/* New Video Intake Trigger */}
          {currentUser && isWorkspaceActive && (
            <button
              type="button"
              onClick={() => setShowNewVideoModal(!showNewVideoModal)}
              className="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-sm"
              title="Process another lecture URL"
            >
              <span>+</span>
              <span>New Video</span>
            </button>
          )}

          {isWorkspaceActive && (
            <button
              type="button"
              onClick={handleClear}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-800 text-xs font-medium transition cursor-pointer"
              title="Close current lecture"
            >
              Clear
            </button>
          )}

          {/* User Account & Authentication Status */}
          {currentUser ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-xl text-xs">
                <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-[10px] font-bold text-white uppercase">
                  {currentUser.full_name?.[0] || currentUser.email[0]}
                </div>
                <span className="text-slate-200 font-medium max-w-[110px] truncate" title={currentUser.email}>
                  {currentUser.full_name || currentUser.username || currentUser.email.split('@')[0]}
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="ml-1 text-[11px] text-slate-400 hover:text-rose-400 transition cursor-pointer"
                  title="Sign Out"
                >
                  Sign Out
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setAuthModalInitialMode('login')
                  setShowAuthModal(true)
                }}
                className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition cursor-pointer"
              >
                Sign In
              </button>
            </div>
          )}
        </div>
      </header>

      {/* =========================================================================
          Persistent Library Modal / Drawer
         ========================================================================= */}
      {showLibraryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-5 space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-base">📚</span>
                <h3 className="text-sm font-bold text-white">Saved Learning Library</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowLibraryModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 text-xs cursor-pointer"
              >
                ✕
              </button>
            </div>
            <LearningLibrary
              onSelectVideo={handleSelectLibraryVideo}
              currentVideoId={video?.id}
              isLoadingWorkspace={isLoadingWorkspace}
            />
          </div>
        </div>
      )}

      {/* =========================================================================
          New Video Modal
         ========================================================================= */}
      {showNewVideoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white">Process New Educational Lecture</h3>
              <button
                type="button"
                onClick={() => setShowNewVideoModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 text-xs cursor-pointer"
              >
                ✕
              </button>
            </div>
            <VideoInput
              onSubmit={handleVideoSubmit}
              isLoading={isSubmitting}
              serverError={submissionError}
              onClearError={() => setSubmissionError(null)}
            />
          </div>
        </div>
      )}

      {/* =========================================================================
          Main Content: Intake Mode vs. Interactive Workspace Mode
         ========================================================================= */}
      <main className="w-full max-w-7xl flex flex-col space-y-6">
        {/* CASE A: No Active Lecture Loaded -> Show Welcome Hero, Library, and Intake */}
        {!isWorkspaceActive && (
          <div className="w-full max-w-2xl mx-auto flex flex-col space-y-6 pt-4 animate-fadeIn">
            <WelcomeBanner title="VIDYORA AI: Learn Smarter" />

            {isAuthChecking ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-3">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-slate-400">Verifying session...</p>
              </div>
            ) : !currentUser ? (
              <div className="bg-slate-900/90 p-8 rounded-2xl border border-slate-800/90 shadow-2xl space-y-5 text-center">
                <div className="w-12 h-12 mx-auto rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-2xl">
                  🔒
                </div>
                <div className="space-y-1.5">
                  <h2 className="text-lg font-bold text-white tracking-tight">
                    Sign in to Your Personalized Learning Workspace
                  </h2>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
                    Every learner's video library, notes, quizzes, and adaptive recoveries are strictly isolated. Sign in or register to begin.
                  </p>
                </div>
                <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setAuthModalInitialMode('login')
                      setShowAuthModal(true)
                    }}
                    className="w-full sm:w-auto px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20 transition cursor-pointer"
                  >
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthModalInitialMode('register')
                      setShowAuthModal(true)
                    }}
                    className="w-full sm:w-auto px-6 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition cursor-pointer"
                  >
                    Create Account
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800/80 shadow-xl space-y-4">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>🎯</span>
                    <span>Enter Lecture Video to Begin</span>
                  </h2>
                  <VideoInput
                    onSubmit={handleVideoSubmit}
                    isLoading={isSubmitting}
                    serverError={submissionError}
                    onClearError={() => setSubmissionError(null)}
                  />
                </div>

                {/* Persistent Learning Library Grid on Intake View */}
                <LearningLibrary
                  onSelectVideo={handleSelectLibraryVideo}
                  currentVideoId={video?.id}
                  isLoadingWorkspace={isLoadingWorkspace}
                />
              </>
            )}
          </div>
        )}

        {/* CASE B: Active Lecture Loaded -> Full Interactive Video Learning Workspace */}
        {isWorkspaceActive && video && (
          <div className="w-full flex flex-col space-y-4 animate-fadeIn">
            {/* Lecture Meta Header Strip */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-sm">
              <div className="space-y-0.5 min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                    Active Lecture
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                    {formatPlatformLabel(video.platform)}
                  </span>
                  {isWorkspaceRestored && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-1">
                      <span>💾</span>
                      <span>Restored from PostgreSQL (0 AI Calls)</span>
                    </span>
                  )}
                </div>
                <h2 className="text-sm sm:text-base font-bold text-white tracking-tight truncate" title={video.title || 'Untitled Lecture'}>
                  {video.title || 'Untitled Educational Lecture'}
                </h2>
              </div>

              {/* Stats Counters */}
              {video.transcript && (
                <div className="flex items-center gap-3 text-[11px] text-slate-400 bg-slate-950/60 px-3 py-1.5 rounded-xl border border-slate-800/60 shrink-0">
                  <span><strong>{video.transcript.chunk_count ?? video.transcript.chunks?.length ?? 0}</strong> chunks</span>
                  <span>•</span>
                  <span><strong>{video.transcript.cleaned_segment_count ?? video.transcript.segment_count}</strong> segments</span>
                  <span>•</span>
                  <span><strong>{video.transcript.full_text.split(/\s+/).filter(Boolean).length}</strong> words</span>
                </div>
              )}
            </div>

            {/* Main Dual-Column Responsive Learning Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* ===================================================================
                  LEFT COLUMN: Interactive Video Player & Transcript / Chunks Pane
                 =================================================================== */}
              <div className="lg:col-span-7 xl:col-span-7 space-y-4">
                {/* 1. Real Embedded Video Player with Custom Controls */}
                <div ref={playerContainerRef}>
                  <VideoPlayer
                    ref={playerRef}
                    videoId={video.id}
                    title={video.title}
                    originalUrl={video.url}
                    onTimeUpdate={(cur, dur) => {
                      setCurrentTime(cur)
                      setVideoDuration(dur)
                    }}
                    onStateChange={(playing) => setIsPlaying(playing)}
                    activeConceptLabel={activeConceptLabel}
                  />
                </div>

                {/* 2. Left Companion Navigation Tabs */}
                <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto text-xs">
                  <button
                    type="button"
                    onClick={() => setLeftTab('transcript')}
                    className={`px-3 py-1.5 rounded-xl font-medium transition cursor-pointer flex items-center gap-1.5 shrink-0 ${
                      leftTab === 'transcript'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>📜</span>
                    <span>Synchronized Transcript</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setLeftTab('chunks')}
                    className={`px-3 py-1.5 rounded-xl font-medium transition cursor-pointer flex items-center gap-1.5 shrink-0 ${
                      leftTab === 'chunks'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>🧩</span>
                    <span>Knowledge Chunks ({video.transcript?.chunks?.length ?? 0})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setLeftTab('details')}
                    className={`px-3 py-1.5 rounded-xl font-medium transition cursor-pointer flex items-center gap-1.5 shrink-0 ${
                      leftTab === 'details'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>ℹ️</span>
                    <span>Details & Metadata</span>
                  </button>
                </div>

                {/* 3. Left Companion Content */}
                <div>
                  {leftTab === 'transcript' && video.transcript && (
                    <InteractiveTranscript
                      segments={video.transcript.cleaned_segments || video.transcript.segments}
                      currentTime={currentTime}
                      onSeek={(sec) => handleSeekTo(sec, true)}
                      chunks={video.transcript.chunks}
                    />
                  )}

                  {leftTab === 'chunks' && video.transcript?.chunks && (
                    <KnowledgeChunksList
                      chunks={video.transcript.chunks}
                      currentTime={currentTime}
                      onSeek={(sec) => handleSeekTo(sec, true)}
                    />
                  )}

                  {leftTab === 'details' && (
                    <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 text-xs space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <span className="text-[10px] uppercase font-semibold text-slate-500 block">Video Identifier</span>
                          <span className="font-mono text-indigo-400 text-xs">{video.id}</span>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-semibold text-slate-500 block">Language / Captions</span>
                          <span className="text-slate-300 text-xs font-mono">
                            {video.transcript?.language.toUpperCase()} ({video.transcript?.is_generated ? 'Automatic ASR' : 'Manual'})
                          </span>
                        </div>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-500 block">Original Source URL</span>
                        <a
                          href={video.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono text-xs text-indigo-300 hover:underline break-all"
                        >
                          {video.url} ↗
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* ===================================================================
                  RIGHT COLUMN: AI Learning Tools, Notes, Quizzes, Gaps & Recovery
                 =================================================================== */}
              <div className="lg:col-span-5 xl:col-span-5 space-y-4">
                {/* 1. AI Content Generation Action Bar */}
                {video.transcript && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <button
                      type="button"
                      onClick={handleGenerateNotes}
                      disabled={isGeneratingNotes || !video.transcript.chunks?.length}
                      className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-slate-100 font-medium text-xs disabled:opacity-50 disabled:cursor-not-allowed transition cursor-pointer shadow-sm group"
                      title="Synthesize structured lecture notes"
                    >
                      {isGeneratingNotes ? (
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin"></div>
                      ) : (
                        <span className="text-indigo-400 group-hover:scale-110 transition">📝</span>
                      )}
                      <span>{notesData ? 'Regen Notes' : 'Study Notes'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleGenerateSummary}
                      disabled={isGeneratingSummary || !video.transcript.chunks?.length}
                      className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-medium text-xs shadow-md shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition cursor-pointer group"
                      title="Generate executive overview and key takeaways"
                    >
                      {isGeneratingSummary ? (
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                      ) : (
                        <span className="text-amber-300 group-hover:scale-110 transition">✨</span>
                      )}
                      <span>{summaryData ? 'Regen Summary' : 'Summary'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleGenerateQuiz}
                      disabled={isGeneratingQuiz || !video.transcript.chunks?.length}
                      className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-gradient-to-r from-violet-600 to-purple-700 hover:from-violet-500 hover:to-purple-600 text-white font-medium text-xs shadow-md shadow-violet-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition cursor-pointer group"
                      title="Generate multiple choice quiz questions"
                    >
                      {isGeneratingQuiz ? (
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                      ) : (
                        <span className="text-violet-300 group-hover:scale-110 transition">🎯</span>
                      )}
                      <span>{quizData ? 'Regen Quiz' : 'Quiz'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleGenerateFlashcards}
                      disabled={isGeneratingFlashcards || !video.transcript.chunks?.length}
                      className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-700 hover:from-teal-500 hover:to-emerald-600 text-white font-medium text-xs shadow-md shadow-teal-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition cursor-pointer group"
                      title="Build active recall flashcards"
                    >
                      {isGeneratingFlashcards ? (
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin"></div>
                      ) : (
                        <span className="text-teal-300 group-hover:scale-110 transition">🗂️</span>
                      )}
                      <span>{flashcardsData ? 'Regen Cards' : 'Cards'}</span>
                    </button>
                  </div>
                )}

                {/* 2. Study Suite Content Navigation Tabs */}
                <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto text-xs">
                  <button
                    id="tab-ask"
                    type="button"
                    onClick={() => setActiveTab('ask')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'ask'
                        ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>💬 Ask VIDYORA</span>
                  </button>

                  <button
                    id="tab-notes"
                    type="button"
                    onClick={() => setActiveTab('notes')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'notes'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>📝 Notes</span>
                    {notesData && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
                  </button>

                  <button
                    id="tab-summary"
                    type="button"
                    onClick={() => setActiveTab('summary')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'summary'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>✨ Summary</span>
                    {summaryData && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
                  </button>

                  <button
                    id="tab-quiz"
                    type="button"
                    onClick={() => setActiveTab('quiz')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'quiz'
                        ? 'bg-violet-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>🎯 Quiz</span>
                    {quizData && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
                  </button>

                  <button
                    id="tab-flashcards"
                    type="button"
                    onClick={() => setActiveTab('flashcards')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'flashcards'
                        ? 'bg-teal-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>🗂️ Cards</span>
                    {flashcardsData && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
                  </button>

                  <button
                    id="tab-gaps"
                    type="button"
                    onClick={() => {
                      setActiveTab('gaps')
                      if (!knowledgeGapsData && video?.id) {
                        handleLoadKnowledgeGaps(video.id)
                      }
                    }}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 ${
                      activeTab === 'gaps'
                        ? 'bg-rose-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                    }`}
                  >
                    <span>📊 Gaps</span>
                    {knowledgeGapsData && knowledgeGapsData.weak_chunk_ids.length > 0 ? (
                      <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                        {knowledgeGapsData.weak_chunk_ids.length}
                      </span>
                    ) : knowledgeGapsData ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                    ) : null}
                  </button>

                  {/* Dynamic Recovery Tab when session is engaged */}
                  {activeRecoveryChunk && (
                    <button
                      id="tab-recovery"
                      type="button"
                      onClick={() => setActiveTab('recovery')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium transition cursor-pointer shrink-0 animate-pulse ${
                        activeTab === 'recovery'
                          ? 'bg-amber-600 text-white shadow-sm'
                          : 'text-amber-400 bg-amber-500/10 border border-amber-500/30'
                      }`}
                    >
                      <span>🎯 Recovery</span>
                      <span className="text-[10px] font-mono">#{activeRecoveryChunk.chunk_index + 1}</span>
                    </button>
                  )}
                </div>

                {/* 3. Study Suite Content Display Area */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 shadow-lg min-h-[24rem]">
                  {/* Ask VIDYORA Grounded AI Tutor */}
                  {activeTab === 'ask' && video?.id && (
                    <AskVidyoraView
                      videoId={video.id}
                      videoTitle={video.title}
                      initialQuestion={askInitialQuestion}
                      onTimestampClick={(sec) => handleSeekTo(sec, true)}
                    />
                  )}

                  {/* Study Notes */}
                  {activeTab === 'notes' && (
                    <div>
                      {isGeneratingNotes && (
                        <div className="p-8 text-center space-y-3">
                          <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto"></div>
                          <p className="text-xs text-indigo-300 font-medium">Gemini is structuring lecture study notes...</p>
                        </div>
                      )}

                      {notesError && !isGeneratingNotes && (
                        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-2">
                          <p className="font-semibold">⚠️ Failed to Generate Study Notes</p>
                          <p>{notesError}</p>
                          <button
                            type="button"
                            onClick={handleGenerateNotes}
                            className="px-2.5 py-1 rounded bg-rose-500/20 text-rose-200 text-xs"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {notesData && !isGeneratingNotes && (
                        <NotesView
                          notes={notesData.notes}
                          modelUsed={notesData.model_used}
                          chunkCount={notesData.chunk_count}
                          onTimestampClick={(sec) => handleSeekTo(sec, true)}
                        />
                      )}

                      {!notesData && !isGeneratingNotes && !notesError && (
                        <div className="p-8 text-center space-y-3">
                          <span className="text-2xl">📝</span>
                          <p className="text-xs text-slate-300 font-medium">No Study Notes Generated Yet</p>
                          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                            Transform this lecture's transcript into structured section breakdowns and glossaries.
                          </p>
                          <button
                            type="button"
                            onClick={handleGenerateNotes}
                            className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition cursor-pointer"
                          >
                            Generate Notes
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Summary */}
                  {activeTab === 'summary' && (
                    <div>
                      {isGeneratingSummary && (
                        <div className="p-8 text-center space-y-3">
                          <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto"></div>
                          <p className="text-xs text-indigo-300 font-medium">Gemini is synthesizing executive summary...</p>
                        </div>
                      )}

                      {summaryError && !isGeneratingSummary && (
                        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-2">
                          <p className="font-semibold">⚠️ Failed to Generate Summary</p>
                          <p>{summaryError}</p>
                          <button
                            type="button"
                            onClick={handleGenerateSummary}
                            className="px-2.5 py-1 rounded bg-rose-500/20 text-rose-200 text-xs"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {summaryData && !isGeneratingSummary && (
                        <SummaryView
                          summary={summaryData.summary}
                          modelUsed={summaryData.model_used}
                          chunkCount={summaryData.chunk_count}
                          onTimestampClick={(sec) => handleSeekTo(sec, true)}
                        />
                      )}

                      {!summaryData && !isGeneratingSummary && !summaryError && (
                        <div className="p-8 text-center space-y-3">
                          <span className="text-2xl">✨</span>
                          <p className="text-xs text-slate-300 font-medium">No Summary Generated Yet</p>
                          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                            Synthesize an overview, core concepts, takeaways, and ELI5 explanation.
                          </p>
                          <button
                            type="button"
                            onClick={handleGenerateSummary}
                            className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition cursor-pointer"
                          >
                            Generate Summary
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Quiz */}
                  {activeTab === 'quiz' && (
                    <div>
                      {isGeneratingQuiz && (
                        <div className="p-8 text-center space-y-3">
                          <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin mx-auto"></div>
                          <p className="text-xs text-violet-300 font-medium">Gemini is crafting formative quiz...</p>
                        </div>
                      )}

                      {quizError && !isGeneratingQuiz && (
                        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-2">
                          <p className="font-semibold">⚠️ Failed to Generate Quiz</p>
                          <p>{quizError}</p>
                          <button
                            type="button"
                            onClick={handleGenerateQuiz}
                            className="px-2.5 py-1 rounded bg-rose-500/20 text-rose-200 text-xs"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {quizData && !isGeneratingQuiz && (
                        <QuizView
                          quiz={quizData.quiz}
                          evaluation={quizEvaluation}
                          isSubmitting={isEvaluatingQuiz}
                          submissionError={evaluationError}
                          modelUsed={quizData.model_used}
                          chunkCount={quizData.chunk_count}
                          onSubmitAnswers={handleEvaluateQuiz}
                          onRetakeQuiz={handleRetakeQuiz}
                          onRegenerateQuiz={handleGenerateQuiz}
                          onTimestampClick={(sec) => handleSeekTo(sec, true)}
                        />
                      )}

                      {!quizData && !isGeneratingQuiz && !quizError && (
                        <div className="p-8 text-center space-y-3">
                          <span className="text-2xl">🎯</span>
                          <p className="text-xs text-slate-300 font-medium">No Quiz Generated Yet</p>
                          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                            Take a 5-question multiple choice assessment grounded directly in lecture moments.
                          </p>
                          <button
                            type="button"
                            onClick={handleGenerateQuiz}
                            className="px-3.5 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-medium text-xs transition cursor-pointer"
                          >
                            Generate Quiz
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Flashcards */}
                  {activeTab === 'flashcards' && (
                    <div>
                      {isGeneratingFlashcards && (
                        <div className="p-8 text-center space-y-3">
                          <div className="w-8 h-8 rounded-full border-2 border-teal-500 border-t-transparent animate-spin mx-auto"></div>
                          <p className="text-xs text-teal-300 font-medium">Gemini is synthesizing flashcards...</p>
                        </div>
                      )}

                      {flashcardsError && !isGeneratingFlashcards && (
                        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-2">
                          <p className="font-semibold">⚠️ Failed to Generate Flashcards</p>
                          <p>{flashcardsError}</p>
                          <button
                            type="button"
                            onClick={handleGenerateFlashcards}
                            className="px-2.5 py-1 rounded bg-rose-500/20 text-rose-200 text-xs"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {flashcardsData && !isGeneratingFlashcards && (
                        <FlashcardsView
                          flashcards={flashcardsData.flashcards}
                          modelUsed={flashcardsData.model_used}
                          chunkCount={flashcardsData.chunk_count}
                          onRegenerateFlashcards={handleGenerateFlashcards}
                          onTimestampClick={(sec) => handleSeekTo(sec, true)}
                        />
                      )}

                      {!flashcardsData && !isGeneratingFlashcards && !flashcardsError && (
                        <div className="p-8 text-center space-y-3">
                          <span className="text-2xl">🗂️</span>
                          <p className="text-xs text-slate-300 font-medium">No Flashcards Generated Yet</p>
                          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                            Generate interactive active-recall cards for terms and formulas.
                          </p>
                          <button
                            type="button"
                            onClick={handleGenerateFlashcards}
                            className="px-3.5 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-medium text-xs transition cursor-pointer"
                          >
                            Generate Flashcard Deck
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Knowledge Gaps */}
                  {activeTab === 'gaps' && (
                    <KnowledgeGapView
                      knowledgeGaps={knowledgeGapsData}
                      isLoading={isLoadingGaps}
                      error={gapsError}
                      onRetry={() => handleLoadKnowledgeGaps()}
                      videoUrl={video.url}
                      videoId={video.id}
                      onReviewInVideo={handleReviewInVideo}
                      onRecoveryCompleted={() => handleLoadKnowledgeGaps()}
                      onAskTutor={handleAskTutorAboutGap}
                      onPracticeQuiz={() => setActiveTab('quiz')}
                      onStartRecovery={(gap) => {
                        setActiveRecoveryChunk(gap)
                        setActiveTab('recovery')
                      }}
                    />
                  )}

                  {/* Learning Recovery (Embedded Side-by-Side Mode) */}
                  {activeTab === 'recovery' && activeRecoveryChunk && (
                    <LearningRecoveryView
                      isEmbedded={true}
                      videoId={video.id}
                      chunk={activeRecoveryChunk}
                      videoUrl={video.url}
                      onClose={() => {
                        setActiveRecoveryChunk(null)
                        setActiveTab('gaps')
                      }}
                      onReviewInVideo={handleReviewInVideo}
                      onPracticeQuiz={() => setActiveTab('quiz')}
                      onRecoveryCompleted={() => handleLoadKnowledgeGaps()}
                      onOpenAskTutor={handleAskTutorWithQuestion}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* =========================================================================
          Authentication Modal (Sign In / Register)
         ========================================================================= */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        initialMode={authModalInitialMode}
        onSuccess={(user) => {
          setCurrentUser(user)
          setShowAuthModal(false)
        }}
        canClose={Boolean(currentUser)}
      />
    </div>
  )
}
