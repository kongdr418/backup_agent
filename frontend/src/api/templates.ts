import client from './client'

export interface TemplateItem {
  template_id: string
  label: string
  summary: string
  tone: string
  theme_mode: string
  category: string
  keywords: string[]
  slide_count: number
}

export async function listTemplates(): Promise<TemplateItem[]> {
  const res = await client.get('/api/templates/list')
  return res.data.templates || []
}

export interface TemplatePreview {
  pages: Record<string, string>
  label: string
  pageOrder: string[]
}

const PAGE_LABELS: Record<string, string> = {
  cover: '封面',
  toc: '目录',
  chapter: '章节',
  content: '内页',
  ending: '结尾',
}

export async function fetchTemplatePreview(templateId: string): Promise<TemplatePreview> {
  const res = await client.get(`/api/templates/preview/${templateId}`)
  const pages: Record<string, string> = res.data.pages || {}
  const pageOrder = ['cover', 'toc', 'chapter', 'content', 'ending'].filter((k) => pages[k])
  return {
    pages,
    label: res.data.label || '',
    pageOrder,
    getLabel: (key: string) => PAGE_LABELS[key] || key,
  } as TemplatePreview
}
