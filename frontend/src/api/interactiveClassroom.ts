import client from './client'

export interface InteractiveClassroomGenerateRequest {
  topic: string
  course?: string
  ppt_job_id?: string
  student_profile?: StudentProfile
  tts_provider?: string
  tts_model?: string
  tts_voice?: string
  tts_api_key?: string
  tts_base_url?: string
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
}

export interface InteractiveClassroomQuestion {
  id: string
  type: 'single' | 'multiple' | string
  question: string
  options: Array<{ label: string; value: string }>
  answer?: string[]
  analysis?: string
  points?: number
  knowledge_point?: string
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
  student_profile?: StudentProfile
  source?: Record<string, unknown>
  scenes: InteractiveClassroomScene[]
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
  }>
  feedback_action?: InteractiveClassroomAction
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
  learned_points: string[]
  knowledge_summary: Record<string, {
    correct: number
    total: number
    earned_points: number
    total_points: number
    mastery: number
  }>
  weak_points: string[]
  strong_points: string[]
  next_recommendation: string
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

export async function getInteractiveClassroomReport(classroomId: string) {
  const res = await client.get<{ success: boolean; report: ClassroomReport }>(
    `/api/interactive-classroom/${encodeURIComponent(classroomId)}/report`,
  )
  return res.data.report
}
