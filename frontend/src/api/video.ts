import client from './client'

export interface VideoJobStatus {
  status: 'generating' | 'done' | 'error' | 'not_found'
  progress: number
  message: string
}

export async function getVideoStatus(jobId: string): Promise<VideoJobStatus> {
  const res = await client.get<VideoJobStatus>(`/api/ppt-video/status/${jobId}`)
  return res.data
}
