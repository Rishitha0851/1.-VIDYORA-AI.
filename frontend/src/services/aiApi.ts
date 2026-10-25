/**
 * VIDYORA AI - AI API Service Client
 * 
 * Provides type-safe wrappers for backend AI generation and evaluation endpoints.
 * Centralizes error extraction, authentication headers, and payload serialization.
 */

import type {
  FlashcardsResponse,
  LearnerOverallKnowledgeGapsResponse,
  NotesResponse,
  QuizAttemptHistoryResponse,
  QuizEvaluationResponse,
  QuizResponse,
  RecoveryEvaluationResponse,
  RecoverySessionClientView,
  SummaryResponse,
  VideoKnowledgeGapsResponse,
  VideoListResponse,
  VideoWorkspaceResponse,
  AskVidyoraResponse,
  ChatHistoryResponse,
} from '../types/ai'
import { API_BASE_URL, clearAuthToken, getAuthHeaders } from './authApi'

const BASE_URL = API_BASE_URL

interface TranscriptChunkPayload {
  chunk_id: string
  chunk_index: number
  video_id: string
  text: string
  start_time: number
  end_time: number
  duration: number
  word_count: number
  segment_start_index: number
  segment_end_index: number
}

async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorDetail = `Request failed with HTTP ${response.status}`
    try {
      const errJson = await response.json()
      if (errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((d: { msg?: string }) => d.msg || 'Validation error').join(', ')
        } else {
          errorDetail = JSON.stringify(errJson.detail)
        }
      }
    } catch {
      // Fallback to HTTP error
    }

    if (response.status === 401) {
      clearAuthToken()
      errorDetail = 'Session expired or unauthenticated. Please sign in again.'
    }
    throw new Error(errorDetail)
  }
  return response.json()
}

/**
 * Ingests and processes a YouTube video URL into clean transcript chunks.
 */
export async function processVideoApi<T = unknown>(url: string): Promise<T> {
  const response = await fetch(`${BASE_URL}/api/videos/process`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ url }),
  })
  return handleApiResponse<T>(response)
}

/**
 * Generates an educational summary grounded in the video's transcript chunks.
 */
export async function generateSummaryApi(params: {
  videoId: string
  title: string | null
  chunks: TranscriptChunkPayload[]
  fullText?: string
}): Promise<SummaryResponse> {
  const response = await fetch(`${BASE_URL}/api/ai/summary`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      title: params.title,
      chunks: params.chunks,
      full_text: params.fullText,
    }),
  })
  return handleApiResponse<SummaryResponse>(response)
}

/**
 * Generates structured, hierarchical study notes from transcript chunks.
 */
export async function generateNotesApi(params: {
  videoId: string
  title: string | null
  chunks: TranscriptChunkPayload[]
  fullText?: string
}): Promise<NotesResponse> {
  const response = await fetch(`${BASE_URL}/api/ai/notes`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      title: params.title,
      chunks: params.chunks,
      full_text: params.fullText,
    }),
  })
  return handleApiResponse<NotesResponse>(response)
}

/**
 * Generates an interactive multiple-choice quiz from transcript chunks.
 * Note: Returned questions omit correct_answer and explanation for integrity.
 */
export async function generateQuizApi(params: {
  videoId: string
  title: string | null
  chunks: TranscriptChunkPayload[]
  numQuestions?: number
}): Promise<QuizResponse> {
  const response = await fetch(`${BASE_URL}/api/ai/quiz`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      title: params.title,
      chunks: params.chunks,
      num_questions: params.numQuestions ?? 5,
    }),
  })
  return handleApiResponse<QuizResponse>(response)
}

/**
 * Submits learner answers to the backend for deterministic grading,
 * adaptive performance tier assignment, and review analysis.
 */
export async function evaluateQuizApi(params: {
  quizId: string
  selectedAnswers: Record<string, string>
}): Promise<QuizEvaluationResponse> {
  const response = await fetch(`${BASE_URL}/api/ai/quiz/evaluate`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      quiz_id: params.quizId,
      selected_answers: params.selectedAnswers,
    }),
  })
  return handleApiResponse<QuizEvaluationResponse>(response)
}

/**
 * Generates a deck of active-recall conceptual flashcards.
 */
export async function generateFlashcardsApi(params: {
  videoId: string
  title: string | null
  chunks: TranscriptChunkPayload[]
  numCards?: number
}): Promise<FlashcardsResponse> {
  const response = await fetch(`${BASE_URL}/api/ai/flashcards`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      title: params.title,
      chunks: params.chunks,
      num_cards: params.numCards ?? 8,
    }),
  })
  return handleApiResponse<FlashcardsResponse>(response)
}

/**
 * Step 13 Phase 4: Retrieves all previously persisted videos from PostgreSQL for the current user.
 */
