import test from 'node:test'
import assert from 'node:assert/strict'

import { isClassroomCancelError, isClassroomGenerationMissingError } from './classroomCancel.ts'

test('recognizes backend classroom cancellation message', () => {
  assert.equal(isClassroomCancelError(new Error('课堂生成已停止')), true)
})

test('recognizes axios abort-style cancellation messages', () => {
  assert.equal(isClassroomCancelError(new Error('canceled')), true)
  assert.equal(isClassroomCancelError(new DOMException('The operation was aborted', 'AbortError')), true)
})

test('does not treat unrelated errors as cancellation', () => {
  assert.equal(isClassroomCancelError(new Error('课堂生成失败')), false)
  assert.equal(isClassroomCancelError('课堂生成已停止'), false)
})

test('recognizes missing classroom generation status', () => {
  assert.equal(isClassroomGenerationMissingError({ response: { status: 404 } }), true)
  assert.equal(isClassroomGenerationMissingError({ response: { status: 500 } }), false)
})
