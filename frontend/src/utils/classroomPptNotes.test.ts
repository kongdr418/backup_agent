import test from 'node:test'
import assert from 'node:assert/strict'

import { buildClassroomPptNotes } from './classroomPptNotes.ts'

test('builds PPT notes from classroom learner profile', () => {
  const notes = buildClassroomPptNotes({
    basis: '零基础',
    goal: '考试通过',
    style: '图解+案例',
    difficulty: '基础',
  })

  assert.match(notes, /智慧课堂生成要求/)
  assert.match(notes, /学习基础：零基础/)
  assert.match(notes, /学习目标：考试通过/)
  assert.match(notes, /讲解偏好：图解\+案例/)
  assert.match(notes, /题目难度：基础/)
  assert.match(notes, /适配 PPT 内容组织、案例选择、解释深度和课堂互动题/)
})

test('preserves existing PPT notes before classroom requirements', () => {
  const notes = buildClassroomPptNotes(
    {
      basis: '有基础',
      goal: '项目实战',
      style: '步骤推导',
      difficulty: '中等',
    },
    '请多加入代码演示',
  )

  assert.ok(notes.startsWith('请多加入代码演示\n\n'))
  assert.match(notes, /学习基础：有基础/)
  assert.match(notes, /学习目标：项目实战/)
})

test('omits empty learner profile fields', () => {
  const notes = buildClassroomPptNotes({
    basis: ' ',
    goal: '概念理解',
    style: '',
    difficulty: undefined,
  })

  assert.doesNotMatch(notes, /学习基础/)
  assert.match(notes, /学习目标：概念理解/)
  assert.doesNotMatch(notes, /讲解偏好/)
  assert.doesNotMatch(notes, /题目难度/)
})
