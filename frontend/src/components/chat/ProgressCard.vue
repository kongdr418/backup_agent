<template>
  <div class="progress-card">
    <div class="progress-header">
      <span class="kind-icon" :class="kindColor">
        <component :is="kindIcon" class="w-4 h-4" />
      </span>
      <div class="progress-info">
        <span class="progress-label">{{ data.label || '生成中' }}</span>
        <span v-if="data.detail" class="progress-detail">{{ data.detail }}</span>
      </div>
    </div>

    <div class="progress-track">
      <div class="progress-fill" :style="{ width: percent + '%' }" />
    </div>

    <div class="progress-footer">
      <span class="percent-text">{{ percent }}%</span>
      <span v-if="elapsed" class="elapsed-text">{{ elapsed }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import {
  FileText,
  Mic,
  Image,
  Video,
  Layers,
  BookOpen,
  Brain,
  Sparkles,
} from 'lucide-vue-next'

interface ProgressData {
  stage?: string
  kind?: string
  percent?: number
  label?: string
  detail?: string
  format?: string
  startedAt?: number
}

const props = defineProps<{ data: ProgressData }>()

const percent = computed(() => Math.min(100, Math.max(0, props.data.percent || 0)))

const kindMap: Record<string, { icon: typeof FileText; color: string }> = {
  outline: { icon: FileText, color: 'kind-blue' },
  lecture: { icon: BookOpen, color: 'kind-blue' },
  speech: { icon: Mic, color: 'kind-blue' },
  exercise: { icon: Layers, color: 'kind-orange' },
  quiz: { icon: Brain, color: 'kind-purple' },
  card: { icon: Sparkles, color: 'kind-purple' },
  mindmap: { icon: Sparkles, color: 'kind-green' },
  graphic: { icon: Image, color: 'kind-rose' },
  video: { icon: Video, color: 'kind-rose' },
}

const kindIcon = computed(() => {
  const k = props.data.kind || 'outline'
  return kindMap[k]?.icon || FileText
})
const kindColor = computed(() => {
  const k = props.data.kind || 'outline'
  return kindMap[k]?.color || 'kind-blue'
})

const elapsed = ref('')
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  if (!props.data.startedAt) return
  const update = () => {
    const secs = Math.floor((Date.now() - props.data.startedAt!) / 1000)
    const m = Math.floor(secs / 60)
    const s = secs % 60
    elapsed.value = m > 0 ? `已用 ${m}m${s}s` : `已用 ${s}s`
  }
  update()
  timer = setInterval(update, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.progress-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 16px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.04);
  width: 100%;
  max-width: 420px;
  min-width: 280px;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kind-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kind-blue { background: rgb(var(--accent-rgb) / 0.12); color: rgb(var(--accent-rgb)); }
.kind-purple { background: rgb(var(--accent-purple-rgb) / 0.12); color: rgb(var(--accent-purple-rgb)); }
.kind-orange { background: rgb(var(--accent-orange-rgb) / 0.12); color: rgb(var(--accent-orange-rgb)); }
.kind-rose { background: rgb(var(--accent-rose-rgb) / 0.12); color: rgb(var(--accent-rose-rgb)); }
.kind-green { background: rgb(var(--accent-green-rgb) / 0.12); color: rgb(var(--accent-green-rgb)); }

.progress-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.progress-label {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-detail {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-track {
  height: 5px;
  background: rgb(var(--bg-subtle-rgb));
  border-radius: 99px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, rgb(var(--accent-rgb)), rgb(90 200 250));
  transition: width 400ms cubic-bezier(0.2, 0.8, 0.2, 1);
  position: relative;
}
.progress-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgb(255 255 255 / 0.35), transparent);
  animation: shimmer 1.8s ease-in-out infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.progress-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.percent-text {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--accent-rgb));
  font-feature-settings: 'tnum';
}

.elapsed-text {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
}
</style>
