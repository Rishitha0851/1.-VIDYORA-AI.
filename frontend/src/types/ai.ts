/**
 * Step 11: AI-Powered Summarization & Structured Notes Type Definitions
 */

export interface SourceTimestamp {
  timestamp: number
  formatted_time: string
  label: string
}

export interface VideoSummary {
  overview: string
  main_concepts: string[]
  takeaways: string[]
  beginner_explanation: string
  source_timestamps: SourceTimestamp[]
}

export interface SummaryResponse {
  status: string
  video_id: string
  summary: VideoSummary
  model_used: string
  chunk_count: number
}

export interface TerminologyItem {
  term: string
  definition: string
  context?: string | null
}

export interface NoteSection {
  title: string
  summary: string
  key_points: string[]
  start_time?: number | null
  formatted_time?: string | null
}

export interface StructuredNotes {
  topic_title: string
  introduction: string
  main_concepts: string[]
  sections: NoteSection[]
  terminology: TerminologyItem[]
  examples: string[]
  key_takeaways: string[]
  relevant_timestamps: SourceTimestamp[]
}

export interface NotesResponse {
  status: string
  video_id: string
  notes: StructuredNotes
  model_used: string
  chunk_count: number
}

/**
 * Step 12: AI-Powered Adaptive Quiz & Flashcards Type Definitions
 */

export type QuizDifficulty = 'easy' | 'medium' | 'hard'

export type PerformanceTier = 'Strong' | 'Developing' | 'Needs Revision'

/** Sanitized quiz question received by frontend (no correct_answer or explanation) */
export interface QuizQuestionClient {
  id: string
  question: string
  options: string[]
  difficulty: QuizDifficulty
  source_timestamp: SourceTimestamp
  source_chunk_id?: string | null
}

export interface QuizClientView {
  quiz_id: string
  video_id: string
  title: string
  instructions: string
  questions: QuizQuestionClient[]
  question_count: number
}

export interface QuizResponse {
  status: string
  video_id: string
  quiz: QuizClientView
  model_used: string
  chunk_count: number
}

export interface QuestionResult {
  question_id: string
  question: string
  selected_answer?: string | null
  correct_answer: string
  is_correct: boolean
  explanation: string
  difficulty: QuizDifficulty
  source_timestamp: SourceTimestamp
  source_chunk_id?: string | null
}

export interface QuizEvaluationResponse {
  quiz_id: string
  total_questions: number
  correct_count: number
  score_percentage: number
  performance_tier: PerformanceTier
  performance_summary: string
  question_results: QuestionResult[]
  weak_chunk_ids: string[]
}

export interface Flashcard {
  id: string
  front: string
  back: string
  difficulty: QuizDifficulty
  source_timestamp: SourceTimestamp
  source_chunk_id?: string | null
}

export interface GeneratedFlashcards {
  topic: string
  cards: Flashcard[]
  card_count: number
}

export interface FlashcardsResponse {
  status: string
  video_id: string
  flashcards: GeneratedFlashcards
  model_used: string
  chunk_count: number
}

/**
 * Step 13 Phase 4: Persistent Read & History Type Definitions
 */

export interface VideoListItem {
  video_id: string
  platform: string
  url: string
  title: string | null
  status: string
  created_at: string
  updated_at: string
  segment_count: number
  chunk_count: number
  has_transcript: boolean
  has_quiz: boolean
  has_flashcards: boolean
}

export interface VideoListResponse {
  videos: VideoListItem[]
  total_count: number
}

export interface VideoWorkspaceResponse {
  video: {
    id: string
    url: string
    platform: 'youtube' | 'direct' | 'unknown'
    title: string | null
    status: 'submitted' | 'validating' | 'accepted' | 'processing' | 'completed' | 'failed'
    created_at: string
    updated_at: string
    error_message?: string | null
    transcript?: {
      video_id: string
      language: string
      is_generated: boolean
      full_text: string
      segments: { text: string; start: number; duration: number }[]
      segment_count: number
      cleaned_segments?: { text: string; start: number; duration: number }[]
      cleaned_segment_count?: number
      chunks?: {
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
      }[]
      chunk_count?: number
    } | null
  }
  latest_quiz: QuizClientView | null
  latest_flashcards: GeneratedFlashcards | null
  summary: VideoSummary | null
  notes: StructuredNotes | null
  available_quizzes_count: number
  available_decks_count: number
}

export interface QuizAttemptAnswerHistory {
  question_id: string
  selected_answer: string | null
  is_correct: boolean
}

export interface QuizAttemptHistoryItem {
  attempt_id: string
  quiz_id: string
  score: number
  total_questions: number
  score_percentage: number
  performance_tier: PerformanceTier
  performance_summary: string | null
  weak_chunk_ids: string[]
  submitted_at: string
  answers: QuizAttemptAnswerHistory[]
}

export interface QuizAttemptHistoryResponse {
  quiz_id: string
  total_attempts: number
  attempts: QuizAttemptHistoryItem[]
}

/**
 * Step 14 Phase 1 & 2: Deterministic Learner Knowledge Gap Engine Types
 */

export type KnowledgeGapClassification = 'STRONG' | 'DEVELOPING' | 'WEAK' | 'INSUFFICIENT_DATA'

