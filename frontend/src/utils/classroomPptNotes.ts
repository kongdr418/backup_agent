const CLASSROOM_NOTES_TITLE = '【智慧课堂生成要求】'
const CLASSROOM_LEARNING_CONTEXT_TITLE = '【智慧课堂学习路径上下文】'

export interface ClassroomLearningContext {
  weakPoints?: string[]
  strongPoints?: string[]
  nextRecommendation?: string
}

export function stripClassroomPptNotes(notes = '') {
  const start = notes.indexOf(CLASSROOM_NOTES_TITLE)
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

  return [baseNotes, learningNotes].filter(Boolean).join('\n\n')
}
