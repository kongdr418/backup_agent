import client from './client'

export async function getMemorySummary() {
  const res = await client.get<{ summary: string }>('/api/memory')
  return res.data.summary
}

export async function saveMemory() {
  await client.post('/api/memory/save', {})
}

export async function clearMemory() {
  await client.post('/api/memory/clear', {})
}

export async function clearMemoryDaily() {
  await client.post('/api/memory/clear-daily', {})
}

export async function searchMemory(q: string) {
  const res = await client.get<{ results: Array<Record<string, unknown>> }>('/api/memory/search', {
    params: { q },
  })
  return res.data.results
}
