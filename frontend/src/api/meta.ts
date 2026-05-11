import client from './client'
import type { ModelInfo } from '@/types'

export async function getHealth() {
  const res = await client.get<{ status: string; service?: string }>('/api/health')
  return res.data
}

export async function getInfo() {
  const res = await client.get<Record<string, unknown>>('/api/info')
  return res.data
}

export async function getModels() {
  const res = await client.get<{ models: ModelInfo[] }>('/api/models')
  return res.data.models
}
