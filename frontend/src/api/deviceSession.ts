import client from './client'
import { getUserId } from '@/composables/useUserId'

export async function ensureDeviceSession(): Promise<void> {
  await client.post('/api/device-session', { legacy_user_id: getUserId() })
}
