import test from 'node:test'
import assert from 'node:assert/strict'

import { buildClassroomPptNotes } from './classroomPptNotes.ts'

test('builds PPT notes from classroom learner profile', () => {
  const notes = buildClassroomPptNotes('', {
    weakPoints: ['循环边界'],
    strongPoints: ['循环概念'],
    nextRecommendation: '下一节进入嵌套循环。',
  })

  assert.match(notes, /智慧课堂学习路径上下文/)
  assert.match(notes, /薄弱点：循环边界/)
  assert.match(notes, /已掌握：循环概念/)
  assert.match(notes, /下一步建议：下一节进入嵌套循环。/)
})

test('preserves existing PPT notes before classroom requirements', () => {
  const notes = buildClassroomPptNotes(
    '请多加入代码演示',
    {
      weakPoints: ['依赖注入'],
    },
  )

  assert.ok(notes.startsWith('请多加入代码演示\n\n'))
  assert.match(notes, /薄弱点：依赖注入/)
})

test('omits empty learner profile fields', () => {
  const notes = buildClassroomPptNotes('', {})

  assert.equal(notes, '')
})

test('includes next-lesson learning context when provided', () => {
  const notes = buildClassroomPptNotes(
    '',
    {
      weakPoints: ['依赖注入', '自动配置'],
      strongPoints: ['项目结构'],
      nextRecommendation: '下一节重点补足依赖注入，并进入配置实战。',
      nextLessonNotes: '【下一堂课生成要求】\n本课主题：配置实战',
    },
  )

  assert.match(notes, /智慧课堂学习路径上下文/)
  assert.match(notes, /薄弱点：依赖注入、自动配置/)
  assert.match(notes, /已掌握：项目结构/)
  assert.match(notes, /下一节重点补足依赖注入/)
  assert.match(notes, /下一堂课生成要求/)
  assert.match(notes, /本课主题：配置实战/)
})
