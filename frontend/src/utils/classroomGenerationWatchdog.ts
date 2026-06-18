import type { InteractiveClassroomGenerationStatus } from '@/api/interactiveClassroom'

export type ClassroomGenerationWatchdogAction =
  | { type: 'continue' }
  | { type: 'done'; classroomId: string }
  | { type: 'cancelled' }
  | { type: 'error'; message: string }

export function resolveClassroomGenerationWatchdogAction(
  job: Pick<InteractiveClassroomGenerationStatus, 'status' | 'classroom_id' | 'error'> | null | undefined,
): ClassroomGenerationWatchdogAction {
  if (!job) return { type: 'continue' }
  if (job.status === 'done') {
    return job.classroom_id
      ? { type: 'done', classroomId: job.classroom_id }
      : { type: 'error', message: '课堂生成完成但缺少课堂编号' }
  }
  if (job.status === 'cancelled') return { type: 'cancelled' }
  if (job.status === 'error') {
    return { type: 'error', message: job.error || '课堂生成失败' }
  }
  return { type: 'continue' }
}

export function resolveClassroomGenerationWatchdogProgress(
  job: Pick<
    InteractiveClassroomGenerationStatus,
    'status' | 'stage_index' | 'stage_total' | 'scene_index' | 'scene_total'
  > | null | undefined,
  current = 0,
) {
  if (!job) return current
  if (job.status === 'done') return 100
  const stageTotal = typeof job.stage_total === 'number' && job.stage_total > 0 ? job.stage_total : 5
  const stageIndex = typeof job.stage_index === 'number' ? job.stage_index : 0
  const sceneIndex = typeof job.scene_index === 'number' ? job.scene_index : 0
  const sceneTotal = typeof job.scene_total === 'number' && job.scene_total > 0 ? job.scene_total : 0
  const base = (stageIndex / stageTotal) * 100
  const within = sceneTotal > 0 && sceneIndex > 0
    ? (sceneIndex / sceneTotal) * (1 / stageTotal) * 100
    : 0
  const next = Math.max(0, Math.min(99, Math.round(base + within)))
  return Math.max(current, next)
}
