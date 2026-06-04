import type {
  ClassroomRecommendedTask,
  ClassroomReport,
  InteractiveClassroomScene,
  StudentProfile,
} from '../api/interactiveClassroom.ts'

export interface ReportTaskActionContext {
  orderedScenes: Array<Pick<InteractiveClassroomScene, 'id' | 'type'>>
  answeredSceneIds: string[]
  topic: string
  course: string
  studentProfile: StudentProfile
  report: Pick<ClassroomReport, 'weak_points' | 'strong_points' | 'next_recommendation'> | null
}

export type ReportTaskAction =
  | { kind: 'scene'; sceneId: string }
  | { kind: 'ppt-studio'; query: Record<string, string> }
  | { kind: 'none' }

export function buildNextLessonQuery(payload: {
  topic: string
  course: string
  studentProfile: StudentProfile
  report: Pick<ClassroomReport, 'weak_points' | 'strong_points' | 'next_recommendation'> | null
}) {
  const query: Record<string, string> = {
    from: 'interactive-classroom',
    topic: payload.topic,
    course: payload.course,
  }

  if (payload.studentProfile.basis) query.basis = payload.studentProfile.basis
  if (payload.studentProfile.goal) query.goal = payload.studentProfile.goal
  if (payload.studentProfile.style) query.style = payload.studentProfile.style
  if (payload.studentProfile.difficulty) query.difficulty = payload.studentProfile.difficulty

  if (payload.report?.weak_points?.length) query.weak_points = payload.report.weak_points.join('||')
  if (payload.report?.strong_points?.length) query.strong_points = payload.report.strong_points.join('||')
  if (payload.report?.next_recommendation?.trim()) query.next_recommendation = payload.report.next_recommendation.trim()

  return query
}

function firstUnansweredQuizSceneId(
  orderedScenes: Array<Pick<InteractiveClassroomScene, 'id' | 'type'>>,
  answeredSceneIds: string[],
) {
  const answered = new Set(answeredSceneIds)
  return orderedScenes.find((scene) => scene.type === 'quiz' && !answered.has(scene.id))?.id || ''
}

export function resolveReportTaskAction(
  task: ClassroomRecommendedTask,
  context: ReportTaskActionContext,
): ReportTaskAction {
  if (task.type === 'review_weak_points' && task.target_scene_ids.length) {
    return { kind: 'scene', sceneId: task.target_scene_ids[0] }
  }

  if (task.type === 'complete_quizzes') {
    const sceneId = firstUnansweredQuizSceneId(context.orderedScenes, context.answeredSceneIds)
    return sceneId ? { kind: 'scene', sceneId } : { kind: 'none' }
  }

  if (task.type === 'next_lesson') {
    return {
      kind: 'ppt-studio',
      query: buildNextLessonQuery({
        topic: context.topic,
        course: context.course,
        studentProfile: context.studentProfile,
        report: context.report,
      }),
    }
  }

  return { kind: 'none' }
}
