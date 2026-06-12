import type { PptGenerateParams } from '../types/index'

export function applyClassroomPptDraft(
  params: PptGenerateParams,
  draft: Pick<PptGenerateParams, 'topic' | 'course' | 'notes'>,
): PptGenerateParams {
  return {
    ...params,
    topic: draft.topic,
    course: draft.course,
    notes: draft.notes,
  }
}

export function resetPptDraftFields(params: PptGenerateParams): PptGenerateParams {
  return {
    ...params,
    topic: '',
    course: undefined,
    notes: '',
    source: undefined,
  }
}
