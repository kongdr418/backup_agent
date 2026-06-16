import type { LearnerProfile } from '@/api/learnerProfile'
import type { ChatMessage, Session } from '@/types'

export const PROFILE_ONBOARDING_SESSION_KIND = 'profile_onboarding' as const
export const PROFILE_ONBOARDING_SESSION_NAME = '建立我的学习画像'

export interface ProfileOnboardingState {
  draft: LearnerProfile
  completed: boolean
  currentField: string
  confirmed: boolean
}

export function needsProfileOnboarding(profile: LearnerProfile): boolean {
  return !(
    profile.basic.learning_stage
    && profile.basic.learning_basis
    && profile.basic.background
    && profile.preferences.goal
    && profile.preferences.content_style.length
    && profile.preferences.preferred_difficulty
    && profile.preferences.tutoring_style
    && profile.global_traits.interest_directions.length
  )
}

export function findProfileOnboardingSession(sessions: Session[]): Session | undefined {
  return sessions.find((session) => session.kind === PROFILE_ONBOARDING_SESSION_KIND)
}

export function getProfileOnboardingState(
  messages: ChatMessage[],
): ProfileOnboardingState | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const raw = messages[index].data?.profileOnboarding
    if (!raw || typeof raw !== 'object') continue
    const state = raw as Partial<ProfileOnboardingState>
    if (!state.draft) continue
    return {
      draft: state.draft,
      completed: Boolean(state.completed),
      currentField: state.currentField || '',
      confirmed: Boolean(state.confirmed),
    }
  }
  return null
}

export function reopenProfileOnboardingState(
  state: ProfileOnboardingState,
): ProfileOnboardingState {
  return {
    ...state,
    completed: false,
    confirmed: false,
  }
}
