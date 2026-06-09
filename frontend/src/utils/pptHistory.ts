const PPT_STYLE_LABELS: Record<string, string> = {
  general: '通用',
  education: '教育',
  academic: '学术',
  business: '商务',
  minimal: '简约',
}

export function formatPptJobCreatedAt(value: string): string {
  const match = value.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/)
  if (!match) return value
  const [, year, month, day, hour, minute] = match
  return `${year}-${month}-${day} ${hour}:${minute}`
}

export function getPptStyleLabel(style?: string): string {
  if (!style) return ''
  return PPT_STYLE_LABELS[style] || style
}
