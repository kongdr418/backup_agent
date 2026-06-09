export interface StoredNextLessonDraft {
  topic?: string
  course?: string
  weakPoints?: string[]
  strongPoints?: string[]
  nextRecommendation?: string
  nextLessonNotes?: string
  courseRootId?: string
  parentClassroomId?: string
  lessonDepth?: number
  lessonIndex?: number
  lessonKind?: string
}

const STORAGE_KEY = 'ai_creator.classroom.next_lesson_draft'

export function saveNextLessonDraft(draft: StoredNextLessonDraft): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
}

export function loadNextLessonDraft(): StoredNextLessonDraft | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function clearNextLessonDraft(): void {
  sessionStorage.removeItem(STORAGE_KEY)
}
