import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PptGenerateParams, PptJob, PptSlide, PptStage } from '@/types'
import * as pptApi from '@/api/pptSvg'

export interface PptGenState {
  status: 'idle' | 'streaming' | 'done' | 'error' | 'cancelled'
  stage: PptStage | string
  message: string
  progress: number
  slides: PptSlide[]
  jobId?: string
  pptxFilename?: string
  totalSlides?: number
  error?: string
  startedAt?: number
  finishedAt?: number
}

const initialState = (): PptGenState => ({
  status: 'idle',
  stage: 'content_planning',
  message: '',
  progress: 0,
  slides: [],
})

const DEFAULT_PARAMS: PptGenerateParams = {
  topic: '',
  language: 'zh',
  num_slides: undefined,
  style: 'education',
  detail_level: 'normal',
  model: 'deepseek-v4-flash',
  canvas_format: 'ppt169',
  repair_enabled: false,
  template_id: undefined,
}

export const usePptStore = defineStore(
  'ppt',
  () => {
    const params = ref<PptGenerateParams>({ ...DEFAULT_PARAMS })
    const gen = ref<PptGenState>(initialState())
    const jobs = ref<PptJob[]>([])
    const jobsLoading = ref(false)
    const abortController = ref<AbortController | null>(null)

    const isGenerating = computed(() => gen.value.status === 'streaming')
    const canDownload = computed(
      () => gen.value.status === 'done' && !!gen.value.jobId && !!gen.value.pptxFilename,
    )

    function resetGen() {
      gen.value = initialState()
    }

    function setAbort(ctrl: AbortController | null) {
      abortController.value = ctrl
    }

    function cancel() {
      if (abortController.value) {
        abortController.value.abort()
        abortController.value = null
      }
      if (gen.value.status === 'streaming') {
        gen.value.status = 'cancelled'
        gen.value.message = '已取消'
      }
    }

    async function refreshJobs() {
      jobsLoading.value = true
      try {
        jobs.value = await pptApi.listPptJobs()
      } finally {
        jobsLoading.value = false
      }
    }

    async function deleteJob(jobId: string) {
      await pptApi.deletePptJob(jobId)
      jobs.value = jobs.value.filter((j) => j.job_id !== jobId)
      if (gen.value.jobId === jobId) {
        resetGen()
      }
    }

    async function clearAllJobs() {
      await pptApi.clearAllPptJobs()
      jobs.value = []
      resetGen()
    }

    return {
      params,
      gen,
      jobs,
      jobsLoading,
      abortController,
      isGenerating,
      canDownload,
      resetGen,
      setAbort,
      cancel,
      refreshJobs,
      deleteJob,
      clearAllJobs,
    }
  },
  {
    persist: {
      key: 'ai_creator.ppt_params',
      storage: localStorage,
      paths: ['params'],
    } as never,
  },
)
