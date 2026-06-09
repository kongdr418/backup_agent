import type { LearnerProfileUpdate } from '@/api/learnerProfile'

export function pendingProfileUpdates(
  updates: LearnerProfileUpdate[],
): LearnerProfileUpdate[] {
  return updates
    .filter((row) => row.status === 'pending')
    .slice()
    .sort((a, b) => {
      const confidenceDelta = (b.confidence || 0) - (a.confidence || 0)
      if (confidenceDelta !== 0) return confidenceDelta
      return (b.created_at || '').localeCompare(a.created_at || '')
    })
}

export function formatMasteryChange(before: number, after: number): string {
  const delta = Math.round(after - before)
  const suffix = delta > 0 ? `+${delta}` : delta < 0 ? `${delta}` : '持平'
  return `${Math.round(before)}% → ${Math.round(after)}%（${suffix}）`
}

export function trendLabel(trend: string): string {
  if (trend === 'improving') return '近期上升'
  if (trend === 'declining') return '近期下降'
  if (trend === 'stable') return '近期稳定'
  return '证据积累中'
}
