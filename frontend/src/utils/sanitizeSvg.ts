import DOMPurify from 'dompurify'

export function sanitizeSvg(svg: string | null | undefined): string {
  if (!svg) return ''
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'foreignObject', 'iframe', 'object', 'embed'],
  })
}
