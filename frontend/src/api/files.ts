import client from './client'
import type { GeneratedFile } from '@/types'

export async function listFiles() {
  const res = await client.get<{ files: GeneratedFile[] }>('/api/files')
  return res.data.files
}

export async function deleteFile(path: string) {
  await client.post('/api/files/delete', { path })
}

export async function renameFile(path: string, newName: string) {
  await client.post('/api/files/rename', { path, new_name: newName })
}

export async function clearAllFiles() {
  await client.post('/api/files/clear', {})
}

export async function readFile(path: string) {
  const res = await client.get<{ content: string; filename: string }>('/api/files/read', { params: { path } })
  return res.data
}

export function fileDownloadUrl(path: string): string {
  return `/api/files/download?path=${encodeURIComponent(path)}`
}
