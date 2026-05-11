<template>
  <CardShell
    :hue="meta.hue"
    :icon="meta.icon"
    :title="title"
    :subtitle="subtitle"
    :stats="stats"
    :is-expanded="isExpanded"
    @toggle="$emit('toggle')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  GraduationCap,
  ClipboardList,
  Lightbulb,
  Network,
  Megaphone,
  ScrollText,
  BookOpen,
  ImageIcon,
  FileText,
} from 'lucide-vue-next'
import CardShell from './CardShell.vue'

const props = defineProps<{ data?: Record<string, unknown>; isExpanded?: boolean }>()
defineEmits<{ toggle: [] }>()

const completeType = computed(() => (props.data?.completeType as string) || '')
const topic = computed(() => (props.data?.topic as string) || '')
const content = computed(() => (props.data?.content as string) || '')

const TYPE_MAP: Record<string, { label: string; hue: 'chat'|'ppt'|'library'|'memory'|'settings'|'dashboard'; icon: unknown }> = {
  exercise_complete: { label: '习题集', hue: 'chat', icon: GraduationCap },
  quiz_complete: { label: '课堂测验', hue: 'ppt', icon: ClipboardList },
  knowledge_card_complete: { label: '知识卡片', hue: 'library', icon: Lightbulb },
  mindmap_complete: { label: '思维导图', hue: 'memory', icon: Network },
  speech_complete: { label: '讲稿', hue: 'settings', icon: Megaphone },
  course_outline_complete: { label: '课程大纲', hue: 'dashboard', icon: ScrollText },
  lecture_complete: { label: '讲义', hue: 'chat', icon: BookOpen },
  content_complete: { label: '图文内容', hue: 'memory', icon: ImageIcon },
}

const meta = computed(() => TYPE_MAP[completeType.value] || { label: '生成结果', hue: 'chat' as const, icon: FileText })

const title = computed(() => meta.value.label)
const subtitle = computed(() => topic.value || '')

// 字数 / 文件大小展示
const stats = computed(() => {
  const parts: string[] = []
  if (content.value) {
    const len = content.value.length
    if (len >= 1000) parts.push(`${(len / 1000).toFixed(1)}k 字`)
    else parts.push(`${len} 字`)
  }
  return parts.join(' · ')
})
</script>
