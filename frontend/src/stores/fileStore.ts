import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { GeneratedFile } from '@/types'
import * as fileApi from '@/api/files'

export const useFileStore = defineStore('file', () => {
  const files = ref<GeneratedFile[]>([])
  const loading = ref(false)
  const error = ref<string>('')

  async function fetchFiles() {
    loading.value = true
    error.value = ''
    try {
      files.value = await fileApi.listFiles()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function deleteFile(path: string) {
    await fileApi.deleteFile(path)
    files.value = files.value.filter((f) => f.path !== path)
  }

  async function renameFile(path: string, newName: string) {
    await fileApi.renameFile(path, newName)
    await fetchFiles()
  }

  async function clearAllFiles() {
    await fileApi.clearAllFiles()
    files.value = []
  }

  return {
    files,
    loading,
    error,
    fetchFiles,
    deleteFile,
    renameFile,
    clearAllFiles,
  }
})
