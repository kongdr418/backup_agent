<template>
  <div class="download-card">
    <div class="card-icon" :class="colorClass">
      <component :is="icon" class="w-8 h-8" />
    </div>
    <div class="card-info">
      <div class="card-name">{{ name }}</div>
      <div class="card-meta">
        <span v-if="size">{{ size }}</span>
        <span v-if="size && date" class="sep">·</span>
        <span v-if="date">{{ date }}</span>
      </div>
    </div>
    <div class="card-actions">
      <a :href="downloadUrl" target="_blank" rel="noopener" class="action-btn primary">
        <Download class="w-4 h-4" />
        下载
      </a>
      <a
        v-if="canOpenInBrowser"
        :href="downloadUrl"
        target="_blank"
        rel="noopener"
        class="action-btn secondary"
      >
        <ExternalLink class="w-4 h-4" />
        新标签页打开
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Download,
  ExternalLink,
  FileText,
  Presentation,
  Image as ImageIcon,
  Music,
  File,
} from 'lucide-vue-next'

const props = defineProps<{
  name: string
  path: string
  type?: string
  size?: string
  date?: string
  downloadUrl: string
}>()

const extension = computed(() => {
  const parts = props.name.split('.')
  return parts.length > 1 ? parts.pop()!.toLowerCase() : ''
})

const canOpenInBrowser = computed(() => {
  const browserTypes = ['md', 'txt', 'json', 'html', 'svg', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'ogg']
  return browserTypes.includes(extension.value)
})

const icon = computed(() => {
  switch (props.type) {
    case 'ppt':
    case 'svg_ppt':
      return Presentation
    case 'content_image':
      return ImageIcon
    case 'content_audio':
      return Music
    default:
      return FileText
  }
})

const colorClass = computed(() => {
  switch (props.type) {
    case 'ppt':
    case 'svg_ppt':
      return 'icon-purple'
    case 'content_image':
      return 'icon-rose'
    case 'content_audio':
      return 'icon-orange'
    case 'mindmap':
      return 'icon-green'
    default:
      return 'icon-blue'
  }
})
</script>

<style scoped>
.download-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 24px;
  border-radius: 16px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  text-align: center;
}

.card-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-blue { background: rgb(var(--accent-rgb) / 0.1); color: rgb(var(--accent-rgb)); }
.icon-purple { background: rgb(var(--accent-purple-rgb) / 0.1); color: rgb(var(--accent-purple-rgb)); }
.icon-orange { background: rgb(var(--accent-orange-rgb) / 0.1); color: rgb(var(--accent-orange-rgb)); }
.icon-rose { background: rgb(var(--accent-rose-rgb) / 0.1); color: rgb(var(--accent-rose-rgb)); }
.icon-green { background: rgb(var(--accent-green-rgb) / 0.1); color: rgb(var(--accent-green-rgb)); }

.card-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  word-break: break-all;
}

.card-meta {
  font-size: 12px;
  color: rgb(var(--ink-4-rgb));
}

.sep {
  margin: 0 4px;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.action-btn.primary {
  background: rgb(var(--accent-rgb));
  color: white;
}
.action-btn.primary:hover {
  opacity: 0.88;
}

.action-btn.secondary {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-2-rgb));
  border: 1px solid rgb(var(--line-rgb));
}
.action-btn.secondary:hover {
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--accent-rgb) / 0.3);
}
</style>
