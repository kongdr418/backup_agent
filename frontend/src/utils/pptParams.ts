import type { PptGenerateParams } from '../types/index'

export function resetPptDraftFields(params: PptGenerateParams): PptGenerateParams {
  return {
    ...params,
    topic: '',
    notes: '',
    source: undefined,
  }
}
