import test from 'node:test'
import assert from 'node:assert/strict'

import { buildLockedPreviewScenes, mergePreviewScene } from './classroomPreviewScenes.ts'
import type { InteractiveClassroomScene } from '../api/interactiveClassroom.ts'

function scene(id: string, order: number): InteractiveClassroomScene {
  return {
    id,
    type: 'slide',
    title: id,
    order,
    knowledge_points: [],
    content: {},
    actions: [],
  }
}

test('merges preview scenes in classroom order', () => {
  const result = mergePreviewScene([scene('scene_slide_003', 3)], scene('scene_slide_001', 1), 0)

  assert.deepEqual(result.scenes.map((item) => item.id), ['scene_slide_001', 'scene_slide_003'])
})

test('keeps the same active scene after sorting inserts earlier scenes', () => {
  const result = mergePreviewScene([scene('scene_slide_003', 3)], scene('scene_slide_001', 1), 0)

  assert.equal(result.currentIndex, 1)
  assert.equal(result.scenes[result.currentIndex]?.id, 'scene_slide_003')
})

test('selects the first scene only when preview was empty', () => {
  const result = mergePreviewScene([], scene('scene_slide_002', 2), 0)

  assert.equal(result.currentIndex, 0)
  assert.equal(result.scenes[0]?.id, 'scene_slide_002')
})

test('does not sort zero-order quiz scenes before generated slides', () => {
  const quiz = {
    ...scene('scene_quiz_001', 0),
    type: 'quiz',
  } as InteractiveClassroomScene
  const result = mergePreviewScene([scene('scene_slide_001', 1)], quiz, 0)

  assert.deepEqual(result.scenes.map((item) => item.id), ['scene_slide_001', 'scene_quiz_001'])
})

test('builds locked placeholders for scenes that are still generating', () => {
  const placeholders = buildLockedPreviewScenes(1, 4)

  assert.deepEqual(placeholders.map((item) => item.title), [
    '第 2 页生成中',
    '第 3 页生成中',
    '第 4 页生成中',
  ])
  assert.equal(placeholders[0]?.locked, true)
})

test('does not invent locked placeholders without a larger expected total', () => {
  assert.deepEqual(buildLockedPreviewScenes(4, 4), [])
  assert.deepEqual(buildLockedPreviewScenes(4, 0), [])
})

test('labels locked quiz and mindmap placeholders after slide count', () => {
  const placeholders = buildLockedPreviewScenes(5, 8, 5)

  assert.deepEqual(placeholders.map((item) => item.title), [
    '随堂测验生成中',
    '随堂测验生成中',
    '知识结构生成中',
  ])
})
