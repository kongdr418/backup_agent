import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCoursewareClassroomSeed } from './classroomCourseware.ts'
import type { GeneratedFile } from '../types/index.ts'

function file(overrides: Partial<GeneratedFile>): GeneratedFile {
  const base: GeneratedFile = {
    id: 'svg_ppt_job_123',
    name: '物理：牛顿第一定律.pptx',
    type: 'ppt',
    type_label: 'PPT',
    path: '/tmp/物理：牛顿第一定律.pptx',
    size: 1024,
    size_formatted: '1.0 KB',
    created: '2026-06-12 12:00',
    job_id: 'job_123',
  }
  return { ...base, ...overrides } as GeneratedFile
}

test('uses selected PPT name as both topic and course fallback', () => {
  const seed = buildCoursewareClassroomSeed({
    selectedPptJobId: 'job_123',
    files: [file({})],
    topic: '',
    course: '',
  })

  assert.deepEqual(seed, {
    topic: '物理：牛顿第一定律',
    course: '物理：牛顿第一定律',
  })
})

test('preserves manually entered topic and course over selected PPT fallback', () => {
  const seed = buildCoursewareClassroomSeed({
    selectedPptJobId: 'job_123',
    files: [file({})],
    topic: '惯性实验复习',
    course: '八年级物理',
  })

  assert.deepEqual(seed, {
    topic: '惯性实验复习',
    course: '八年级物理',
  })
})
