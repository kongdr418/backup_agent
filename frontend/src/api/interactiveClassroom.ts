import client from './client'
import { sseFetch } from './sse'
import type { SseEvent } from '@/types'

export interface InteractiveClassroomGenerateRequest {
  topic: string
  request_id?: string
  course?: string
  ppt_job_id?: string
  student_profile?: StudentProfile
  tts_provider?: string
  tts_model?: string
  tts_voice?: string
  tts_api_key?: string
  tts_base_url?: string
  content_model?: string
  content_api_key?: string
  content_base_url?: string
  content_provider_type?: string
  signal?: AbortSignal
}

export interface StudentProfile {
  basis?: string
  goal?: string
  style?: string
  difficulty?: string
}

export interface InteractiveClassroomListItem {
  id: string
  title: string
  topic: string
  course?: string
  scene_count: number
  created_at: string
}

export interface InteractiveClassroomAction {
  id: string
  type: string
  agent_id: string
  text?: string
  audio_url?: string
  payload?: Record<string, unknown>
}

export interface HighlightTarget {
  id: string
  text: string
  kind?: string
  bbox: {
    x: number
    y: number
    width: number
    height: number
  }
}

export interface HighlightCue {
  target_id: string
  start_ratio: number
  end_ratio: number
  mode?: 'outline' | 'spotlight' | string
  label?: string
}

export interface InteractiveClassroomQuestion {
  id: string
  type: 'single' | 'multiple' | 'short_answer' | string
  question: string
  options: Array<{ label: string; value: string }>
  answer?: string[]
  analysis?: string
  points?: number
  knowledge_point?: string
  // P1-3: 简答题专属字段
  reference_answer?: string
  rubric?: string[]
}

export interface InteractiveClassroomScene {
  id: string
  type: 'slide' | 'quiz' | 'summary' | string
  title: string
  order: number
  knowledge_points?: string[]
  content: Record<string, unknown>
  actions: InteractiveClassroomAction[]
}

export interface InteractiveClassroomPayload {
  id: string
  title: string
  topic: string
  course?: string
  status: string
  student_profile?: StudentProfile
  generation_strategy?: Record<string, unknown>
  source?: Record<string, unknown>
  scenes: InteractiveClassroomScene[]
  answers_record?: {
    scenes?: Record<string, {
      answers?: Record<string, string[]>
      evaluation?: Omit<QuizSubmitResult, 'success' | 'feedback_action'>
    }>
  }
}

export interface InteractiveClassroomGenerationStatus {
  request_id: string
  topic?: string
  status: 'running' | 'cancelling' | 'cancelled' | 'done' | 'error' | string
  started_at?: string
  updated_at?: string
  classroom_id?: string
  classroom?: InteractiveClassroomPayload
  error?: string
}

export interface QuizSubmitResult {
  success: boolean
  score: number
  correct: number
  total: number
  earned_points: number
  total_points: number
  results: Array<{
    question_id: string
    correct: boolean
    your_answer: string[]
    correct_answer: string[]
    analysis?: string
    // P1-3: 简答题专属
    score?: number         // 0-100，仅 short_answer 有
    feedback?: string      // LLM 评语，仅 short_answer 有
    earned_points?: number // 简答题按 (score/100)*points 折算
    covered_points?: string[] // LLM 评出的"学生答到的要点"
    knowledge_point?: string
    points?: number
  }>
  feedback_action?: InteractiveClassroomAction
}

export interface ClassroomRecommendedTask {
  id: string
  type: string
  title: string
  description: string
  priority: 'high' | 'medium' | 'low' | string
  knowledge_points: string[]
  target_scene_ids: string[]
  action_label: string
  reason?: string
  evidence_ids?: string[]
}

export interface ClassroomReport {
  classroom_id: string
  title: string
  topic: string
  status: 'not_started' | 'needs_review' | 'completed' | string
  score: number
  correct: number
  total: number
  earned_points: number
  total_points: number
  quiz_scene_count: number
  answered_quiz_count: number
  answered_scene_ids: string[]
  learned_points: string[]
  knowledge_summary: Record<string, {
    correct: number
    total: number
    earned_points: number
    total_points: number
    mastery: number
    event_ids?: string[]
  }>
  weak_points: string[]
  strong_points: string[]
  next_recommendation: string
  recommended_tasks?: ClassroomRecommendedTask[]
  event_count?: number
  course_trend?: string
  profile_update_count?: number
  profile_update_ids?: string[]
}

