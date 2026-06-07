import test from 'node:test'
import assert from 'node:assert/strict'

import {
  activeHighlightCue,
  fallbackHighlightTargetsFromSvgElement,
  normalizeHighlightCues,
  resolveHighlightTargetsFromSvgElement,
} from './classroomHighlight.ts'

test('normalizes cues by clamping ratios and dropping invalid targets', () => {
  const result = normalizeHighlightCues([
    { target_id: 'hl_002', start_ratio: 0.6, end_ratio: 1.4, mode: 'laser', label: '后半段' },
    { target_id: '', start_ratio: 0, end_ratio: 0.2 },
    { target_id: 'hl_001', start_ratio: -0.2, end_ratio: 0.5, mode: 'spotlight', label: '前半段' },
  ])

  assert.deepEqual(result, [
    { target_id: 'hl_001', start_ratio: 0, end_ratio: 0.5, mode: 'spotlight', label: '前半段' },
    { target_id: 'hl_002', start_ratio: 0.6, end_ratio: 1, mode: 'outline', label: '后半段' },
  ])
})

test('selects active cue from playback ratio', () => {
  const cues = normalizeHighlightCues([
    { target_id: 'hl_001', start_ratio: 0, end_ratio: 0.4, mode: 'spotlight' },
    { target_id: 'hl_002', start_ratio: 0.4, end_ratio: 1, mode: 'outline' },
  ])

  assert.equal(activeHighlightCue(cues, 12, 30)?.target_id, 'hl_002')
  assert.equal(activeHighlightCue(cues, 2, 30)?.target_id, 'hl_001')
  assert.equal(activeHighlightCue(cues, 31, 30)?.target_id, 'hl_002')
})

test('extracts fallback highlight targets from visible svg text elements', () => {
  const svg = {
    querySelectorAll: () => [
      {
        textContent: '依赖注入',
        getBBox: () => ({ x: 80, y: 90, width: 120, height: 32 }),
      },
      {
        textContent: 'Bean 创建流程',
        getBBox: () => ({ x: 120, y: 180, width: 180, height: 28 }),
      },
    ],
  } as unknown as SVGSVGElement

  const targets = fallbackHighlightTargetsFromSvgElement(svg)

  assert.deepEqual(targets, [
    { id: 'fallback_001', text: '依赖注入', kind: 'text', bbox: { x: 80, y: 90, width: 120, height: 32 } },
    { id: 'fallback_002', text: 'Bean 创建流程', kind: 'text', bbox: { x: 120, y: 180, width: 180, height: 28 } },
  ])
})

test('resolves backend targets with actual rendered svg boxes', () => {
  const svg = {
    viewBox: { baseVal: { width: 1000, height: 562 } },
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 500, height: 281 }),
    querySelectorAll: () => [
      {
        textContent: '计算机视觉概述',
        getBoundingClientRect: () => ({ left: 110, top: 70, width: 90, height: 20 }),
        getBBox: () => ({ x: 999, y: 999, width: 1, height: 1 }),
      },
    ],
  } as unknown as SVGSVGElement

  const targets = resolveHighlightTargetsFromSvgElement(
    [
      {
        id: 'hl_001',
        text: '计算机视觉概述',
        kind: 'text',
        bbox: { x: 0, y: 0, width: 10, height: 10 },
      },
    ],
    svg,
  )

  assert.deepEqual(targets, [
    {
      id: 'hl_001',
      text: '计算机视觉概述',
      kind: 'text',
      bbox: { x: 200, y: 100, width: 180, height: 40 },
    },
  ])
})
