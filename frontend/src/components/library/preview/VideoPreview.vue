<template>
  <div class="video-preview">
    <div class="video-frame">
      <video :src="src" class="video-el" controls preload="metadata" />
    </div>

    <div class="video-footer">
      <div class="video-info">
        <div class="video-name" :title="name">{{ name }}</div>
        <div v-if="meta" class="video-meta">{{ meta }}</div>
      </div>
      <a :href="src" :download="name" class="download-btn">
        <Download class="w-3.5 h-3.5" />
        下载
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download } from 'lucide-vue-next'

defineProps<{
  src: string
  name?: string
  meta?: string
}>()
</script>

<style scoped>
.video-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
}

.video-frame {
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-el {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.video-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.video-info {
  min-width: 0;
  flex: 1;
}

.video-name {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.video-meta {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  margin-top: 2px;
}

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgb(var(--accent-rgb) / 0.08);
  color: rgb(var(--accent-rgb));
  font-size: 12px;
  text-decoration: none;
  transition: background 150ms;
  flex-shrink: 0;
}

.download-btn:hover {
  background: rgb(var(--accent-rgb) / 0.15);
}
</style>
