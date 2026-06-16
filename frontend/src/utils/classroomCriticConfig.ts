import type { ContentSettings } from '@/types'

export type ClassroomCriticMode = ContentSettings['classroom_critic_mode']

const VALID_MODES = new Set<ClassroomCriticMode>(['off', 'standard', 'strict'])

export function normalizeClassroomCriticMode(value: unknown): ClassroomCriticMode {
  const mode = String(value || 'standard').trim().toLowerCase() as ClassroomCriticMode
  return VALID_MODES.has(mode) ? mode : 'standard'
}

export function buildClassroomCriticPayload(
  settings: Partial<Pick<ContentSettings, 'classroom_critic_mode'>>,
): { critic_mode: ClassroomCriticMode } {
  return {
    critic_mode: normalizeClassroomCriticMode(settings.classroom_critic_mode),
  }
}
