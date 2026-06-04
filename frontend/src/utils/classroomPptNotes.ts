export interface ClassroomLearnerProfile {
  basis?: string
  goal?: string
  style?: string
  difficulty?: string
}

const CLASSROOM_NOTES_TITLE = '【智慧课堂生成要求】'
const CLASSROOM_LEARNING_CONTEXT_TITLE = '【智慧课堂学习路径上下文】'

export interface ClassroomLearningContext {
  weakPoints?: string[]
  strongPoints?: string[]
  nextRecommendation?: string
}

const PROFILE_FIELDS: Array<{
  key: keyof ClassroomLearnerProfile
  label: string
}> = [
  { key: 'basis', label: '学习基础' },
  { key: 'goal', label: '学习目标' },
  { key: 'style', label: '讲解偏好' },
  { key: 'difficulty', label: '题目难度' },
]

export function stripClassroomPptNotes(notes = '') {
  const start = notes.indexOf(CLASSROOM_NOTES_TITLE)
  if (start < 0) return notes.trim()
  return notes.slice(0, start).trim()
}

export function buildClassroomPptNotes(
  profile: ClassroomLearnerProfile,
  existingNotes = '',
  learningContext?: ClassroomLearningContext,
) {
  const lines = PROFILE_FIELDS
    .map(({ key, label }) => {
      const value = profile[key]?.trim()
      return value ? `${label}：${value}` : ''
    })
    .filter(Boolean)

  const baseNotes = stripClassroomPptNotes(existingNotes)
  if (!lines.length) return baseNotes

  const classroomNotes = [
    CLASSROOM_NOTES_TITLE,
    ...lines,
    '请据此适配 PPT 内容组织、案例选择、解释深度和课堂互动题；画像仅作为生成策略，不要机械堆砌到学生可见文本中。',
  ].join('\n')

  const contextLines = [
    learningContext?.weakPoints?.length ? `薄弱点：${learningContext.weakPoints.join('、')}` : '',
    learningContext?.strongPoints?.length ? `已掌握：${learningContext.strongPoints.join('、')}` : '',
    learningContext?.nextRecommendation?.trim() ? `下一步建议：${learningContext.nextRecommendation.trim()}` : '',
  ].filter(Boolean)

  const learningNotes = contextLines.length
    ? [CLASSROOM_LEARNING_CONTEXT_TITLE, ...contextLines].join('\n')
    : ''

  return [baseNotes, classroomNotes, learningNotes].filter(Boolean).join('\n\n')
}
