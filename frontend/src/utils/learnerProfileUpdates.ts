import type { LearnerProfileUpdate, LearnerRecommendation } from '@/api/learnerProfile'

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

const PROFILE_TERM_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bProfile Agent\b/gi, '个性化学习助手'],
  [/\bevidence_ids?\b/gi, '学习证据'],
  [/\bpending_updates?\b/gi, '学习分析建议'],
  [/\bgeneration_strategy\b/gi, '个性化学习方案'],
  [/知识迁移能力/g, '知识应用情况'],
  [/知识迁移/g, '知识应用'],
  [/错误模式/g, '学习卡点'],
]

const TREND_LABELS: Record<string, string> = {
  improving: '近期上升',
  declining: '近期下降',
  stable: '近期稳定',
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

export function learnerFacingTransferLevel(level: string | undefined): string {
  return TRANSFER_LABELS[level || ''] || '完成更多练习后生成分析'
}

export function learnerFacingErrorPattern(pattern: string | undefined): string {
  return ERROR_LABELS[pattern || ''] || '等待进一步分析'
}

export function sanitizeLearnerFacingText(text: string | undefined): string {
  let next = String(text || '').trim()
  for (const [pattern, replacement] of PROFILE_TERM_REPLACEMENTS) {
    next = next.replace(pattern, replacement)
  }
  for (const [key, label] of Object.entries(TREND_LABELS)) {
    next = next.replace(new RegExp(`\\b${key}\\b`, 'g'), label)
  }
  for (const [key, label] of Object.entries(TRANSFER_LABELS)) {
    next = next.replace(new RegExp(`\\b${key}\\b`, 'g'), label)
  }
  for (const [key, label] of Object.entries(ERROR_LABELS)) {
    next = next.replace(new RegExp(`\\b${key}\\b`, 'g'), label)
  }
  return next.replace(/([为是：，。；、])\s+(?=[\u4e00-\u9fa5])/g, '$1')
}

export function formatProfileUpdateReason(update: LearnerProfileUpdate): string {
  const evidenceCount = update.evidence_ids?.length || 0
  if (update.type === 'transfer_ability_update') {
    const after = update.after as { level?: string } | undefined
    const level = learnerFacingTransferLevel(after?.level)
    if (evidenceCount > 0) {
      return `根据最近 ${evidenceCount} 次练习表现，系统判断你目前${level}。`
    }
    return `系统判断你目前${level}。`
  }
  if (update.type === 'error_pattern_update') {
    const pattern = learnerFacingErrorPattern(update.trait_key)
    if (evidenceCount > 0) {
      return `根据最近 ${evidenceCount} 次学习表现，系统发现你可能${pattern}。`
    }
    return `系统发现你可能${pattern}。`
  }
  const sanitized = sanitizeLearnerFacingText(update.reason)
  return sanitized || '系统根据近期学习证据提出此建议。'
}

export function formatRecommendationReason(recommendation: LearnerRecommendation): string {
  return sanitizeLearnerFacingText(recommendation.reason)
}

export function analysisConfidenceLabel(confidence: number): string {
  if (confidence >= 0.85) return '判断依据较充分'
  if (confidence >= 0.6) return '判断依据一般'
  return '初步判断'
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
  if (TREND_LABELS[trend]) return TREND_LABELS[trend]
  return '完成更多练习后生成分析'
}
