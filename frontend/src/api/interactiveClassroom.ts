import client from './client'

export interface InteractiveClassroomGenerateRequest {
  topic: string
  course?: string
  ppt_job_id?: string
  tts_provider?: string
  tts_model?: string
  tts_voice?: string
  tts_api_key?: string
  tts_base_url?: string
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
}

export interface InteractiveClassroomQuestion {
  id: string
  type: string
  question: string
  options: Array<{ label: string; value: string }>
  answer?: string[]
  analysis?: string
  points?: number
}

export interface InteractiveClassroomScene {
  id: string
  type: 'slide' | 'quiz' | 'summary' | string
  title: string
  order: number
  content: Record<string, unknown>
  actions: InteractiveClassroomAction[]
}

export interface InteractiveClassroomPayload {
  id: string
  title: string
  topic: string
  course?: string
  status: string
  scenes: InteractiveClassroomScene[]
}

export interface QuizSubmitResult {
  success: boolean
  score: number
  correct: number
  total: number
  results: Array<{
    question_id: string
    correct: boolean
    your_answer: string[]
    correct_answer: string[]
    analysis?: string
  }>
  feedback_action?: InteractiveClassroomAction
}

export async function generateInteractiveClassroom(body: InteractiveClassroomGenerateRequest) {
  const res = await client.post<{
    success: boolean
    classroom_id: string
    status: string
    classroom: InteractiveClassroomPayload
  }>('/api/interactive-classroom/generate', body, {
    timeout: 180_000,
  })
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

export async function submitInteractiveClassroomAnswer(
  classroomId: string,
  sceneId: string,
  answers: Record<string, string[]>,
) {
  const res = await client.post<QuizSubmitResult>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/answer`,
    {
      scene_id: sceneId,
      answers,
    },
  )
  return res.data
}
