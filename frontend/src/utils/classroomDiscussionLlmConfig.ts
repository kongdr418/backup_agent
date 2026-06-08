import type { ContentSettings } from '@/types'

export interface ClassroomDiscussionLlmPayload {
  content_model: string
  content_api_key: string
  content_base_url: string
  content_provider_type: string
}

export function buildClassroomDiscussionLlmPayload(input: {
  settings: Pick<ContentSettings, 'chat_model'>
  getEffectiveApiKey: () => string
  getEffectiveBaseUrl: () => string
  getProviderType: () => string
}): ClassroomDiscussionLlmPayload {
  return {
    content_model: input.settings.chat_model || '',
    content_api_key: input.getEffectiveApiKey(),
    content_base_url: input.getEffectiveBaseUrl(),
    content_provider_type: input.getProviderType(),
  }
}
