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
}

export interface LearnerProfileUpdate {
  id: string
  course_id?: string
  course_name?: string
  classroom_id?: string
  type?: string
  knowledge_point_id?: string
  knowledge_point_name?: string
  parent_name?: string
  before?: number
  after?: number
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
}

export interface LearnerProfile {
  profile_version: number
  user_id: string
  basic: LearnerProfileBasic
  preferences: LearnerProfilePreferences
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
  after?: number,
): Promise<LearnerProfile> {
  const response = await client.patch<LearnerProfileResponse>(
    `/api/learner-profile/updates/${encodeURIComponent(updateId)}`,
    { action, after },
  )
  return response.data.profile
}
