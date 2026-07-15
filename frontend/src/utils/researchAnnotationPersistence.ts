export type PersistedAnnotationSource = 'ai' | 'final' | ''

export type PersistedAnnotation = Record<string, unknown> & {
  output_id_or_replay_id?: string
  output_id?: string
  created_at?: string
  timestamp?: string
  severity?: string
  memory_ids?: unknown[]
}

export type AnnotationByOutputId<TAnnotation extends PersistedAnnotation> = Record<string, TAnnotation>

function outputIdOf(annotation: PersistedAnnotation) {
  return String(annotation.output_id_or_replay_id || annotation.output_id || '')
}

function timeOf(annotation: PersistedAnnotation) {
  return String(annotation.created_at || annotation.timestamp || '')
}

export function buildLatestAnnotationByOutputId<TAnnotation extends PersistedAnnotation>(
  annotations: TAnnotation[],
): AnnotationByOutputId<TAnnotation> {
  return annotations.reduce<AnnotationByOutputId<TAnnotation>>((latest, annotation) => {
    const outputId = outputIdOf(annotation)
    if (!outputId) return latest
    const existing = latest[outputId]
    if (!existing || timeOf(annotation) >= timeOf(existing)) {
      latest[outputId] = annotation
    }
    return latest
  }, {})
}

export function clonePersistedAnnotation<TAnnotation extends PersistedAnnotation>(
  annotation: TAnnotation,
): TAnnotation {
  return {
    ...annotation,
    memory_ids: Array.isArray(annotation.memory_ids) ? [...annotation.memory_ids] : [],
  }
}

export function pickPersistedAnnotation<TAnnotation extends PersistedAnnotation>(
  outputId: string,
  aiByOutputId: AnnotationByOutputId<TAnnotation>,
  finalByOutputId: AnnotationByOutputId<TAnnotation>,
): { source: PersistedAnnotationSource; annotation: TAnnotation | null } {
  const finalAnnotation = finalByOutputId[outputId]
  if (finalAnnotation) {
    return { source: 'final', annotation: clonePersistedAnnotation(finalAnnotation) }
  }
  const aiAnnotation = aiByOutputId[outputId]
  if (aiAnnotation) {
    return { source: 'ai', annotation: clonePersistedAnnotation(aiAnnotation) }
  }
  return { source: '', annotation: null }
}
