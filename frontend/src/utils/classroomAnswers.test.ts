import test from 'node:test'
import assert from 'node:assert/strict'

import { buildPlayerAnswerState } from './classroomAnswers.ts'

test('hydrates quiz answers and evaluation from classroom answers_record', () => {
  const result = buildPlayerAnswerState({
    id: 'cls_001',
    title: '测试课堂',
    topic: '测试主题',
    status: 'ready',
    scenes: [],
    answers_record: {
      scenes: {
        scene_quiz_001: {
          answers: { q1: ['A'] },
          evaluation: {
            score: 100,
            correct: 1,
            total: 1,
            earned_points: 1,
            total_points: 1,
            results: [
              {
                question_id: 'q1',
                correct: true,
                your_answer: ['A'],
                correct_answer: ['A'],
                analysis: 'A 是正确答案。',
              },
            ],
          },
        },
      },
    },
  })

  assert.deepEqual(result.answersByScene.scene_quiz_001, { q1: ['A'] })
  assert.equal(result.quizResultsByScene.scene_quiz_001?.score, 100)
})
