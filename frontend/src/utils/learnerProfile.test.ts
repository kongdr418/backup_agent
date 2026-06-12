import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clearLearnerCourseProfile,
  clearLearnerCourses,
  clearLearnerProfileBasic,
  clearLearnerProfilePreferences,
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

test('clears basic learner information without touching preferences or courses', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.basic = {
    display_name: '小林',
    learning_stage: '大二',
    learning_basis: '有基础',
    background: '软件工程',
  }
  profile.preferences.goal = '项目实战'
  profile.courses.course_python = {
    course_id: 'course_python',
    course_name: 'Python',
    mastery: {},
    strong_points: [],
    weak_points: [],
    recent_trend: 'stable',
  }

  const cleared = clearLearnerProfileBasic(profile)

  assert.deepEqual(cleared.basic, {
    display_name: '',
    learning_stage: '',
    learning_basis: '',
    background: '',
  })
  assert.equal(cleared.preferences.goal, '项目实战')
  assert.equal(cleared.courses.course_python.course_name, 'Python')
})

test('clears learner preferences without touching basic information or courses', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.basic.display_name = '小林'
  profile.preferences = {
    goal: '考试通过',
    content_style: ['图解', '案例'],
    preferred_difficulty: '中等',
    tutoring_style: '引导式',
  }
  profile.courses.course_physics = {
    course_id: 'course_physics',
    course_name: '物理',
    mastery: {},
    strong_points: [],
    weak_points: [],
    recent_trend: 'stable',
  }

  const cleared = clearLearnerProfilePreferences(profile)

  assert.deepEqual(cleared.preferences, {
    goal: '',
    content_style: [],
    preferred_difficulty: '',
    tutoring_style: '',
  })
  assert.equal(cleared.basic.display_name, '小林')
  assert.equal(cleared.courses.course_physics.course_name, '物理')
})

test('clears all course profiles and related course artifacts', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.courses.course_physics = {
    course_id: 'course_physics',
    course_name: '物理',
    mastery: {},
    strong_points: [],
    weak_points: [],
    recent_trend: 'stable',
  }
  profile.pending_updates = [
    { id: 'u1', course_id: 'course_physics', confidence: 0.8, status: 'pending' },
    { id: 'u_orphan', course_id: 'course_orphan', confidence: 0.8, status: 'pending' },
    { id: 'u2', confidence: 0.7, status: 'pending' },
  ]
  profile.recent_recommendations = [
    {
      id: 'r1',
      type: 'review',
      title: '复习',
      description: '复习物理',
      priority: 'high',
      knowledge_points: [],
      course_id: 'course_physics',
    },
  ]

  const cleared = clearLearnerCourses(profile)

  assert.deepEqual(cleared.courses, {})
  assert.deepEqual(cleared.pending_updates, [{ id: 'u2', confidence: 0.7, status: 'pending' }])
  assert.deepEqual(cleared.recent_recommendations, [])
})

test('clears one course profile and only that course artifacts', () => {
  const profile = createEmptyLearnerProfile('user_1')
  profile.courses.course_physics = {
    course_id: 'course_physics',
    course_name: '物理',
    mastery: {},
    strong_points: [],
    weak_points: [],
    recent_trend: 'stable',
  }
  profile.courses.course_math = {
    course_id: 'course_math',
    course_name: '数学',
    mastery: {},
    strong_points: [],
    weak_points: [],
    recent_trend: 'stable',
  }
  profile.pending_updates = [
    { id: 'u1', course_id: 'course_physics', confidence: 0.8, status: 'pending' },
    { id: 'u2', course_id: 'course_math', confidence: 0.7, status: 'pending' },
  ]

  const cleared = clearLearnerCourseProfile(profile, 'course_physics')

  assert.equal(cleared.courses.course_physics, undefined)
  assert.equal(cleared.courses.course_math.course_name, '数学')
  assert.deepEqual(cleared.pending_updates, [
    { id: 'u2', course_id: 'course_math', confidence: 0.7, status: 'pending' },
  ])
})
