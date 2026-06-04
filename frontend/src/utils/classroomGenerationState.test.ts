import test from 'node:test'
import assert from 'node:assert/strict'

import {
  CLASSROOM_GENERATION_STORAGE_KEY,
  clearPersistedClassroomGeneration,
  loadPersistedClassroomGeneration,
  savePersistedClassroomGeneration,
} from './classroomGenerationState.ts'

const store = new Map<string, string>()
globalThis.localStorage = {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => {
    store.set(key, value)
  },
  removeItem: (key: string) => {
    store.delete(key)
  },
  clear: () => {
    store.clear()
  },
  key: (index: number) => Array.from(store.keys())[index] ?? null,
  get length() {
    return store.size
  },
} as Storage

test('persists classroom generation request for refresh recovery', () => {
  store.clear()

  savePersistedClassroomGeneration({
    requestId: 'classroom:123',
    surface: 'home',
    topic: 'Python 入门',
    startedAt: 1000,
  })

  assert.equal(localStorage.getItem(CLASSROOM_GENERATION_STORAGE_KEY)?.includes('classroom:123'), true)
  assert.deepEqual(loadPersistedClassroomGeneration(), {
    requestId: 'classroom:123',
    surface: 'home',
    topic: 'Python 入门',
    startedAt: 1000,
  })
})

test('clears persisted classroom generation request', () => {
  savePersistedClassroomGeneration({
    requestId: 'classroom:456',
    surface: 'ppt-studio',
    topic: 'Python 入门',
    startedAt: 1000,
  })

  clearPersistedClassroomGeneration()

  assert.equal(loadPersistedClassroomGeneration(), null)
})
