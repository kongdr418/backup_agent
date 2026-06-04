export function isClassroomCancelError(error: unknown) {
  if (!(error instanceof Error)) return false
  const message = error.message.toLowerCase()
  return (
    error.name === 'CanceledError' ||
    error.name === 'AbortError' ||
    message.includes('canceled') ||
    message.includes('cancelled') ||
    error.message.includes('课堂生成已停止')
  )
}

export function isClassroomGenerationMissingError(error: unknown) {
  if (!error || typeof error !== 'object') return false
  const response = (error as { response?: { status?: number } }).response
  return response?.status === 404
}
