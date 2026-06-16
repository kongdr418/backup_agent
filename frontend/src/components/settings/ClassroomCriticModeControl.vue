<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-line bg-bg-subtle/60 px-4 py-3 text-sm text-ink-2">
      <div class="flex items-start gap-2">
        <Clock3 class="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <p>
          审查强度越高，生成耗时和模型调用量可能越大。该设置目前应用于智慧课堂的讲解、测验和简答评分。
        </p>
      </div>
    </div>

    <div class="grid gap-3" role="radiogroup" aria-label="智慧课堂防幻觉检查强度">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="w-full rounded-xl border px-4 py-3.5 text-left transition-colors"
        :class="modelValue === option.value
          ? 'border-accent/70 bg-accent/5 shadow-sm ring-1 ring-accent/10'
          : 'border-line bg-bg-surface hover:border-accent/30 hover:bg-bg-subtle/50'"
        role="radio"
        :aria-checked="modelValue === option.value"
        @click="emit('update:modelValue', option.value)"
      >
        <div class="flex items-start gap-3">
          <div
            class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            :class="modelValue === option.value ? 'bg-accent/10 text-accent' : 'bg-bg-subtle text-ink-3'"
          >
            <component :is="option.icon" class="h-4 w-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-ink-1">{{ option.label }}</span>
              <span
                v-if="option.recommended"
                class="rounded-full border border-accent/20 bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent"
              >
                推荐
              </span>
              <span class="text-xs text-ink-3">{{ option.speed }}</span>
            </div>
            <p class="mt-1 text-xs leading-5 text-ink-3">{{ option.description }}</p>
          </div>
          <span
            class="mt-1 h-4 w-4 shrink-0 rounded-full border-2"
            :class="modelValue === option.value ? 'border-[5px] border-accent' : 'border-line'"
          />
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Clock3, Gauge, ShieldCheck, ShieldAlert } from 'lucide-vue-next'
import type { ClassroomCriticMode } from '@/utils/classroomCriticConfig'

defineProps<{
  modelValue: ClassroomCriticMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ClassroomCriticMode]
}>()

const options = [
  {
    value: 'off',
    label: '关闭',
    speed: '速度最快',
    description: '关闭语义审查，仅保留生成流程本身的基础格式处理。',
    icon: Gauge,
  },
  {
    value: 'standard',
    label: '标准',
    speed: '轻微影响速度',
    description: '始终执行本地规则，仅在发现可疑内容时调用模型复核。',
    icon: ShieldCheck,
    recommended: true,
  },
  {
    value: 'strict',
    label: '严格',
    speed: '速度较慢',
    description: '每次都执行语义复核，可靠性更高，但会增加生成耗时和模型用量。',
    icon: ShieldAlert,
  },
] satisfies Array<{
  value: ClassroomCriticMode
  label: string
  speed: string
  description: string
  icon: typeof Gauge
  recommended?: boolean
}>
</script>
