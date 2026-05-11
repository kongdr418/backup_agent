import type { PptGenerateParams, PptStage, PptStreamEvent } from '@/types'
import { pptGenerateStream } from '@/api/pptSvg'
import { usePptStore } from '@/stores/pptStore'

const STAGE_NAMES: Record<string, string> = {
  content_planning: '内容规划',
  design: '设计规范',
  svg_generation: '逐页 SVG',
  export: '转换 PPTX',
  done: '完成',
  error: '错误',
}

const STAGE_ORDER = ['content_planning', 'design', 'svg_generation', 'export']

function mapStage(ev: PptStreamEvent): PptStage | string {
  const stage = ev.stage || ''
  // 直接信任后端 stage 字段; finalize/init 映射到前端已有阶段
  if (stage === 'finalize') return 'svg_generation'
  if (stage === 'init') return 'content_planning'
  if (STAGE_NAMES[stage]) return stage as PptStage
  // Fallback: map event status to a rough stage
  const status = (ev.type || '').replace(/^ppt_svg_/, '')
  if (status === 'started' || status === 'progress') {
    const msg = ev.message || ''
    if (msg.includes('规划')) return 'content_planning'
    if (msg.includes('设计')) return 'design'
    if (msg.includes('SVG') || msg.includes('页')) return 'svg_generation'
    if (msg.includes('导出') || msg.includes('PPTX')) return 'export'
  }
  return 'content_planning'
}

export function usePptStream() {
  const store = usePptStore()

  async function generate(params: PptGenerateParams) {
    if (store.isGenerating) return

    store.resetGen()
    store.gen.status = 'streaming'
    store.gen.stage = 'content_planning'
    store.gen.message = '正在初始化...'
    store.gen.progress = 0
    store.gen.startedAt = Date.now()

    const ctrl = new AbortController()
    store.setAbort(ctrl)

    try {
      const stream = pptGenerateStream({ ...params, signal: ctrl.signal })

      for await (const ev of stream as AsyncGenerator<PptStreamEvent>) {
        if ('done' in ev && (ev as { done?: boolean }).done) break

        if (ev.type === 'error' || ev.type === 'ppt_svg_error') {
          throw new Error(ev.error || ev.message || 'PPT 生成失败')
        }

        const stage = mapStage(ev)
        store.gen.stage = stage
        if (ev.message) store.gen.message = ev.message
        if (typeof ev.progress === 'number') {
          store.gen.progress = Math.max(store.gen.progress, Math.round(ev.progress * 100))
        }
        if (ev.total_slides) store.gen.totalSlides = ev.total_slides

        if (ev.slide && typeof ev.slide.page === 'number' && ev.slide.svg) {
          const existing = store.gen.slides.findIndex((s) => s.page === ev.slide!.page)
          if (existing >= 0) {
            store.gen.slides[existing] = { page: ev.slide.page, svg: ev.slide.svg }
          } else {
            store.gen.slides.push({ page: ev.slide.page, svg: ev.slide.svg })
            store.gen.slides.sort((a, b) => a.page - b.page)
          }
        }

        if (ev.job_id) store.gen.jobId = ev.job_id
        if (ev.pptx_filename) store.gen.pptxFilename = ev.pptx_filename

        // Only mark done when the last stage (export) completes
        if ((ev.type === 'ppt_svg_complete' && stage === 'export') || ev.progress === 1.0) {
          store.gen.status = 'done'
          store.gen.progress = 100
          store.gen.message = STAGE_NAMES.done
          store.gen.finishedAt = Date.now()
        }
      }

      if (store.gen.status === 'streaming') {
        store.gen.status = 'done'
        store.gen.progress = 100
        store.gen.finishedAt = Date.now()
      }

      // refresh history list
      store.refreshJobs().catch(() => undefined)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败'
      const aborted = msg.includes('aborted') || msg === 'AbortError'
      if (aborted) {
        store.gen.status = 'cancelled'
        store.gen.message = '已取消'
      } else {
        store.gen.status = 'error'
        store.gen.error = msg
        store.gen.message = msg
      }
    } finally {
      store.setAbort(null)
    }
  }

  return { generate, stageNames: STAGE_NAMES }
}