export interface ClassroomDiscussionMessage {
  role: 'assistant' | 'user'
  content: string
  trigger?: string
  agent_id?: string
  agent_name?: string
  message_id?: string
  pending?: boolean
}

export interface ClassroomDiscussionResponse {
  success: boolean
  assistant_message: ClassroomDiscussionMessage
  assistant_messages?: ClassroomDiscussionMessage[]
  auto_advance_paused: boolean
}

export async function generateInteractiveClassroom(body: InteractiveClassroomGenerateRequest) {
  const { signal, ...payload } = body
  const res = await client.post<{
    success: boolean
    classroom_id: string
    status: string
    classroom: InteractiveClassroomPayload
  }>('/api/interactive-classroom/generate', payload, {
    timeout: 600_000,
    signal,
  })
  return res.data
}

export async function startInteractiveClassroomGeneration(body: InteractiveClassroomGenerateRequest) {
  const { signal, ...payload } = body
  const res = await client.post<{
    success: boolean
    request_id: string
    status: string
    job: InteractiveClassroomGenerationStatus
  }>('/api/interactive-classroom/generate', payload, {
    timeout: 30_000,
    signal,
  })
  return res.data
}

export async function getInteractiveClassroomGenerationStatus(requestId: string) {
  const res = await client.get<{
    success: boolean
    job: InteractiveClassroomGenerationStatus
  }>(`/api/interactive-classroom/generate/status/${encodeURIComponent(requestId)}`, {
    timeout: 10_000,
  })
  return res.data.job
}

export async function cancelInteractiveClassroomGeneration(requestId: string) {
  const res = await client.post<{ success: boolean; cancelled: boolean }>(
    '/api/interactive-classroom/generate/cancel',
    { request_id: requestId },
    { timeout: 10_000 },
  )
  return res.data
}

export async function listInteractiveClassrooms() {
  const res = await client.get<{ classrooms: InteractiveClassroomListItem[] }>('/api/interactive-classroom/list')
  return res.data.classrooms || []
}

export async function getInteractiveClassroom(classroomId: string) {
  const res = await client.get<{ success: boolean; classroom: InteractiveClassroomPayload }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}`,
  )
  return res.data.classroom
}

export async function renameInteractiveClassroom(classroomId: string, title: string) {
  const res = await client.patch<{ success: boolean; classroom: InteractiveClassroomPayload }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}`,
    { title },
  )
  return res.data.classroom
}

export async function deleteInteractiveClassroom(classroomId: string) {
  const res = await client.delete<{ success: boolean }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}`,
  )
  return res.data
}

export async function submitInteractiveClassroomAnswer(
  classroomId: string,
  sceneId: string,
  answers: Record<string, string[]>,
  config?: {
    tts_provider?: string
    tts_model?: string
    tts_voice?: string
    tts_api_key?: string
    tts_base_url?: string
    // P1-3: 简答题 LLM 评分所需
    content_model?: string
    content_api_key?: string
    content_base_url?: string
    content_provider_type?: string
  },
) {
  const res = await client.post<QuizSubmitResult>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/answer`,
    {
      scene_id: sceneId,
      answers,
      ...(config ?? {}),
    },
  )
  return res.data
}

export async function getInteractiveClassroomReport(classroomId: string) {
  const res = await client.get<{ success: boolean; report: ClassroomReport }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/report`,
  )
  return res.data.report
}

export async function discussInteractiveClassroom(
  classroomId: string,
  body: {
    played_scene_ids: string[]
    current_scene_id?: string
    messages: ClassroomDiscussionMessage[]
    trigger?: string
    quick_action?: string
    multi_agent?: boolean
    content_model?: string
    content_api_key?: string
    content_base_url?: string
    content_provider_type?: string
  },
) {
  const res = await client.post<ClassroomDiscussionResponse>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/discuss`,
    body,
  )
  return res.data
}

export type DiscussRequest = Parameters<typeof discussInteractiveClassroom>[1]

/**
 * 流式讨论 — 与对话页 chatStream 走同样的 sseFetch 工具，
 * 事件格式 data: {"chunk": "..."} ... data: {"done": true}。
 */
