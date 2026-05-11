import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as memoryApi from '@/api/memory'

export const useMemoryStore = defineStore('memory', () => {
  const summary = ref<string>('')
  const loading = ref(false)

  async function fetchSummary() {
    loading.value = true
    try {
      summary.value = await memoryApi.getMemorySummary()
    } finally {
      loading.value = false
    }
  }

  async function save() {
    await memoryApi.saveMemory()
  }

  async function clearAll() {
    await memoryApi.clearMemory()
    summary.value = ''
  }

  async function clearDaily() {
    await memoryApi.clearMemoryDaily()
    await fetchSummary()
  }

  async function search(q: string) {
    return memoryApi.searchMemory(q)
  }

  return { summary, loading, fetchSummary, save, clearAll, clearDaily, search }
})
