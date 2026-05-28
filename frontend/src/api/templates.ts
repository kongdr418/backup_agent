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