export async function* discussInteractiveClassroomStream(
  classroomId: string,
  body: DiscussRequest,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent, void, void> {
  yield* sseFetch({
    url: `/api/interactive-classroom/${encodeURIComponent(classroomId)}/discuss/stream`,
    method: 'POST',
    body,
    signal,
  })
}

// ---------- SSE 流式生成进度 ----------

export type ClassroomStreamEvent =
  | {
      type: 'classroom_start'
      request_id: string
      topic: string
      stages: string[]
      stage_total: number
      stage_labels: Record<string, string>
      scene_total: number
    }
  | {
      type: 'classroom_progress'
      request_id: string
      stage: string
      stage_index: number
      stage_total: number
      stage_label: string
      scene_index: number
      scene_total: number
      scene?: { id: string; type: string; title: string; order: number }
    }
  | {
      type: 'classroom_done'
      request_id: string
      classroom_id: string
      scene_count: number
    }
  | { type: 'classroom_cancelled'; request_id: string }
  | { type: 'classroom_error'; request_id: string; error: string }

export function isClassroomTerminalEvent(
  ev: ClassroomStreamEvent,
): ev is Extract<ClassroomStreamEvent, { type: 'classroom_done' | 'classroom_cancelled' | 'classroom_error' }> {
  return (
    ev.type === 'classroom_done' ||
    ev.type === 'classroom_cancelled' ||
    ev.type === 'classroom_error'
  )
}

/**
 * 订阅课堂生成的实时进度（SSE）。
 *
 * 行为：
 * - 服务器不存在该 request_id → fetch 抛 404，由调用方处理（清持久化 + 提示）
 * - 服务器已结束 → 立即收一条 terminal 事件后流关闭
 * - 服务器进行中 → 持续收 progress 事件，直到 terminal
 * - 客户端断开 → 通过 signal abort SSE 连接；服务端不感知，但不会再 fanout 事件给已退订的 queue
 */
export async function* streamInteractiveClassroomGeneration(
  requestId: string,
  signal?: AbortSignal,
): AsyncGenerator<ClassroomStreamEvent, void, void> {
  const url = `/api/interactive-classroom/generate/stream/${encodeURIComponent(requestId)}`
  for await (const raw of sseFetch({ url, method: 'GET', signal })) {
    if (!raw || typeof raw !== 'object' || typeof raw.type !== 'string') continue
    const event = raw as unknown as ClassroomStreamEvent
    yield event
  }
}

// ---------- P7: 学习事件 ----------

export type LearningEventType =
  | 'quiz_submitted'
  | 'short_answer_scored'
  | 'scene_reviewed'
  | 'recommended_task_opened'
  | 'recommended_task_completed'
  | 'classroom_completed'

export interface LearningEvent {
  id: string
  type: LearningEventType
  user_id: string
  classroom_id: string
  scene_id?: string
  course_id?: string
  created_at: string
  knowledge_points: string[]
  payload: Record<string, unknown>
  retry_of?: string
  dedupe_key?: string
}

export async function recordClassroomEvent(
  classroomId: string,
  eventType: LearningEventType,
  payload?: {
    scene_id?: string
    task_id?: string
    task_type?: string
    knowledge_points?: string[]
    quiz_total?: number
    answered_total?: number
    review_count?: number
    result?: Record<string, unknown>
  },
): Promise<LearningEvent> {
  const res = await client.post<{ success: boolean; event: LearningEvent }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/event`,
    {
      event_type: eventType,
      scene_id: payload?.scene_id,
      payload,
    },
  )
  return res.data.event
}

export async function listClassroomEvents(
  classroomId: string,
  filterType?: LearningEventType,
): Promise<LearningEvent[]> {
  const params: Record<string, string> = {}
  if (filterType) params.type = filterType
  const res = await client.get<{ success: boolean; events: LearningEvent[] }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/events`,
    { params },
  )
  return res.data.events || []
}

export async function createClassroomPractice(
  classroomId: string,
  taskId: string,
  taskType: 'practice_weak_points' | 'challenge_practice' | string,
): Promise<InteractiveClassroomPayload> {
  const res = await client.post<{
    success: boolean
    classroom_id: string
    classroom: InteractiveClassroomPayload
  }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/practice`,
    {
      task_id: taskId,
      task_type: taskType,
    },
  )
  return res.data.classroom
}
