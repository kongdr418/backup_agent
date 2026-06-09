import type {
  InteractiveClassroomScene,
  LearningEventType,
} from '../api/interactiveClassroom.ts'

/** 尝试记录学习事件，失败时静默（不影响主流程）。 */
async function emit(
  classroomId: string,
  type: LearningEventType,
  payload?: Record<string, unknown>,
): Promise<void> {
  try {
    const { recordClassroomEvent } = await import('../api/interactiveClassroom.ts')
    await recordClassroomEvent(classroomId, type, payload as any)
  } catch {
    // 静默：学习事件记录不应阻断课堂播放
  }
}

/** 复听讲解页。 */
export async function emitSceneReviewed(
  classroomId: string,
  scene: Pick<InteractiveClassroomScene, 'id' | 'knowledge_points'>,
  reviewCount = 1,
): Promise<void> {
  await emit(classroomId, 'scene_reviewed', {
    scene_id: scene.id,
    knowledge_points: scene.knowledge_points || [],
    review_count: reviewCount,
  })
}

/** 点击推荐任务。 */
export async function emitRecommendedTaskOpened(
  classroomId: string,
  taskId: string,
  taskType: string,
  knowledgePoints: string[] = [],
): Promise<void> {
  await emit(classroomId, 'recommended_task_opened', {
    task_id: taskId,
    task_type: taskType,
    knowledge_points: knowledgePoints,
  })
}

/** 完成推荐任务。 */
export async function emitRecommendedTaskCompleted(
  classroomId: string,
  taskId: string,
  taskType: string,
  knowledgePoints: string[] = [],
  result: Record<string, unknown> = {},
): Promise<void> {
  await emit(classroomId, 'recommended_task_completed', {
    task_id: taskId,
    task_type: taskType,
    knowledge_points: knowledgePoints,
    result,
  })
}

/** 课堂完成（所有测验答完）。 */
export async function emitClassroomCompleted(
  classroomId: string,
  quizTotal: number,
  answeredTotal: number,
): Promise<void> {
  await emit(classroomId, 'classroom_completed', {
    quiz_total: quizTotal,
    answered_total: answeredTotal,
  })
}
