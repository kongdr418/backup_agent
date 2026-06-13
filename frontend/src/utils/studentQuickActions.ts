export interface StudentQuickAction {
  label: string
  prompt: string
  icon: 'exercise' | 'quiz' | 'card' | 'mindmap' | 'graphic'
  supportsDocx: boolean
}

export const STUDENT_QUICK_ACTIONS: StudentQuickAction[] = [
  { label: '习题集', prompt: '习题集：', icon: 'exercise', supportsDocx: true },
  { label: '课堂测验', prompt: '课堂测验：', icon: 'quiz', supportsDocx: true },
  { label: '知识卡片', prompt: '知识卡片：', icon: 'card', supportsDocx: true },
  { label: '思维导图', prompt: '思维导图：', icon: 'mindmap', supportsDocx: false },
  { label: '图文', prompt: '生成图文：', icon: 'graphic', supportsDocx: false },
]
