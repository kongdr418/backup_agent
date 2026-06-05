import test from 'node:test'
import assert from 'node:assert/strict'

import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import {
  clearPersistedDiscussionMessages,
  loadPersistedDiscussionMessages,
  savePersistedDiscussionMessages,
} from './classroomDiscussionState.ts'

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

const messages: ClassroomDiscussionMessage[] = [
  { role: 'user', content: '换个例子' },
  { role: 'assistant', content: '你先看看浏览器和服务器谁先发起请求。' },
]

test('persists discussion messages by classroom and scene', () => {
  store.clear()

  savePersistedDiscussionMessages('cls_001', 'scene_008', messages)

  assert.deepEqual(loadPersistedDiscussionMessages('cls_001', 'scene_008'), messages)
  assert.equal(loadPersistedDiscussionMessages('cls_001', 'scene_009'), null)
})

test('clears discussion messages for one classroom scene', () => {
  store.clear()

  savePersistedDiscussionMessages('cls_001', 'scene_008', messages)
  clearPersistedDiscussionMessages('cls_001', 'scene_008')

  assert.equal(loadPersistedDiscussionMessages('cls_001', 'scene_008'), null)
})
