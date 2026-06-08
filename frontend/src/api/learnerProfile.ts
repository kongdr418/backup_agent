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

export interface LearnerProfile {
  profile_version: number
  user_id: string
  basic: LearnerProfileBasic
  preferences: LearnerProfilePreferences
  courses: Record<string, unknown>
  pending_updates: unknown[]
  recent_recommendations: unknown[]
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
