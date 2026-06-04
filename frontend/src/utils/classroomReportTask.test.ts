import test from 'node:test'
import assert from 'node:assert/strict'

import { buildNextLessonQuery, resolveReportTaskAction } from './classroomReportTask.ts'

test('resolves complete_quizzes task to the first unanswered quiz scene', () => {
  const action = resolveReportTaskAction(
    {
      id: 'task_complete_quizzes',
      type: 'complete_quizzes',
      title: '先完成课堂测验',
      description: '',
      priority: 'high',
      knowledge_points: [],
      target_scene_ids: [],
      action_label: '回到测验',
    },
    {
      orderedScenes: [
        { id: 'scene_slide_001', type: 'slide' },
        { id: 'scene_quiz_001', type: 'quiz' },
        { id: 'scene_slide_002', type: 'slide' },
        { id: 'scene_quiz_002', type: 'quiz' },
      ],
      answeredSceneIds: ['scene_quiz_001'],
      topic: 'Spring Boot',
      course: 'Spring Boot 入门',
      studentProfile: {
        basis: '零基础',
        goal: '考试通过',
        style: '图解+案例',
        difficulty: '基础',
      },
      report: null,
    },
  )

  assert.deepEqual(action, {
    kind: 'scene',
    sceneId: 'scene_quiz_002',
  })
})

test('resolves review_weak_points task to the first target slide scene', () => {
  const action = resolveReportTaskAction(
    {
      id: 'task_review_weak_points',
      type: 'review_weak_points',
      title: '复听薄弱知识点',
      description: '',
      priority: 'high',
      knowledge_points: ['依赖注入'],
      target_scene_ids: ['scene_slide_003', 'scene_slide_004'],
      action_label: '复听讲解',
    },
    {
      orderedScenes: [],
      answeredSceneIds: [],
      topic: 'Spring Boot',
      course: 'Spring Boot 入门',
      studentProfile: {
        basis: '零基础',
        goal: '考试通过',
        style: '图解+案例',
        difficulty: '基础',
      },
      report: null,
    },
  )

  assert.deepEqual(action, {
    kind: 'scene',
    sceneId: 'scene_slide_003',
  })
})

test('builds next-lesson query with report context and learner profile', () => {
  const query = buildNextLessonQuery({
    topic: 'Spring Boot',
    course: 'Spring Boot 入门',
    studentProfile: {
      basis: '有基础',
      goal: '项目实战',
      style: '步骤推导',
      difficulty: '中等',
    },
    report: {
      weak_points: ['依赖注入', '自动配置'],
      strong_points: ['项目结构'],
      next_recommendation: '下一节重点补足依赖注入，并进入配置实战。',
    },
  })

  assert.equal(query.from, 'interactive-classroom')
  assert.equal(query.topic, 'Spring Boot')
  assert.equal(query.course, 'Spring Boot 入门')
  assert.equal(query.basis, '有基础')
  assert.equal(query.goal, '项目实战')
  assert.equal(query.style, '步骤推导')
  assert.equal(query.difficulty, '中等')
  assert.equal(query.weak_points, '依赖注入||自动配置')
  assert.equal(query.strong_points, '项目结构')
  assert.match(query.next_recommendation, /下一节重点补足依赖注入/)
})
