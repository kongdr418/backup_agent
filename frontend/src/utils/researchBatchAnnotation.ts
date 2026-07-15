export interface ResearchBatchAnnotationState<TAnnotation = unknown> {
  total: number
  completed: number
  succeeded: number
  failed: number
  currentOutputId: string
  lastAnnotation: TAnnotation | null
  errors: Array<{ outputId: string; message: string }>
}

export interface RunResearchBatchAnnotationOptions<TAnnotation = unknown> {
  outputIds: string[]
  annotate: (outputId: string) => Promise<TAnnotation>
  onProgress?: (state: ResearchBatchAnnotationState<TAnnotation>) => void
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'AI 标注失败'
}

export async function runResearchBatchAnnotation<TAnnotation = unknown>({
  outputIds,
  annotate,
  onProgress,
}: RunResearchBatchAnnotationOptions<TAnnotation>): Promise<ResearchBatchAnnotationState<TAnnotation>> {
  const state: ResearchBatchAnnotationState<TAnnotation> = {
    total: outputIds.length,
    completed: 0,
    succeeded: 0,
    failed: 0,
    currentOutputId: '',
    lastAnnotation: null,
    errors: [],
  }

  for (const outputId of outputIds) {
    state.currentOutputId = outputId
    try {
      state.lastAnnotation = await annotate(outputId)
      state.succeeded += 1
    } catch (error) {
      state.failed += 1
      state.errors.push({ outputId, message: errorMessage(error) })
    } finally {
      state.completed += 1
      onProgress?.({ ...state, errors: [...state.errors] })
    }
  }

  state.currentOutputId = ''
  return state
}
