const CLASSROOM_NOTES_TITLE = '【智慧课堂生成要求】'
const CLASSROOM_LEARNING_CONTEXT_TITLE = '【智慧课堂学习路径上下文】'
const NEXT_LESSON_CONTEXT_TITLE = '【连续课堂上下文】'
const NEXT_LESSON_REQUIREMENTS_TITLE = '【下一堂课生成要求】'

export interface ClassroomLearningContext {
  weakPoints?: string[]
  strongPoints?: string[]
  nextRecommendation?: string
  nextLessonNotes?: string
}

export function stripClassroomPptNotes(notes = '') {
  const starts = [
    CLASSROOM_NOTES_TITLE,
    CLASSROOM_LEARNING_CONTEXT_TITLE,
    NEXT_LESSON_CONTEXT_TITLE,
    NEXT_LESSON_REQUIREMENTS_TITLE,
  ]
    .map((marker) => notes.indexOf(marker))
    .filter((index) => index >= 0)
  const start = starts.length ? Math.min(...starts) : -1
  if (start < 0) return notes.trim()
  return notes.slice(0, start).trim()
}

export function buildClassroomPptNotes(
  existingNotes = '',
  learningContext?: ClassroomLearningContext,
) {
  const baseNotes = stripClassroomPptNotes(existingNotes)
  const contextLines = [
    learningContext?.weakPoints?.length ? `薄弱点：${learningContext.weakPoints.join('、')}` : '',
    learningContext?.strongPoints?.length ? `已掌握：${learningContext.strongPoints.join('、')}` : '',
    learningContext?.nextRecommendation?.trim() ? `下一步建议：${learningContext.nextRecommendation.trim()}` : '',
  ].filter(Boolean)

  const learningNotes = contextLines.length
    ? [CLASSROOM_LEARNING_CONTEXT_TITLE, ...contextLines].join('\n')
    : ''

  const nextLessonNotes = learningContext?.nextLessonNotes?.trim() || ''

  return [baseNotes, learningNotes, nextLessonNotes].filter(Boolean).join('\n\n')
}
