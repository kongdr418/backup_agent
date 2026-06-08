import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createEmptyLearnerProfile,
  mergeLegacyStudentProfile,
  shouldMigrateLegacyProfile,
  toLegacyStudentProfile,
  UNIVERSITY_STAGE_VALUES,
} from './learnerProfile.ts'

test('migrates legacy classroom profile into an empty learner profile', () => {
  const profile = createEmptyLearnerProfile('user_1')
  const migrated = mergeLegacyStudentProfile(profile, {
    basis: '零基础',
    goal: '考试通过',
    style: '图解+案例',
    difficulty: '基础',
  })

  assert.equal(migrated.basic.learning_basis, '零基础')
  assert.equal(migrated.preferences.goal, '考试通过')
  assert.deepEqual(migrated.preferences.content_style, ['图解', '案例'])
  assert.equal(migrated.preferences.preferred_difficulty, '基础')
})

test('does not migrate legacy values over an existing backend profile', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.preferences.goal = '项目实战'

  assert.equal(shouldMigrateLegacyProfile(profile, {
    basis: '零基础',
    goal: '考试通过',
    style: '图解+案例',
    difficulty: '基础',
  }), false)
})

test('converts learner profile to the temporary classroom compatibility format', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.basic.learning_basis = '有基础'
  profile.preferences.goal = '概念理解'
  profile.preferences.content_style = ['步骤推导', '案例']
  profile.preferences.preferred_difficulty = '中等'

  assert.deepEqual(toLegacyStudentProfile(profile), {
    basis: '有基础',
    goal: '概念理解',
    style: '步骤推导+案例',
    difficulty: '中等',
  })
})

test('provides university-focused learning stages', () => {
  assert.deepEqual(UNIVERSITY_STAGE_VALUES, [
    '大一',
    '大二',
    '大三',
    '大四',
    '专升本',
    '硕士研究生',
    '博士研究生',
  ])
})
