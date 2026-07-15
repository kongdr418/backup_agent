import client from './client'

export type ResearchSample = Record<string, unknown> & {
  research_user_id?: string
  research_label?: string
  output_id: string
  learner_id: string
  source: string
  task_id: string
  prompt: string
  response: string
  timestamp: string
  severity?: string
}

export interface ResearchAnnotation extends Record<string, unknown> {
  annotation_id?: string
  output_id_or_replay_id?: string
  output_id?: string
  annotator?: string
  created_at?: string
  model_version?: string
  provider_type?: string
  a_memory_failure_type: string
  b_pedagogical_boundary_type: string
  c_compliance_flag: string
  severity: string
  cannot_judge_reason: string
  relation_between_a_and_b: string
  evidence_span: string
  memory_ids: string[]
  memory_evidence: string
  current_task_or_code_evidence: string
  rationale: string
  teacher_review_needed: boolean
  suggested_correction: string
}

export type ResearchAnnotationRecord = ResearchAnnotation

export async function listResearchSamples(limit = 100, source = '') {
  const res = await client.get<{ success: boolean; samples: ResearchSample[] }>('/api/research/samples', {
    params: { limit, source },
  })
  return res.data.samples
}

export async function aiAnnotateResearchSample(outputId: string, body: Record<string, unknown> = {}) {
  const res = await client.post<{ success: boolean; annotation: ResearchAnnotation }>(
    `/api/research/samples/${encodeURIComponent(outputId)}/ai-annotate`,
    body,
  )
  return res.data.annotation
}

export async function listAiResearchAnnotations() {
  const res = await client.get<{ success: boolean; annotations: ResearchAnnotationRecord[] }>('/api/research/annotations/ai')
  return res.data.annotations
}

export async function listFinalResearchAnnotations() {
  const res = await client.get<{ success: boolean; annotations: ResearchAnnotationRecord[] }>('/api/research/annotations/final')
  return res.data.annotations
}

export async function saveFinalResearchAnnotation(outputId: string, annotation: ResearchAnnotation) {
  const res = await client.post<{ success: boolean; annotation: ResearchAnnotation }>(
    `/api/research/samples/${encodeURIComponent(outputId)}/final-annotation`,
    annotation,
  )
  return res.data.annotation
}

export function researchExportUrl(format: 'csv' | 'json' = 'csv') {
  return `/api/research/export?format=${encodeURIComponent(format)}`
}
