type SpeechCueLike = {
  target_id?: string
  start_ratio?: number
  end_ratio?: number
  label?: string
}

export interface SpeechParagraph {
  text: string
  start_ratio: number
  end_ratio: number
}

const SPEECH_ENTRY_DELAY_SECONDS = 0.35

function normalizeText(value: unknown) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function roundRatio(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000
}

function splitSpeechText(text: string) {
  const normalized = String(text || '').trim()
  if (!normalized) return []

  const lineSegments = normalized
    .split(/\n+/)
    .map((item) => normalizeText(item))
    .filter(Boolean)
  if (lineSegments.length > 1) return lineSegments

  const sentenceSegments = normalized
    .match(/[^。！？!?；;\n]+[。！？!?；;]?/g)
    ?.map((item) => normalizeText(item))
    .filter(Boolean)

  return sentenceSegments?.length ? sentenceSegments : [normalizeText(normalized)]
}

export function buildSpeechParagraphs(
  speechText: string,
  cues: SpeechCueLike[],
): SpeechParagraph[] {
  const cueParagraphs = Array.isArray(cues)
    ? cues
      .map((cue): SpeechParagraph | null => {
        const text = normalizeText(cue.label)
        const start = Number(cue.start_ratio)
        const end = Number(cue.end_ratio)
        if (!text || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null
        return {
          text,
          start_ratio: roundRatio(Math.max(0, Math.min(1, start))),
          end_ratio: roundRatio(Math.max(0, Math.min(1, end))),
        }
      })
      .filter((item): item is SpeechParagraph => Boolean(item))
    : []
  if (cueParagraphs.length) return cueParagraphs

  const segments = splitSpeechText(speechText)
  if (!segments.length) return []
  return segments.map((text, index) => ({
    text,
    start_ratio: roundRatio(index / segments.length),
    end_ratio: roundRatio(index === segments.length - 1 ? 1 : (index + 1) / segments.length),
  }))
}

export function activeSpeechParagraphIndex(
  paragraphs: SpeechParagraph[],
  currentTime: number,
  duration: number,
) {
  if (!paragraphs.length) return -1
  if (!Number.isFinite(currentTime) || currentTime < SPEECH_ENTRY_DELAY_SECONDS) return -1
  if (!(duration > 0) || !Number.isFinite(duration) || currentTime > duration) return -1
  const ratio = Math.min(1, Math.max(0, currentTime / duration))
  return paragraphs.findIndex((item) => ratio >= item.start_ratio && ratio < item.end_ratio)
}
