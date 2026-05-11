import client from './client'
import type { ContentSettings, SettingsResponse } from '@/types'

export async function getSettings() {
  const res = await client.get<SettingsResponse>('/api/settings')
  return res.data
}

export async function updateSettings(settings: Partial<ContentSettings>) {
  const res = await client.post<{ success: boolean; settings: ContentSettings }>(
    '/api/settings',
    { settings },
  )
  return res.data
}
