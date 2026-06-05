import { onBeforeUnmount, ref, shallowRef } from 'vue'
import {
  cancelInteractiveClassroomGeneration,
  isClassroomTerminalEvent,
  streamInteractiveClassroomGeneration,
  type ClassroomStreamEvent,
} from '@/api/interactiveClassroom'

/**
 * 订阅一个课堂生成任务的 SSE 进度流。
 *
 * 用法：
 * ```ts
 * const stream = useInteractiveClassroomStream()
 * stream.onDone = (classroomId) => router.push(`/interactive-classroom/${classroomId}`)
 * stream.onCancelled = () => message.info('已停止')
 * stream.onError = (err) => message.error(err)
 * stream.start(requestId)
 * ```
 *
 * 状态都是 shallowRef，避免 Vue 对事件对象做深度响应式包装。
 */
export function useInteractiveClassroomStream() {
  const status = ref<'idle' | 'streaming' | 'done' | 'cancelled' | 'error'>('idle')
  const stage = ref<string>('')
  const stageLabel = ref<string>('')
  const stageIndex = ref<number>(0)
  const stageTotal = ref<number>(5)
  const sceneIndex = ref<number>(0)
  const sceneTotal = ref<number>(0)
  const lastScene = shallowRef<{ id: string; type: string; title: string; order: number } | null>(null)
  const error = ref<string>('')
  const classroomId = ref<string>('')

  let abortCtrl: AbortController | null = null
  let consumed = false

  // —— 钩子；调用方覆盖 ——
  let onDone: (classroomId: string, sceneCount: number) => void = () => {}
  let onCancelled: () => void = () => {}
  let onError: (message: string) => void = () => {}

  function reset() {
    status.value = 'idle'
    stage.value = ''
    stageLabel.value = ''
    stageIndex.value = 0
    stageTotal.value = 5
    sceneIndex.value = 0
    sceneTotal.value = 0
    lastScene.value = null
    error.value = ''
    classroomId.value = ''
  }

  function applyEvent(ev: ClassroomStreamEvent) {
    if (ev.type === 'classroom_start') {
      status.value = 'streaming'
      stageTotal.value = ev.stage_total || 5
      sceneTotal.value = ev.scene_total || 0
      return
    }
    if (ev.type === 'classroom_progress') {
      status.value = 'streaming'
      stage.value = ev.stage
      stageLabel.value = ev.stage_label
      stageIndex.value = ev.stage_index
      stageTotal.value = ev.stage_total || stageTotal.value
      sceneIndex.value = ev.scene_index
      sceneTotal.value = ev.scene_total || sceneTotal.value
      if (ev.scene) lastScene.value = ev.scene
      return
    }
    if (ev.type === 'classroom_done') {
      status.value = 'done'
      classroomId.value = ev.classroom_id
      onDone(ev.classroom_id, ev.scene_count)
      return
    }
    if (ev.type === 'classroom_cancelled') {
      status.value = 'cancelled'
      onCancelled()
      return
    }
    if (ev.type === 'classroom_error') {
      status.value = 'error'
      error.value = ev.error
      onError(ev.error)
      return
    }
  }

  /**
   * 计算进度百分比：[0, 100]。
   * 阶段粒度 + 场景粒度混合：每个阶段内按 scene_index/scene_total 推进。
   */
  const progressPercent = ref<number>(0)
  function recomputeProgress() {
    const st = stageTotal.value || 5
    const base = (stageIndex.value / st) * 100
    let within = 0
    if (sceneTotal.value > 0 && sceneIndex.value > 0) {
      // 估算当前阶段在 st 段中的等分宽度
      const stageFraction = 1 / st
      within = (sceneIndex.value / sceneTotal.value) * stageFraction * 100
    }
    // 单调递增保护：事件乱序/补发/公式受 stageTotal 变化影响时，
    // 进度条只能前进不能倒退。用 Math.max 锁住历史最高值。
    const next = Math.max(0, Math.min(99, Math.round(base + within)))
    if (next < progressPercent.value) return
    progressPercent.value = next
    if (status.value === 'done') progressPercent.value = 100
  }

  async function start(requestId: string) {
    stop()
    reset()
    abortCtrl = new AbortController()
    consumed = false
    status.value = 'streaming'

    try {
      for await (const ev of streamInteractiveClassroomGeneration(requestId, abortCtrl.signal)) {
        applyEvent(ev)
        recomputeProgress()
        if (isClassroomTerminalEvent(ev)) {
          consumed = true
          break
        }
      }
    } catch (err) {
      // 404（任务不存在）或其他网络错误：当 error 处理
      const message = err instanceof Error ? err.message : '生成进度连接失败'
      status.value = 'error'
      error.value = message
      onError(message)
    } finally {
      abortCtrl = null
    }
  }

  function stop() {
    if (abortCtrl) {
      try {
        abortCtrl.abort()
      } catch {
        /* ignore */
      }
      abortCtrl = null
    }
  }

  async function cancel(requestId: string) {
    if (!requestId) return
    stop()
    try {
      await cancelInteractiveClassroomGeneration(requestId)
    } catch {
      /* ignore */
    }
  }

  onBeforeUnmount(() => stop())

  return {
    // state
    status,
    stage,
    stageLabel,
    stageIndex,
    stageTotal,
    sceneIndex,
    sceneTotal,
    lastScene,
    progressPercent,
    error,
    classroomId,
    // controls
    start,
    stop,
    cancel,
    // hooks (callers assign)
    set onDone(fn: (classroomId: string, sceneCount: number) => void) {
      onDone = fn
    },
    set onCancelled(fn: () => void) {
      onCancelled = fn
    },
    set onError(fn: (message: string) => void) {
      onError = fn
    },
    // internal flag for tests
    get consumed() {
      return consumed
    },
  }
}
