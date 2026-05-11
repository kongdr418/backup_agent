<template>
  <div class="vac-wrap">
    <CardShell
      hue="settings"
      :icon="Video"
      :title="title"
      :subtitle="subtitle"
      :stats="stats"
      :is-expanded="isExpanded"
      @toggle="$emit('toggle')"
    />
    <!-- Script text preview (collapsed) -->
    <div v-if="scriptText && !isExpanded" class="vac-script-preview">
      <div class="vac-script-label">
        <ScrollText class="w-3 h-3" />
        <span>脚本内容</span>
      </div>
      <div class="vac-script-text">{{ scriptPreview }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { Video, ScrollText } from 'lucide-vue-next'
import CardShell from './CardShell.vue'
import { useMediaRestore } from '@/composables/useMediaRestore'

const props = defineProps<{ data?: Record<string, unknown>; isExpanded?: boolean }>()
defineEmits<{ toggle: [] }>()

const dataRef = toRef(props, 'data')
const { audioBase64: restoredAudio } = useMediaRestore(dataRef)

const voiceoverText = computed(() => (props.data?.voiceoverText as string) || '')
const scriptText = computed(() => (props.data?.video_script as string) || '')

const title = computed(() => {
  if (scriptText.value && restoredAudio.value) return '短视频脚本 + 配音'
  if (scriptText.value) return '短视频脚本'
  return 'AI 配音'
})

const subtitle = computed(() => {
  if (voiceoverText.value) {
    return voiceoverText.value.split('\n').find((l) => l.trim())?.slice(0, 40) || '配音内容'
  }
  return restoredAudio.value ? '配音已生成' : '合成中...'
})

const stats = computed(() => {
  const parts: string[] = []
  if (scriptText.value) parts.push(`${scriptText.value.length} 字脚本`)
  if (restoredAudio.value) parts.push('音频可播放')
  return parts.join(' · ')
})

const scriptPreview = computed(() => {
  const text = scriptText.value
  if (!text) return ''
  return text.length > 150 ? text.slice(0, 150) + '…' : text
})
</script>

<style scoped>
.vac-wrap {
  max-width: 480px;
}
.vac-script-preview {
  margin-top: 8px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
}
.vac-script-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-weight: 500;
  color: rgb(var(--ink-3-rgb));
  margin-bottom: 6px;
}
.vac-script-text {
  font-size: 12.5px;
  line-height: 1.6;
  color: rgb(var(--ink-2-rgb));
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}
</style>
