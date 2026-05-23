import client from './client'
import type { ProvidersResponse, TTSProvidersResponse, VerifyModelRequest } from '@/types'

export async function getProviders() {
  const res = await client.get<ProvidersResponse>('/api/providers')
  return res.data
}

export async function getTTSProviders() {
  const res = await client.get<TTSProvidersResponse>('/api/tts-providers')
  return res.data
}

export async function verifyModel(req: VerifyModelRequest) {
  const res = await client.post<{ success: boolean; message: string; response?: string }>(
    '/api/verify-model',
    req,
  )
  return res.data
}
