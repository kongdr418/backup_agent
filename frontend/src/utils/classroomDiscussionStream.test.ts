import test from 'node:test'
import assert from 'node:assert/strict'

import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import { applyDiscussionAgentEvent } from './classroomDiscussionStream.ts'

test('agent_start appends a pending assistant message for the speaking agent', () => {
  const messages: ClassroomDiscussionMessage[] = [
    { role: 'user', content: '计算机视觉很重要吗' },
  ]

  const next = applyDiscussionAgentEvent(messages, {
    type: 'agent_start',
    message_id: 'discussion_2_student_peer',
    agent_id: 'student_peer',
    agent_name: 'AI 同学',
  }, 'manual')

  assert.equal(next.length, 2)
  assert.deepEqual(next[1], {
    role: 'assistant',
    content: '',
    trigger: 'manual',
    agent_id: 'student_peer',
    agent_name: 'AI 同学',
    message_id: 'discussion_2_student_peer',
    pending: true,
  })
})

test('agent_chunk fills the pending message and clears pending state', () => {
  const messages: ClassroomDiscussionMessage[] = [
    { role: 'user', content: '计算机视觉很重要吗' },
    {
      role: 'assistant',
      content: '',
      trigger: 'manual',
      agent_id: 'student_peer',
      agent_name: 'AI 同学',
      message_id: 'discussion_2_student_peer',
      pending: true,
    },
  ]

  const next = applyDiscussionAgentEvent(messages, {
    type: 'agent_chunk',
    message_id: 'discussion_2_student_peer',
    agent_id: 'student_peer',
    agent_name: 'AI 同学',
    chunk: '自动驾驶具体怎么用到视觉？',
  }, 'manual')

  assert.equal(next.length, 2)
  assert.equal(next[1].content, '自动驾驶具体怎么用到视觉？')
  assert.equal(next[1].pending, false)
})
