import client from './client'
import { sseFetch } from './sse'
import type {
  PptGenerateParams,
  PptStreamEvent,
  PptJobListResponse,
  PptPreviewAllResponse,
  PptSlide,
} from '@/types'

export interface PptGenerateArgs extends PptGenerateParams {
  signal?: AbortSignal
}

export function pptGenerateStream(args: PptGenerateArgs) {
  const { signal, ...body } = args
  return sseFetch({
    url: '/api/ppt-svg/generate',
    method: 'POST',
    body,
    signal,
  }) as AsyncGenerator<PptStreamEvent, void, void>
}

export async function getPptSlide(jobId: string, slideNum: number) {
  const res = await client.get<PptSlide>(`/api/ppt-svg/preview/${jobId}/${slideNum}`)
  return res.data
}

export async function getPptAllSlides(jobId: string) {
  const res = await client.get<PptPreviewAllResponse>(`/api/ppt-svg/preview-all/${jobId}`)
  return res.data
}

export function pptDownloadUrl(jobId: string): string {
  return `/api/ppt-svg/download/${encodeURIComponent(jobId)}`
}

export async function listPptJobs() {
  const res = await client.get<PptJobListResponse>('/api/ppt-svg/list')
  return res.data.jobs
}

export async function deletePptJob(jobId: string) {
  await client.delete(`/api/ppt-svg/${encodeURIComponent(jobId)}`)
}
