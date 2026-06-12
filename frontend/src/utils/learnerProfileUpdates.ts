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

const ERROR_LABELS: Record<string, string> = {
  concept_confusion: '容易混淆相近概念',
  prerequisite_gap: '建议先补充相关基础知识',
  procedural_error: '解题步骤还不稳定',
  application_failure: '将知识用于新问题时有困难',
  careless_error: '需要加强题目条件检查',
  expression_gap: '思路基本正确，但表达不够完整',
}

const COGNITIVE_LABELS: Record<string, string> = {
  visual_structure: '图示结构',
  example_based: '案例理解',
  step_by_step: '步骤推导',
  comparison: '对比辨析',
  text_summary: '文字概括',
  hands_on: '实践操作',
}

const TRANSFER_LABELS: Record<string, string> = {
  unobserved: '完成更多练习后生成分析',
  recall: '已能理解基础概念',
  near_transfer: '能完成相似类型的问题',
  far_transfer: '能解决新的应用问题',
  integrated_problem_solving: '能综合运用多个知识点',
}

export function formatProfileUpdateChange(update: LearnerProfileUpdate): string {
  if (update.type === 'mastery_adjustment') {
    return formatMasteryChange(
      Number(update.before || 0),
      Number(update.after || 0),
    )
  }
  if (update.type === 'error_pattern_update') {
    return `当前学习卡点：${ERROR_LABELS[update.trait_key || ''] || update.trait_key || '等待进一步分析'}`
  }
  if (update.type === 'transfer_ability_update') {
    const after = update.after as { level?: string } | undefined
    const label = TRANSFER_LABELS[after?.level || ''] || after?.level || '完成更多练习后生成分析'
    return `知识应用情况：${label}`
  }
  if (update.type === 'cognitive_preference_update') {
    return `认知偏好：${COGNITIVE_LABELS[update.trait_key || ''] || update.trait_key || '待归类'}`
  }
  if (update.type === 'interest_direction_update') {
    const after = update.after as { label?: string } | undefined
    return `兴趣方向：${after?.label || update.trait_key || '待归类'}`
  }
  return '个性化学习建议'
}

export function profileUpdateTitle(update: LearnerProfileUpdate): string {
  if (update.type === 'mastery_adjustment') return update.knowledge_point_name || '知识点掌握度'
  if (update.type === 'error_pattern_update') return '当前学习卡点'
  if (update.type === 'transfer_ability_update') return '知识应用情况'
  if (update.type === 'cognitive_preference_update') return '认知偏好'
  if (update.type === 'interest_direction_update') return '兴趣方向'
  return '个性化学习'
}

export function trendLabel(trend: string): string {
  if (trend === 'improving') return '近期上升'
  if (trend === 'declining') return '近期下降'
  if (trend === 'stable') return '近期稳定'
  return '完成更多练习后生成分析'
}
