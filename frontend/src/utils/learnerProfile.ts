import type { StudentProfile } from '@/api/interactiveClassroom'
import type { LearnerProfile } from '@/api/learnerProfile'

export const LEGACY_PROFILE_STORAGE_KEY = 'ai_creator.student_profile'
export const UNIVERSITY_STAGE_VALUES = [
  '大一',
  '大二',
  '大三',
  '大四',
  '专升本',
  '硕士研究生',
  '博士研究生',
] as const

export function createEmptyLearnerProfile(userId = ''): LearnerProfile {
  return {
    profile_version: 1,
    user_id: userId,
    basic: {
      display_name: '',
      learning_stage: '',
      learning_basis: '',
      background: '',
    },
    preferences: {
      goal: '',
      content_style: [],
      preferred_difficulty: '',
      tutoring_style: '',
    },
    courses: {},
    pending_updates: [],
    recent_recommendations: [],
    created_at: '',
    updated_at: '',
  }
}

function hasText(value: unknown): boolean {
  return typeof value === 'string' && value.trim().length > 0
}

export function shouldMigrateLegacyProfile(
  profile: LearnerProfile,
  legacy: StudentProfile | null,
): boolean {
  if (!legacy || !Object.values(legacy).some(hasText)) return false
  return ![
    profile.basic.display_name,
    profile.basic.learning_stage,
    profile.basic.learning_basis,
    profile.basic.background,
    profile.preferences.goal,
    profile.preferences.preferred_difficulty,
    profile.preferences.tutoring_style,
    ...profile.preferences.content_style,
  ].some(hasText)
}

export function mergeLegacyStudentProfile(
  profile: LearnerProfile,
  legacy: StudentProfile,
): LearnerProfile {
  return {
    ...profile,
    basic: {
      ...profile.basic,
      learning_basis: legacy.basis?.trim() || profile.basic.learning_basis,
    },
    preferences: {
      ...profile.preferences,
      goal: legacy.goal?.trim() || profile.preferences.goal,
      content_style: legacy.style
        ? legacy.style.split(/[+，、/|]/).map((item) => item.trim()).filter(Boolean)
        : profile.preferences.content_style,
      preferred_difficulty:
        legacy.difficulty?.trim() || profile.preferences.preferred_difficulty,
    },
  }
}

export function toLegacyStudentProfile(profile: LearnerProfile): Required<StudentProfile> {
  return {
    basis: profile.basic.learning_basis || '零基础',
    goal: profile.preferences.goal || '考试通过',
    style: profile.preferences.content_style.join('+') || '图解+案例',
    difficulty: profile.preferences.preferred_difficulty || '基础',
  }
}

export function readLegacyStudentProfile(storage: Storage): StudentProfile | null {
  try {
    const raw = storage.getItem(LEGACY_PROFILE_STORAGE_KEY)
    if (!raw) return null
    const value = JSON.parse(raw)
    return typeof value === 'object' && value !== null ? value as StudentProfile : null
  } catch {
    return null
  }
}

export function writeLegacyStudentProfile(storage: Storage, profile: LearnerProfile): void {
  storage.setItem(
    LEGACY_PROFILE_STORAGE_KEY,
    JSON.stringify(toLegacyStudentProfile(profile)),
  )
}
