import client from './client'

export type MistakeSource = 'manual' | 'classroom'

export interface MistakeAttachment {
  id: string
  name: string
  url: string
  mime: string
  size: number
  uploaded_at: string
}

export interface MistakeItem {
  id: string
  source: MistakeSource | string
  source_evidence_id?: string | null
  source_ref?: { classroom_id?: string; question_id?: string }
  course_id: string
  course_name: string
  knowledge_point_id?: string | null
  knowledge_point_name: string
  stem: string
  question_type?: 'single' | 'multiple' | 'short_answer' | null
  options?: string[] | null
  correct_answer: string
  user_answer?: string | null
  analysis: string
  tags: string[]
  collection_ids: string[]
  attachments: MistakeAttachment[]
  mastered: boolean
  review_count: number
  first_added_at: string
  last_reviewed_at?: string | null
  mastered_at?: string | null
  updated_at: string
}

export interface SM2State {
  repetitions: number
  ease_factor: number
  interval_days: number
  due_date: string
  last_grade: number | null
}

export type FlashcardSource = 'card' | 'mistake' | 'manual' | 'ai'

export interface FlashcardItem {
  id: string
  source: FlashcardSource | string
  source_id?: string | null
  front: string
  back: string
  course_id: string
  course_name: string
  knowledge_point_id?: string | null
  knowledge_point_name: string
  tags: string[]
  sm2: SM2State
  suspended: boolean
  created_at: string
  last_reviewed_at?: string | null
  updated_at: string
}

export interface PagedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface StatsResult {
  mistakes: {
    total: number
    mastered: number
    unmastered: number
    top_knowledge_points: { name: string; count: number }[]
  }
  flashcards: {
    total: number
    due_today: number
    mastered: number
    streak_days: number
  }
}

// ─── 错题本 ───

export interface ListMistakesParams {
  course_id?: string
  knowledge_point_id?: string
  mastered?: boolean
  source?: string
  collection_id?: string
  q?: string
  page?: number
  page_size?: number
}

export async function listMistakes(params: ListMistakesParams = {}): Promise<PagedResult<MistakeItem>> {
  const res = await client.get<{ success: boolean } & PagedResult<MistakeItem>>(
    '/api/study-tools/mistakes',
    { params },
  )
  return { items: res.data.items, total: res.data.total, page: res.data.page, page_size: res.data.page_size }
}

export async function addMistake(payload: Partial<MistakeItem>): Promise<MistakeItem> {
  const res = await client.post<{ success: boolean; item: MistakeItem }>(
    '/api/study-tools/mistakes',
    payload,
  )
  return res.data.item
}

export async function addMistakeWithFiles(
  payload: Partial<MistakeItem>,
  files: File[],
): Promise<MistakeItem> {
  const form = new FormData()
  form.append('payload', JSON.stringify(payload))
  for (const f of files) form.append('files', f, f.name)
  const res = await client.post<{ success: boolean; item: MistakeItem }>(
    '/api/study-tools/mistakes',
    form,
  )
  return res.data.item
}

export async function uploadMistakeAttachments(
  mistakeId: string,
  files: File[],
): Promise<{ saved: MistakeAttachment[]; rejected: string[]; item: MistakeItem }> {
  const form = new FormData()
  for (const f of files) form.append('files', f, f.name)
  const res = await client.post<{
    success: boolean
    saved: MistakeAttachment[]
    rejected: string[]
    item: MistakeItem
  }>(`/api/study-tools/mistakes/${mistakeId}/attachments`, form)
  return { saved: res.data.saved, rejected: res.data.rejected, item: res.data.item }
}

export async function deleteMistakeAttachment(
  mistakeId: string,
  attachmentId: string,
): Promise<MistakeItem> {
  const res = await client.delete<{ success: boolean; item: MistakeItem }>(
    `/api/study-tools/mistakes/${mistakeId}/attachments/${attachmentId}`,
  )
  return res.data.item
}

export async function bulkAddMistakes(items: Partial<MistakeItem>[]) {
  const res = await client.post<{ success: boolean; added: MistakeItem[]; added_count: number; deduped_count: number }>(
    '/api/study-tools/mistakes/bulk',
    { items },
  )
  return { added: res.data.added, addedCount: res.data.added_count, dedupedCount: res.data.deduped_count }
}

export async function getMistake(id: string): Promise<MistakeItem> {
  const res = await client.get<{ success: boolean; item: MistakeItem }>(`/api/study-tools/mistakes/${id}`)
  return res.data.item
}

