import test from 'node:test'
import assert from 'node:assert/strict'

import { shouldSubmitDiscussionOnEnter } from './discussionInput.ts'

test('Enter without shift submits discussion message', () => {
  assert.equal(
    shouldSubmitDiscussionOnEnter({ key: 'Enter', shiftKey: false, isComposing: false }),
    true,
  )
})

test('Shift+Enter keeps newline behavior', () => {
  assert.equal(
    shouldSubmitDiscussionOnEnter({ key: 'Enter', shiftKey: true, isComposing: false }),
    false,
  )
})

test('IME composing Enter should not submit', () => {
  assert.equal(
    shouldSubmitDiscussionOnEnter({ key: 'Enter', shiftKey: false, isComposing: true }),
    false,
  )
})
