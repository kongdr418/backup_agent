import client from './client'

export interface LearnerProfileBasic {
  display_name: string
  learning_stage: string
  learning_basis: string
  background: string
}

export interface LearnerProfilePreferences {
  goal: string
  content_style: string[]
  preferred_difficulty: string
  tutoring_style: string
}

export interface ProfileTraitValue {
  weight?: number
  confidence: number
  source: 'self_reported' | 'inferred' | 'confirmed' | string
  status: 'confirmed' | 'pending' | 'unobserved' | string
  evidence_ids: string[]
  updated_at?: string
}

export interface InterestDirection extends ProfileTraitValue {
  label: string
}

export interface LearnerGlobalTraits {
  cognitive_preferences: Record<string, ProfileTraitValue>
  interest_directions: InterestDirection[]
}

export interface ErrorPatternValue {
  severity: number
  confidence: number
  status: 'confirmed' | 'pending' | string
  knowledge_point_ids: string[]
  evidence_ids: string[]
  updated_at?: string
}

export interface TransferAbility {
  level: 'unobserved' | 'recall' | 'near_transfer' | 'far_transfer' | 'integrated_problem_solving' | string
  score: number
  confidence: number
  status: 'confirmed' | 'pending' | 'unobserved' | string
  dimensions: Record<string, number>
  evidence_ids: string[]
  updated_at?: string
}

export interface CourseMasteryPoint {
  name: string
  parent_name?: string
  score: number
  confidence: number
  evidence_count: number
  evidence_ids?: string[]
  recent_scores?: number[]
  updated_at?: string
}

export interface LearnerCourseProfile {
  course_id: string
  course_name: string
  mastery: Record<string, CourseMasteryPoint>
  strong_points: string[]
  weak_points: string[]
  recent_trend: 'improving' | 'declining' | 'stable' | string
  last_classroom_id?: string
  updated_at?: string
  error_patterns?: Record<string, ErrorPatternValue>
  transfer_ability?: TransferAbility
}

export interface LearnerProfileUpdate {
  id: string
  course_id?: string
  course_name?: string
  classroom_id?: string
  type?: string
  scope?: 'global' | 'course' | string
  trait_key?: string
  knowledge_point_id?: string
  knowledge_point_name?: string
  parent_name?: string
  before?: unknown
  after?: unknown
  observed_score?: number
  confidence: number
  reason?: string
  evidence_ids?: string[]
  status: 'pending' | 'accepted' | 'modified' | 'ignored' | string
  created_at?: string
  resolved_at?: string
}

export interface LearnerRecommendation {
  id: string
  type: string
  title: string
  description: string
  priority: string
  knowledge_points: string[]
  reason?: string
  evidence_ids?: string[]
  classroom_id?: string
  course_id?: string
  created_at?: string
}

export interface GenerationStrategy {
  strategy_version: number
  course_id: string
  course_name: string
  explanation_depth: string
  content_style: string[]
  quiz_difficulty: string
  feedback_style: string
  focus_knowledge_points: string[]
  avoid: string[]
  reason: string
  profile_updated_at?: string
  resource_type?: string
  content_strategy?: {
    explanation_depth: string
    preferred_patterns: string[]
    interest_contexts: string[]
    avoid_patterns: string[]
  }
  assessment_strategy?: {
    difficulty: string
    error_targets: string[]
    transfer_level: string
  }
  interaction_strategy?: {
    feedback_style: string
    require_step_hints: boolean
  }
  evidence_ids?: string[]
}

export interface LearnerProfile {
  profile_version: number
  user_id: string
  basic: LearnerProfileBasic
  preferences: LearnerProfilePreferences
  global_traits: LearnerGlobalTraits
  courses: Record<string, LearnerCourseProfile>
  pending_updates: LearnerProfileUpdate[]
  recent_recommendations: LearnerRecommendation[]
  update_history: Array<Record<string, unknown>>
  evidence_buffer: Record<string, Record<string, unknown>>
  created_at: string
  updated_at: string
}

interface LearnerProfileResponse {
  success: boolean
  profile: LearnerProfile
}

export interface ProfileOnboardingMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ProfileOnboardingResult {
  reply: string
  draft: LearnerProfile
  completed: boolean
  current_field: string
  messages: ProfileOnboardingMessage[]
}

export async function getLearnerProfile(): Promise<LearnerProfile> {
  const response = await client.get<LearnerProfileResponse>('/api/learner-profile')
  return response.data.profile
}

export async function saveLearnerProfile(
  profile: LearnerProfile,
): Promise<LearnerProfile> {
  const response = await client.put<LearnerProfileResponse>(
    '/api/learner-profile',
    { profile },
  )
  return response.data.profile
}

export async function sendProfileOnboardingMessage(
  messages: ProfileOnboardingMessage[],
  draft?: LearnerProfile | null,
  llmConfig: {
    content_model?: string
    content_api_key?: string
    content_base_url?: string
    content_provider_type?: string
  } = {},
): Promise<ProfileOnboardingResult> {
  const response = await client.post<ProfileOnboardingResult & { success: boolean }>(
    '/api/learner-profile/onboarding/message',
    { messages, draft: draft || undefined, ...llmConfig },
  )
  return response.data
}

export async function getLearnerGenerationStrategy(
  course: string,
): Promise<GenerationStrategy> {
  const response = await client.get<{
    success: boolean
    generation_strategy: GenerationStrategy
  }>('/api/learner-profile/strategy', { params: { course } })
  return response.data.generation_strategy
}

export async function resolveLearnerProfileUpdate(
  updateId: string,
  action: 'accept' | 'modify' | 'ignore',
  after?: unknown,
): Promise<LearnerProfile> {
  const response = await client.patch<LearnerProfileResponse>(
    `/api/learner-profile/updates/${encodeURIComponent(updateId)}`,
    { action, after },
  )
  return response.data.profile
}
