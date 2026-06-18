const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

const INTERNAL_TAG_LABELS: Record<string, string> = {
  classroom: '课堂同步',
  'interactive-classroom': '互动课堂',
  interactive_classroom: '互动课堂',
  manual: '手动添加',
  mistake: '错题复习',
  card: '闪卡复习',
  ai: 'AI 生成',
}

export function formatMistakeSourceLabel(source: unknown): string {
  const value = String(source || '').trim().toLowerCase()
  if (value === 'classroom') return '课堂同步'
  if (value === 'manual') return '手动添加'
  if (value === 'mistake') return '错题复习'
  if (value === 'card') return '闪卡复习'
  if (value === 'ai') return 'AI 生成'
  return '学习记录'
}

export function formatMistakeTagLabel(tag: unknown): string {
  const raw = String(tag || '').trim()
  if (!raw) return ''
  const key = raw.replace(/^#/, '').trim().toLowerCase()
  return INTERNAL_TAG_LABELS[key] || key.replace(/[_-]+/g, ' ')
}

export function getChoiceLetter(label: unknown, index: number): string {
  const text = String(label || '').trim()
  const match = text.match(/^\(?([A-Ha-h])[\).、\s]/)
  if (match) return match[1].toUpperCase()
  return OPTION_LETTERS[index] || String(index + 1)
}

export function getChoiceText(label: unknown, index: number): string {
  const text = String(label || '').trim()
  const letter = getChoiceLetter(text, index)
  const escaped = letter.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const stripped = text.replace(new RegExp(`^\\(?${escaped}[\\).、\\s]+`, 'i'), '').trim()
  return stripped || text
}
