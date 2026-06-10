import test from 'node:test'
import assert from 'node:assert/strict'

import { classroomUnitCountLabel, classroomUnitLabel } from './classroomLessonDisplay.ts'

test('labels regular root and next lessons as lessons', () => {
  assert.equal(classroomUnitLabel({ lesson_kind: 'root', lesson_index: 1 }), '第 1 课')
  assert.equal(classroomUnitLabel({ lesson_kind: 'next_lesson', lesson_index: 2 }), '第 2 课')
})

test('labels practice classrooms as learning exercises instead of lessons', () => {
  assert.equal(classroomUnitLabel({ lesson_kind: 'practice', lesson_index: 3 }), '补强练习')
  assert.equal(classroomUnitLabel({ lesson_kind: 'challenge_practice', lesson_index: 4 }), '挑战练习')
})

test('counts mixed classroom groups as learning units', () => {
  assert.equal(classroomUnitCountLabel(1), '1 个学习单元')
  assert.equal(classroomUnitCountLabel(3), '3 个学习单元')
})