export async function updateMistake(id: string, patch: Partial<MistakeItem>): Promise<MistakeItem> {
  const res = await client.patch<{ success: boolean; item: MistakeItem }>(
    `/api/study-tools/mistakes/${id}`,
    patch,
  )
  return res.data.item
}

export async function deleteMistake(id: string): Promise<void> {
  await client.delete(`/api/study-tools/mistakes/${id}`)
}

export async function mistakeToFlashcard(id: string): Promise<FlashcardItem> {
  const res = await client.post<{ success: boolean; item: FlashcardItem }>(
    `/api/study-tools/mistakes/${id}/to-flashcard`,
    {},
  )
  return res.data.item
}

// ─── 闪卡 ───

export interface ListFlashcardsParams {
  course_id?: string
  knowledge_point_id?: string
  source?: string
  suspended?: boolean
  q?: string
  page?: number
  page_size?: number
}

export async function listFlashcards(params: ListFlashcardsParams = {}): Promise<PagedResult<FlashcardItem>> {
  const res = await client.get<{ success: boolean } & PagedResult<FlashcardItem>>(
    '/api/study-tools/flashcards',
    { params },
  )
  return { items: res.data.items, total: res.data.total, page: res.data.page, page_size: res.data.page_size }
}

export async function addFlashcard(payload: Partial<FlashcardItem>): Promise<FlashcardItem> {
  const res = await client.post<{ success: boolean; item: FlashcardItem }>(
    '/api/study-tools/flashcards',
    payload,
  )
  return res.data.item
}

export async function listDueFlashcards(limit = 50): Promise<FlashcardItem[]> {
  const res = await client.get<{ success: boolean; items: FlashcardItem[]; total: number }>(
    '/api/study-tools/flashcards/due',
    { params: { limit } },
  )
  return res.data.items
}

export async function updateFlashcard(id: string, patch: Partial<FlashcardItem>): Promise<FlashcardItem> {
  const res = await client.patch<{ success: boolean; item: FlashcardItem }>(
    `/api/study-tools/flashcards/${id}`,
    patch,
  )
  return res.data.item
}

export async function deleteFlashcard(id: string): Promise<void> {
  await client.delete(`/api/study-tools/flashcards/${id}`)
}

export async function reviewFlashcard(id: string, grade: number): Promise<FlashcardItem> {
  const res = await client.post<{ success: boolean; item: FlashcardItem }>(
    `/api/study-tools/flashcards/${id}/review`,
    { grade },
  )
  return res.data.item
}

// ─── 统计 ───

export async function getStats(): Promise<StatsResult> {
  const res = await client.get<{ success: boolean } & StatsResult>('/api/study-tools/stats')
  return { mistakes: res.data.mistakes, flashcards: res.data.flashcards }
}

// ─── 错题集(用户自定义分类) ───

export interface MistakeCollection {
  id: string
  name: string
  created_at: string
  updated_at: string
  count: number
  unmastered_count: number
}

export async function listCollections(): Promise<MistakeCollection[]> {
  const res = await client.get<{ success: boolean; items: MistakeCollection[]; total: number }>(
    '/api/study-tools/mistake-collections',
  )
  return res.data.items
}

export async function createCollection(name: string, mistakeIds: string[] = []): Promise<MistakeCollection> {
  const res = await client.post<{ success: boolean; item: MistakeCollection }>(
    '/api/study-tools/mistake-collections',
    { name, mistake_ids: mistakeIds },
  )
  return res.data.item
}

export async function renameCollection(id: string, name: string): Promise<MistakeCollection> {
  const res = await client.patch<{ success: boolean; item: MistakeCollection }>(
    `/api/study-tools/mistake-collections/${id}`,
    { name },
  )
  return res.data.item
}

export async function deleteCollection(id: string): Promise<void> {
  await client.delete(`/api/study-tools/mistake-collections/${id}`)
}

export async function addMistakesToCollection(
  collectionId: string,
  mistakeIds: string[],
): Promise<{ added: number; not_found: string[] }> {
  const res = await client.post<{ success: boolean; added: number; not_found: string[] }>(
    `/api/study-tools/mistake-collections/${collectionId}/mistakes`,
    { mistake_ids: mistakeIds },
  )
  return { added: res.data.added, not_found: res.data.not_found }
}

export async function removeMistakeFromCollection(
  collectionId: string,
  mistakeId: string,
): Promise<void> {
  await client.delete(`/api/study-tools/mistake-collections/${collectionId}/mistakes/${mistakeId}`)
}
