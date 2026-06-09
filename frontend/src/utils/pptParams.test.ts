import test from 'node:test'
import assert from 'node:assert/strict'

import { resetPptDraftFields } from './pptParams.ts'
import type { PptGenerateParams } from '../types/index.ts'

test('clears classroom draft topic and notes while preserving generation options', () => {
  const params: PptGenerateParams = {
    topic: '无监督学习：从数据中发现隐藏规律补强与应用',
    notes: '一轮同类练习。\n请在 PPT 前 1-2 页简要总结上一堂课讲了什么与学生表现。',
    source: 'interactive-classroom',
    language: 'zh',
    num_slides: 8,
    style: 'education',
    detail_level: 'detailed',
    canvas_format: 'ppt169',
    repair_enabled: true,
  }

  const next = resetPptDraftFields(params)

  assert.equal(next.topic, '')
  assert.equal(next.notes, '')
  assert.equal(next.source, undefined)
  assert.equal(next.language, 'zh')
  assert.equal(next.num_slides, 8)
  assert.equal(next.style, 'education')
  assert.equal(next.detail_level, 'detailed')
  assert.equal(next.canvas_format, 'ppt169')
  assert.equal(next.repair_enabled, true)
})
