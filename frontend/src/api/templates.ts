import client from './client'

export interface TemplateImportResult {
  success: boolean
  import_id?: string
  template_id?: string
  status?: string
  stage?: string
  progress?: number
  message?: string
  slide_count?: number
  export_mode?: string
  review_required?: boolean
  steps?: Record<string, unknown>
  error?: string
}

export interface TemplateReview {
  success: boolean
  import_id?: string
  pages?: Array<{
    page_type: string
    title?: string
    svg_filename?: string
    placeholder_tokens?: string[]
  }>
  error?: string
}

export interface TemplateItem {
  template_id: string
  label: string
  created_at: string
  slide_count: number
  page_types?: string[]
}

export interface TemplateListResponse {
  success: boolean
  templates: TemplateItem[]
}

export async function uploadTemplate(file: File, label?: string): Promise<TemplateImportResult> {
  const form = new FormData()
  form.append('file', file)
  if (label) form.append('label', label)
  const res = await client.post<TemplateImportResult>('/api/templates/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  })
  return res.data
}

export async function getImportStatus(importId: string): Promise<TemplateImportResult> {
  const res = await client.get<TemplateImportResult>(`/api/templates/import/${importId}`)
  return res.data
}

export async function getImportReview(importId: string): Promise<TemplateReview> {
  const res = await client.get<TemplateReview>(`/api/templates/import/${importId}/review`)
  return res.data
}

export async function updateImportReview(importId: string, data: Record<string, unknown>): Promise<TemplateReview> {
  const res = await client.put<TemplateReview>(`/api/templates/import/${importId}/review`, data)
  return res.data
}

export async function requestAssist(importId: string, feedback?: string) {
  const res = await client.post(`/api/templates/import/${importId}/assist`, { feedback })
  return res.data
}

export async function submitFeedback(importId: string, feedback: string) {
  const res = await client.post(`/api/templates/import/${importId}/feedback`, { feedback })
  return res.data
}

export async function confirmImport(importId: string) {
  const res = await client.post(`/api/templates/import/${importId}/confirm`)
  return res.data
}

export async function listTemplates(): Promise<TemplateItem[]> {
  const res = await client.get<TemplateListResponse>('/api/templates/list')
  return res.data.templates || []
}

export async function deleteTemplate(templateId: string) {
  await client.delete(`/api/templates/${templateId}`)
}