export type PerformanceTrend = 'IMPROVING' | 'STABLE' | 'DECLINING' | 'INSUFFICIENT_DATA'

export interface ChunkKnowledgeGap {
  chunk_id: string
  chunk_index: number
  video_id: string
  source_timestamp: SourceTimestamp
  classification: KnowledgeGapClassification
  trend: PerformanceTrend
  accuracy: float_or_number
  confidence_level?: string | null
  recovery_session_id?: string | null
  total_observations: number
  correct_count: number
  incorrect_count: number
  unanswered_count?: number
  concept_name?: string
  recommended_action?: string
  recovery_status?: string
  distinct_attempts_count: number
  most_recent_result: boolean | null
  most_recent_attempt_at: string | null
  consecutive_incorrect_count: number
  consecutive_correct_count: number
  has_demonstrated_mastery: boolean
  reason: string
  chunk_summary_text?: string | null
  latest_recovery_result?: string | null
  has_recovered?: boolean
}

// Helper type alias for numeric accuracy
type float_or_number = number

export interface VideoKnowledgeGapSummary {
  total_chunks: number
  assessed_chunks: number
  weak_chunks_count: number
  developing_chunks_count: number
  strong_chunks_count: number
  insufficient_data_count: number
  overall_accuracy: number
  recovered_chunks_count?: number
  recovery_in_progress_count?: number
}

export interface VideoKnowledgeGapsResponse {
  video_id: string
  summary: VideoKnowledgeGapSummary
  weak_chunk_ids: string[]
  gaps: ChunkKnowledgeGap[]
}

export interface LearnerOverallKnowledgeGapsResponse {
  user_id?: string | null
  summary: VideoKnowledgeGapSummary
  weak_chunk_ids: string[]
  gaps: ChunkKnowledgeGap[]
  videos_analyzed: number
}

/**
 * Step 14 Phase 3: Targeted Learning Recovery Engine Types
 */

export type RecoverySessionStatus =
  | 'CREATED'
  | 'EXPLANATION_GENERATED'
  | 'QUIZ_READY'
  | 'IN_PROGRESS'
  | 'EVALUATED'

export type RecoveryResultEnum =
  | 'RECOVERED'
  | 'IMPROVED'
  | 'NOT_RECOVERED'
  | 'INSUFFICIENT_EVIDENCE'

export interface RecoveryQuestionResult {
  question_id: string
  question: string
  selected_answer?: string | null
  correct_answer: string
  is_correct: boolean
  explanation: string
  source_timestamp: SourceTimestamp
}

export interface CreateRecoverySessionRequest {
  video_id: string
  chunk_id: string
  user_id?: string | null
  reuse_existing?: boolean
}

export interface RecoverySessionClientView {
  id: string
  video_id: string
  chunk_id: string
  chunk_index: number
  source_timestamp: SourceTimestamp
  originating_evidence: string
  attempt_number: number
  status: RecoverySessionStatus
  explanation_title?: string | null
  targeted_explanation?: string | null
  worked_example?: string | null
  key_takeaway?: string | null
  micro_quiz: QuizQuestionClient[]
  pre_recovery_accuracy: number
  chunk_text?: string | null
  post_recovery_accuracy?: number | null
  absolute_improvement?: number | null
  recovery_result?: RecoveryResultEnum | null
  result_summary?: string | null
  question_results?: RecoveryQuestionResult[]
  can_retry: boolean
  evaluated_at?: string | null
}

export interface RecoverySubmitRequest {
  selected_answers: Record<string, string>
}

export interface RecoveryEvaluationResponse {
  session_id: string
  video_id: string
  chunk_id: string
  attempt_number: number
  total_questions: number
  correct_count: number
  pre_recovery_accuracy: number
  post_recovery_accuracy: number
  absolute_improvement: number
  recovery_result: RecoveryResultEnum
  result_summary: string
  question_results: RecoveryQuestionResult[]
  can_retry: boolean
  evaluated_at: string
}

/** Time-aligned transcript segment */
export interface TranscriptSegment {
  text: string
  start: number
  duration: number
}

/** Structured knowledge chunk for downstream RAG and AI */
export interface TranscriptChunk {
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

/** Structured video transcript entity */
export interface VideoTranscript {
  video_id: string
  language: string
  is_generated: boolean
  full_text: string
  segments: TranscriptSegment[]
  segment_count: number
  cleaned_segments?: TranscriptSegment[]
  cleaned_segment_count?: number
  chunks?: TranscriptChunk[]
  chunk_count?: number
}

/**
 * Step 3: Ask VIDYORA Grounded AI Tutor Types
 */

export interface ChatSourceCitation {
  chunk_id: string
  chunk_index: number
  start_time: number
  end_time: number
  source_formatted_start: string
  source_formatted_end: string
  similarity: number
  text: string
}

export interface AskVidyoraRequest {
  video_id: string
  question: string
}

export interface AskVidyoraResponse {
  id: string
  video_id: string
  question: string
  answer: string
  sources: ChatSourceCitation[]
  model_used: string
  created_at: string
}

export interface ChatHistoryResponse {
  video_id: string
  total_messages: number
  messages: AskVidyoraResponse[]
}



