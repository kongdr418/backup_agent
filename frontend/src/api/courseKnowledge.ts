import client from './client'
import { getUserId } from '@/composables/useUserId'

type UnknownRecord = Record<string, unknown>

export interface CourseKnowledgeDocumentSummary {
  id: string
  title: string
  fileName: string
  courseName: string
  summary: string
  createdAt: string
  moduleCount: number
  lessonCount: number
  knowledgePointCount: number
  raw: UnknownRecord
}

export interface CourseKnowledgeCourseSummary {
  id: string
  courseName: string
  documentCount: number
  moduleCount: number
  lessonCount: number
  knowledgePointCount: number
  raw: UnknownRecord
}

export interface UploadCourseKnowledgeResult {
  document: CourseKnowledgeDocumentSummary | null
  courses: CourseKnowledgeCourseSummary[]
}

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' ? value as UnknownRecord : {}
}

function firstString(record: UnknownRecord, keys: string[]): string {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function firstNumber(record: UnknownRecord, keys: string[]): number {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value)
      if (Number.isFinite(parsed)) return parsed
    }
  }
  return 0
}

function nestedRecord(record: UnknownRecord, key: string): UnknownRecord {
  return asRecord(record[key])
}

function normalizeDocument(value: unknown): CourseKnowledgeDocumentSummary | null {
  const record = asRecord(value)
  const title = firstString(record, ['title', 'name', 'document_name', 'document_title'])
  const fileName = firstString(record, [
    'original_filename',
    'file_name',
    'filename',
    'name',
    'title',
  ])
  const courseName = firstString(record, ['course_name', 'course', 'course_title'])
  const id = firstString(record, ['id', 'document_id', 'file_id', 'filename']) || fileName || title

  if (!id && !title && !fileName) return null

  return {
    id,
    title: title || fileName || '未命名资料',
    fileName: fileName || title || '未命名文件',
    courseName: courseName || '未归类课程',
    summary: firstString(record, ['summary', 'abstract', 'description', 'excerpt']),
    createdAt: firstString(record, ['created_at', 'uploaded_at', 'updated_at']),
    moduleCount: firstNumber(record, ['module_count', 'modules_count']),
    lessonCount: firstNumber(record, ['lesson_count', 'lessons_count', 'session_count']),
    knowledgePointCount: firstNumber(record, [
      'knowledge_point_count',
      'knowledge_points_count',
      'concept_count',
    ]),
    raw: record,
  }
}

function normalizeCourse(value: unknown): CourseKnowledgeCourseSummary | null {
  const record = asRecord(value)
  const courseName = firstString(record, ['course_name', 'course', 'name', 'title'])
  const id = firstString(record, ['id', 'course_id', 'name']) || courseName
  if (!id && !courseName) return null

  return {
    id,
    courseName: courseName || '未命名课程',
    documentCount:
      firstNumber(record, ['document_count', 'documents_count', 'material_count']) ||
      firstNumber(nestedRecord(record, 'counts'), ['documents', 'document_count']),
    moduleCount:
      firstNumber(record, ['module_count', 'modules_count']) ||
      firstNumber(nestedRecord(record, 'counts'), ['modules', 'module_count']),
    lessonCount:
      firstNumber(record, ['lesson_count', 'lessons_count', 'session_count']) ||
      firstNumber(nestedRecord(record, 'counts'), ['lessons', 'lesson_count', 'session_count']),
    knowledgePointCount:
      firstNumber(record, ['knowledge_point_count', 'knowledge_points_count', 'concept_count']) ||
      firstNumber(nestedRecord(record, 'counts'), ['knowledge_points', 'knowledge_point_count']),
    raw: record,
  }
}

function normalizeCourseList(value: unknown): CourseKnowledgeCourseSummary[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => normalizeCourse(item))
    .filter((item): item is CourseKnowledgeCourseSummary => Boolean(item))
}

function normalizeDocumentList(value: unknown): CourseKnowledgeDocumentSummary[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => normalizeDocument(item))
    .filter((item): item is CourseKnowledgeDocumentSummary => Boolean(item))
}

export async function uploadCourseKnowledge(file: File): Promise<UploadCourseKnowledgeResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('user_id', getUserId())

  const res = await client.post<{
    success: boolean
    document?: unknown
    course_map?: unknown
  }>('/api/course-knowledge/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 120_000,
  })

  const courseMap = asRecord(res.data.course_map)
  const courses = normalizeCourseList(courseMap.courses ?? courseMap.items)
  const document = normalizeDocument(res.data.document)

  return {
    document,
    courses: courses.length ? courses : normalizeCourseList([courseMap]),
  }
}

export async function listCourseKnowledgeDocuments(): Promise<CourseKnowledgeDocumentSummary[]> {
  const res = await client.get<{
    success: boolean
    items?: unknown[]
  }>('/api/course-knowledge/list')
  return normalizeDocumentList(res.data.items)
}

export async function getCourseKnowledgeCourseMap(): Promise<CourseKnowledgeCourseSummary[]> {
  const res = await client.get<{
    success: boolean
    courses?: unknown[]
  }>('/api/course-knowledge/course-map')
  return normalizeCourseList(res.data.courses)
}

export async function deleteCourseKnowledgeDocument(documentId: string): Promise<void> {
  await client.delete(`/api/course-knowledge/${documentId}`)
}