export async function fetchPersistedVideosApi(): Promise<VideoListResponse> {
  const response = await fetch(`${BASE_URL}/api/videos`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<VideoListResponse>(response)
}

/**
 * Step 13 Phase 4: Reloads an entire educational workspace directly from PostgreSQL.
 * Does not re-run transcript extraction or Gemini.
 */
export async function fetchVideoWorkspaceApi(videoId: string): Promise<VideoWorkspaceResponse> {
  const response = await fetch(`${BASE_URL}/api/videos/${encodeURIComponent(videoId)}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<VideoWorkspaceResponse>(response)
}

/**
 * Step 13 Phase 4: Retrieves all historical attempts for a persisted quiz from PostgreSQL.
 */
export async function fetchQuizAttemptsApi(quizId: string): Promise<QuizAttemptHistoryResponse> {
  const response = await fetch(`${BASE_URL}/api/quizzes/${encodeURIComponent(quizId)}/attempts`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<QuizAttemptHistoryResponse>(response)
}

/**
 * Step 14 Phase 1 & 2: Retrieves the deterministic knowledge gap profile for a specific video.
 * Grounded in historical quiz answers linked to video knowledge chunks.
 */
export async function fetchVideoKnowledgeGapsApi(videoId: string): Promise<VideoKnowledgeGapsResponse> {
  const response = await fetch(`${BASE_URL}/api/videos/${encodeURIComponent(videoId)}/knowledge-gaps`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<VideoKnowledgeGapsResponse>(response)
}

/**
 * Step 14 Phase 1 & 2: Retrieves the cross-video learner knowledge gap profile.
 */
export async function fetchLearnerKnowledgeGapsApi(userId?: string): Promise<LearnerOverallKnowledgeGapsResponse> {
  const url = userId
    ? `${BASE_URL}/api/learners/${encodeURIComponent(userId)}/knowledge-gaps`
    : `${BASE_URL}/api/learners/knowledge-gaps`
  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<LearnerOverallKnowledgeGapsResponse>(response)
}

/**
 * Step 14 Phase 3: Initiates a targeted learning recovery session for a weak chunk.
 */
export async function createRecoverySessionApi(params: {
  videoId: string
  chunkId: string
  userId?: string | null
  reuseExisting?: boolean
}): Promise<RecoverySessionClientView> {
  const response = await fetch(`${BASE_URL}/api/recovery`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      chunk_id: params.chunkId,
      user_id: params.userId ?? null,
      reuse_existing: params.reuseExisting ?? false,
    }),
  })
  return handleApiResponse<RecoverySessionClientView>(response)
}

/**
 * Step 4: Retrieves the latest recovery session for a specific knowledge chunk.
 */
export async function fetchLatestChunkRecoverySessionApi(
  videoId: string,
  chunkId: string
): Promise<RecoverySessionClientView | null> {
  const response = await fetch(
    `${BASE_URL}/api/videos/${encodeURIComponent(videoId)}/chunks/${encodeURIComponent(chunkId)}/recovery`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  )
  if (response.status === 404) {
    return null
  }
  return handleApiResponse<RecoverySessionClientView | null>(response)
}

/**
 * Step 14 Phase 3: Retrieves a learning recovery session by ID.
 */
export async function fetchRecoverySessionApi(
  sessionId: string,
  userId?: string | null
): Promise<RecoverySessionClientView> {
  const url = userId
    ? `${BASE_URL}/api/recovery/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`
    : `${BASE_URL}/api/recovery/${encodeURIComponent(sessionId)}`
  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<RecoverySessionClientView>(response)
}

/**
 * Step 14 Phase 3: Submits learner answers for deterministic recovery evaluation.
 */
export async function submitRecoverySessionApi(params: {
  sessionId: string
  selectedAnswers: Record<string, string>
  userId?: string | null
}): Promise<RecoveryEvaluationResponse> {
  const url = params.userId
    ? `${BASE_URL}/api/recovery/${encodeURIComponent(params.sessionId)}/submit?user_id=${encodeURIComponent(params.userId)}`
    : `${BASE_URL}/api/recovery/${encodeURIComponent(params.sessionId)}/submit`
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      selected_answers: params.selectedAnswers,
    }),
  })
  return handleApiResponse<RecoveryEvaluationResponse>(response)
}

/**
 * Step 14 Phase 3: Retrieves all past recovery sessions for a specific chunk.
 */
export async function fetchChunkRecoveryHistoryApi(
  videoId: string,
  chunkId: string,
  userId?: string | null
): Promise<RecoverySessionClientView[]> {
  const url = userId
    ? `${BASE_URL}/api/videos/${encodeURIComponent(videoId)}/chunks/${encodeURIComponent(chunkId)}/recovery-history?user_id=${encodeURIComponent(userId)}`
    : `${BASE_URL}/api/videos/${encodeURIComponent(videoId)}/chunks/${encodeURIComponent(chunkId)}/recovery-history`
  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<RecoverySessionClientView[]>(response)
}

/**
 * Step 3: Ask VIDYORA Grounded AI Tutor API
 */

export async function askVidyoraApi(params: {
  videoId: string
  question: string
}): Promise<AskVidyoraResponse> {
  const response = await fetch(`${BASE_URL}/api/chat/ask`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      video_id: params.videoId,
      question: params.question,
    }),
  })
  return handleApiResponse<AskVidyoraResponse>(response)
}

export async function fetchChatHistoryApi(videoId: string): Promise<ChatHistoryResponse> {
  const response = await fetch(`${BASE_URL}/api/chat/${encodeURIComponent(videoId)}/history`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<ChatHistoryResponse>(response)
}

export async function clearChatHistoryApi(
  videoId: string
): Promise<{ status: string; message: string; deleted_count: number }> {
  const response = await fetch(`${BASE_URL}/api/chat/${encodeURIComponent(videoId)}/history`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
  return handleApiResponse<{ status: string; message: string; deleted_count: number }>(response)
}

