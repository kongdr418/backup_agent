export interface HighlightBox {
  x: number
  y: number
  width: number
  height: number
}

export interface HighlightTarget {
  id: string
  text: string
  kind?: string
  bbox: HighlightBox
}

export interface HighlightCue {
  target_id: string
  start_ratio: number
  end_ratio: number
  mode?: 'outline' | 'spotlight'
  label?: string
}

function clampRatio(value: unknown, fallback: number) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return fallback
  return Math.min(1, Math.max(0, numberValue))
}

export function normalizeHighlightCues(value: unknown): HighlightCue[] {
  if (!Array.isArray(value)) return []
  return value
    .map((row): HighlightCue | null => {
      if (!row || typeof row !== 'object') return null
      const item = row as Record<string, unknown>
      const targetId = String(item.target_id || '').trim()
      if (!targetId) return null
      const start = clampRatio(item.start_ratio, 0)
      const end = clampRatio(item.end_ratio, 1)
      if (end <= start) return null
      const mode = item.mode === 'spotlight' ? 'spotlight' : 'outline'
      const label = String(item.label || '').trim()
      return {
        target_id: targetId,
        start_ratio: start,
        end_ratio: end,
        mode,
        ...(label ? { label } : {}),
      }
    })
    .filter((row): row is HighlightCue => Boolean(row))
    .sort((a, b) => a.start_ratio - b.start_ratio)
}

export function activeHighlightCue(
  cues: HighlightCue[],
  currentTime: number,
  duration: number,
): HighlightCue | null {
  if (!cues.length) return null
  const ratio = duration > 0 && Number.isFinite(duration)
    ? Math.min(1, Math.max(0, currentTime / duration))
    : 0
  return (
    cues.find((cue) => ratio >= cue.start_ratio && ratio < cue.end_ratio)
    || cues[cues.length - 1]
  )
}

function roundedBox(box: DOMRect | { x: number; y: number; width: number; height: number }): HighlightBox {
  return {
    x: Math.round(box.x * 100) / 100,
    y: Math.round(box.y * 100) / 100,
    width: Math.round(box.width * 100) / 100,
    height: Math.round(box.height * 100) / 100,
  }
}

function boxFromRenderedRect(svg: SVGSVGElement, node: SVGGraphicsElement): HighlightBox | null {
  const svgRect = svg.getBoundingClientRect?.()
  const nodeRect = node.getBoundingClientRect?.()
  const viewBox = svg.viewBox?.baseVal
  if (!svgRect || !nodeRect || !viewBox?.width || !viewBox?.height || !svgRect.width || !svgRect.height) {
    return null
  }
  return roundedBox({
    x: ((nodeRect.left - svgRect.left) / svgRect.width) * viewBox.width,
    y: ((nodeRect.top - svgRect.top) / svgRect.height) * viewBox.height,
    width: (nodeRect.width / svgRect.width) * viewBox.width,
    height: (nodeRect.height / svgRect.height) * viewBox.height,
  })
}

function measuredNodeBox(svg: SVGSVGElement, node: SVGGraphicsElement): HighlightBox | null {
  try {
    const rendered = boxFromRenderedRect(svg, node)
    if (rendered && rendered.width > 0 && rendered.height > 0) return rendered
  } catch {
    // getBoundingClientRect may be missing in tests or fail for detached nodes.
  }
  try {
    const box = node.getBBox()
    if (box.width > 0 && box.height > 0) return roundedBox(box)
  } catch {
    // getBBox can throw when the SVG is detached or hidden.
  }
  return null
}

function svgTextNodes(svg: SVGSVGElement): Array<SVGGraphicsElement & { textContent: string | null }> {
  return Array.from(svg.querySelectorAll('text,tspan')) as Array<SVGGraphicsElement & { textContent: string | null }>
}

export function fallbackHighlightTargetsFromSvgElement(svg: SVGSVGElement | null, limit = 12): HighlightTarget[] {
  if (!svg) return []
  const targets: HighlightTarget[] = []
  const seen = new Set<string>()
  const nodes = svgTextNodes(svg)
  for (const node of nodes) {
    const text = (node.textContent || '').replace(/\s+/g, ' ').trim()
    if (text.length < 2 || seen.has(text)) continue
    const box = measuredNodeBox(svg, node)
    if (!box) continue
    seen.add(text)
    targets.push({
      id: `fallback_${String(targets.length + 1).padStart(3, '0')}`,
      text,
      kind: 'text',
      bbox: box,
    })
    if (targets.length >= limit) break
  }
  return targets
}

export function resolveHighlightTargetsFromSvgElement(
  targets: HighlightTarget[],
  svg: SVGSVGElement | null,
): HighlightTarget[] {
  if (!svg || !targets.length) return targets
  const nodes = svgTextNodes(svg).map((node) => ({
    node,
    text: (node.textContent || '').replace(/\s+/g, ' ').trim(),
  }))
  const used = new Set<SVGGraphicsElement>()
  return targets.map((target) => {
    const exact = nodes.find((item) => item.text === target.text && !used.has(item.node))
    const partial = exact || nodes.find((item) => (
      item.text.includes(target.text) || target.text.includes(item.text)
    ) && !used.has(item.node))
    if (!partial) return target
    const box = measuredNodeBox(svg, partial.node)
    if (!box) return target
    used.add(partial.node)
    return { ...target, bbox: box }
  })
}
