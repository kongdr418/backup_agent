import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getVideoStatus } from '@/api/video'

export const useVideoStore = defineStore(
  'video',
  () => {
    // 持久化到 localStorage 的状态
    const activeJobId = ref('')
    const generating = ref(false)
    const progress = ref(0)
    const progressMessage = ref('')
    const pptxPath = ref('')
    const voice = ref('mimo_default')

    // 轮询定时器（不持久化）
    let pollTimer: ReturnType<typeof setInterval> | null = null

    function setActiveJob(jobId: string, path: string, v: string) {
      activeJobId.value = jobId
      generating.value = true
      progress.value = 0.1
      progressMessage.value = '准备开始...'
      pptxPath.value = path
      voice.value = v
    }

    function clearActiveJob() {
      activeJobId.value = ''
      generating.value = false
      progress.value = 0
      progressMessage.value = ''
      pptxPath.value = ''
      stopPolling()
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    /**
     * 开始轮询任务状态，用于页面刷新后恢复进度
     * @param onDone 任务完成时的回调
     * @param onError 任务失败时的回调
     */
    function startPolling(onDone: () => void, onError: (msg: string) => void) {
      stopPolling()
      if (!activeJobId.value) return

      pollTimer = setInterval(async () => {
        try {
          const status = await getVideoStatus(activeJobId.value)
          if (status.status === 'done') {
            progress.value = 1.0
            progressMessage.value = '视频生成完成'
            generating.value = false
            stopPolling()
            onDone()
          } else if (status.status === 'error') {
            const errMsg = status.message
            clearActiveJob()
            stopPolling()
            onError(errMsg)
          } else if (status.status === 'generating') {
            progress.value = status.progress
            progressMessage.value = status.message
          } else {
            // not_found — 任务不存在，清除状态
            clearActiveJob()
            stopPolling()
          }
        } catch {
          // 网络错误，停止轮询
          clearActiveJob()
          stopPolling()
        }
      }, 2000)
    }

    return {
      activeJobId,
      generating,
      progress,
      progressMessage,
      pptxPath,
      voice,
      setActiveJob,
      clearActiveJob,
      startPolling,
      stopPolling,
    }
  },
  {
    persist: {
      key: 'ai_creator.video_gen',
      storage: localStorage,
      paths: ['activeJobId', 'generating', 'progress', 'progressMessage', 'pptxPath', 'voice'],
    } as never,
  },
)
