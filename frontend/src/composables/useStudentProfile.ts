import { ref, watch } from 'vue'
import type { StudentProfile } from '@/api/interactiveClassroom'

const STORAGE_KEY = 'ai_creator.student_profile'

export const DEFAULT_STUDENT_PROFILE: Required<StudentProfile> = {
  basis: '零基础',
  goal: '考试通过',
  style: '图解+案例',
  difficulty: '基础',
}

function normalizeProfile(value: unknown): Required<StudentProfile> {
  const row = typeof value === 'object' && value !== null ? value as StudentProfile : {}
  return {
    basis: row.basis || DEFAULT_STUDENT_PROFILE.basis,
    goal: row.goal || DEFAULT_STUDENT_PROFILE.goal,
    style: row.style || DEFAULT_STUDENT_PROFILE.style,
    difficulty: row.difficulty || DEFAULT_STUDENT_PROFILE.difficulty,
  }
}

function loadProfile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return normalizeProfile(raw ? JSON.parse(raw) : null)
  } catch {
    return { ...DEFAULT_STUDENT_PROFILE }
  }
}

export function useStudentProfile() {
  const profile = ref<Required<StudentProfile>>(loadProfile())

  function saveProfile() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile.value))
  }

  function resetProfile() {
    profile.value = { ...DEFAULT_STUDENT_PROFILE }
    saveProfile()
  }

  watch(profile, saveProfile, { deep: true })

  return {
    profile,
    resetProfile,
  }
}
