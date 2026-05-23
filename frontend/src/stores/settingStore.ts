import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ContentSettings, SettingsOption, ProviderInfo, ProviderConfig, ProvidersResponse, TTSProviderInfo, TTSProvidersResponse } from '@/types'
import * as settingsApi from '@/api/settings'
import * as providerApi from '@/api/providers'

const DEFAULTS: ContentSettings = {
  mimo_voice: 'mimo_default',
  mimo_style: '',
  aspect_ratio: '3:4',
  cover_style: 'infographic',
  chat_model: 'MiniMax-M2.5-highspeed',
  chat_provider: 'minimax',
  content_model: 'deepseek-v4-flash',
  content_provider: 'deepseek',
  ppt_model: 'deepseek-v4-flash',
  ppt_provider: 'deepseek',
  tts_provider: 'minimax-tts',
  tts_model: 'mimo-v2.5-tts',
  tts_voice: 'mimo_default',
  ppt_default_style: 'education',
  ppt_default_pages: 8,
  ppt_default_detail: 'normal',
  ppt_default_model: 'deepseek-v4-flash',
}

const LS_KEY = 'providers-config'
const TTS_LS_KEY = 'tts-config'

function loadProvidersConfig(): Record<string, ProviderConfig> {
  try {
    const raw = localStorage.getItem(LS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveProvidersConfig(config: Record<string, ProviderConfig>) {
  localStorage.setItem(LS_KEY, JSON.stringify(config))
}

function loadTTSConfig(): Record<string, ProviderConfig> {
  try {
    const raw = localStorage.getItem(TTS_LS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveTTSConfig(config: Record<string, ProviderConfig>) {
  localStorage.setItem(TTS_LS_KEY, JSON.stringify(config))
}

export const useSettingStore = defineStore('setting', () => {
  const settings = ref<ContentSettings>({ ...DEFAULTS })
  const options = ref<Record<string, SettingsOption[]>>({})
  const loading = ref(false)

  // Provider 配置（仅前端 localStorage，含 API Keys）
  const providers = ref<Record<string, ProviderInfo>>({})
  const providersLoading = ref(false)
  const providersConfig = ref<Record<string, ProviderConfig>>(loadProvidersConfig())

  // TTS Provider 配置
  const ttsProviders = ref<Record<string, TTSProviderInfo>>({})
  const ttsProvidersLoading = ref(false)
  const ttsConfig = ref<Record<string, ProviderConfig>>(loadTTSConfig())

  // 自动保存到 localStorage
  watch(providersConfig, (v) => saveProvidersConfig(v), { deep: true })
  watch(ttsConfig, (v) => saveTTSConfig(v), { deep: true })

  async function fetchSettings() {
    loading.value = true
    try {
      const data = await settingsApi.getSettings()
      settings.value = { ...DEFAULTS, ...data.settings }
      options.value = data.options as Record<string, SettingsOption[]>
    } finally {
      loading.value = false
    }
  }

  async function updateSettings(patch: Partial<ContentSettings>) {
    const merged = { ...settings.value, ...patch }
    settings.value = merged
    await settingsApi.updateSettings(patch)
  }

  async function fetchProviders() {
    providersLoading.value = true
    try {
      const data: ProvidersResponse = await providerApi.getProviders()
      providers.value = data.providers
      // 为首选 provider 设置默认 baseUrl
      for (const [pid, p] of Object.entries(data.providers)) {
        if (!providersConfig.value[pid]) {
          providersConfig.value[pid] = { apiKey: '', baseUrl: p.defaultBaseUrl }
        } else if (!providersConfig.value[pid].baseUrl) {
          providersConfig.value[pid].baseUrl = p.defaultBaseUrl
        }
      }
    } finally {
      providersLoading.value = false
    }
  }

  function setProviderConfig(providerId: string, patch: Partial<ProviderConfig>) {
    providersConfig.value[providerId] = {
      ...providersConfig.value[providerId] || { apiKey: '', baseUrl: '' },
      ...patch,
    }
  }

  /** 当前选中 provider 的 API Key（客户端填写优先，没有则用服务端） */
  function getEffectiveApiKey(providerId?: string): string {
    const pid = providerId || settings.value.chat_provider
    return providersConfig.value[pid]?.apiKey || ''
  }

  /** 当前选中 provider 的 Base URL */
  function getEffectiveBaseUrl(providerId?: string): string {
    const pid = providerId || settings.value.chat_provider
    return providersConfig.value[pid]?.baseUrl || providers.value[pid]?.defaultBaseUrl || ''
  }

  /** 当前选中 provider 的类型 */
  function getProviderType(providerId?: string): string {
    const pid = providerId || settings.value.chat_provider
    return providers.value[pid]?.type || 'openai'
  }

  // --- 内容生成模型 helpers ---

  function getEffectiveContentApiKey(): string {
    const pid = settings.value.content_provider
    return providersConfig.value[pid]?.apiKey || ''
  }

  function getEffectiveContentBaseUrl(): string {
    const pid = settings.value.content_provider
    return providersConfig.value[pid]?.baseUrl || providers.value[pid]?.defaultBaseUrl || ''
  }

  function getContentProviderType(): string {
    const pid = settings.value.content_provider
    return providers.value[pid]?.type || 'openai'
  }

  // --- PPT 生成模型 helpers ---

  function getEffectivePptApiKey(): string {
    const pid = settings.value.ppt_provider
    return providersConfig.value[pid]?.apiKey || ''
  }

  function getEffectivePptBaseUrl(): string {
    const pid = settings.value.ppt_provider
    return providersConfig.value[pid]?.baseUrl || providers.value[pid]?.defaultBaseUrl || ''
  }

  function getPptProviderType(): string {
    const pid = settings.value.ppt_provider
    return providers.value[pid]?.type || 'openai'
  }

  // --- TTS 语音合成 helpers ---

  async function fetchTTSProviders() {
    ttsProvidersLoading.value = true
    try {
      const data: TTSProvidersResponse = await providerApi.getTTSProviders()
      ttsProviders.value = data.providers
      for (const [pid, p] of Object.entries(data.providers)) {
        if (!ttsConfig.value[pid]) {
          ttsConfig.value[pid] = { apiKey: '', baseUrl: p.defaultBaseUrl }
        } else if (!ttsConfig.value[pid].baseUrl) {
          ttsConfig.value[pid].baseUrl = p.defaultBaseUrl
        }
      }
    } finally {
      ttsProvidersLoading.value = false
    }
  }

  function setTTSConfig(providerId: string, patch: Partial<ProviderConfig>) {
    ttsConfig.value[providerId] = {
      ...ttsConfig.value[providerId] || { apiKey: '', baseUrl: '' },
      ...patch,
    }
  }

  function getEffectiveTTSApiKey(): string {
    const pid = settings.value.tts_provider
    return ttsConfig.value[pid]?.apiKey || ''
  }

  function getEffectiveTTSBaseUrl(): string {
    const pid = settings.value.tts_provider
    return ttsConfig.value[pid]?.baseUrl || ttsProviders.value[pid]?.defaultBaseUrl || ''
  }

  return {
    settings, options, loading, fetchSettings, updateSettings,
    providers, providersLoading, providersConfig, fetchProviders, setProviderConfig,
    getEffectiveApiKey, getEffectiveBaseUrl, getProviderType,
    getEffectiveContentApiKey, getEffectiveContentBaseUrl, getContentProviderType,
    getEffectivePptApiKey, getEffectivePptBaseUrl, getPptProviderType,
    ttsProviders, ttsProvidersLoading, ttsConfig, fetchTTSProviders, setTTSConfig,
    getEffectiveTTSApiKey, getEffectiveTTSBaseUrl,
  }
})
