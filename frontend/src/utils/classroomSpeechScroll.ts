export interface SpeechAutoScrollInput {
  currentScrollTop: number
  containerHeight: number
  contentHeight: number
  segmentTop: number
  segmentHeight: number
}

const VIEWPORT_MARGIN = 10
const SEGMENT_ANCHOR_RATIO = 0.35

export function computeSpeechAutoScrollTop(input: SpeechAutoScrollInput) {
  const {
    currentScrollTop,
    containerHeight,
    contentHeight,
    segmentTop,
    segmentHeight,
  } = input

  if (!(containerHeight > 0) || !(contentHeight > containerHeight) || !(segmentHeight > 0)) {
    return null
  }

  const viewportTop = currentScrollTop
  const viewportBottom = currentScrollTop + containerHeight
  const segmentBottom = segmentTop + segmentHeight

  if (
    segmentTop >= viewportTop + VIEWPORT_MARGIN
    && segmentBottom <= viewportBottom - VIEWPORT_MARGIN
  ) {
    return null
  }

  const segmentCenter = segmentTop + segmentHeight / 2
  const anchorY = containerHeight * SEGMENT_ANCHOR_RATIO
  const maxScrollTop = Math.max(0, contentHeight - containerHeight)
  const targetTop = Math.max(0, Math.min(maxScrollTop, segmentCenter - anchorY))
  return Math.round(targetTop)
}
