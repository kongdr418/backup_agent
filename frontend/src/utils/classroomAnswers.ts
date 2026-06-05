import type { InteractiveClassroomPayload, QuizSubmitResult } from '@/api/interactiveClassroom'

export function buildPlayerAnswerState(classroom: InteractiveClassroomPayload) {
  const answersByScene: Record<string, Record<string, string[]>> = {}
  const quizResultsByScene: Record<string, QuizSubmitResult | null> = {}

  const scenes = classroom.answers_record?.scenes || {}
  for (const [sceneId, record] of Object.entries(scenes)) {
    answersByScene[sceneId] = record.answers || {}
    if (record.evaluation) {
      quizResultsByScene[sceneId] = {
        success: true,
        score: record.evaluation.score || 0,
        correct: record.evaluation.correct || 0,
        total: record.evaluation.total || 0,
        earned_points: record.evaluation.earned_points || 0,
        total_points: record.evaluation.total_points || 0,
        results: record.evaluation.results || [],
      }
    } else {
      quizResultsByScene[sceneId] = null
    }
  }

  return { answersByScene, quizResultsByScene }
}
