import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ContentSettings, SettingsOption } from '@/types'
import * as settingsApi from '@/api/settings'

const DEFAULTS: ContentSettings = {
  mimo_voice: 'mimo_default',
  mimo_style: '',
  aspect_ratio: '3:4',
  cover_style: 'infographic',
  ppt_default_style: 'education',
  ppt_default_pages: 8,
  ppt_default_detail: 'normal',
  ppt_default_model: 'deepseek-v4-flash',
}

export const useSettingStore = defineStore('setting', () => {
  const settings = ref<ContentSettings>({ ...DEFAULTS })
  const options = ref<Record<string, SettingsOption[]>>({})
  const loading = ref(false)

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

  return { settings, options, loading, fetchSettings, updateSettings }
})
