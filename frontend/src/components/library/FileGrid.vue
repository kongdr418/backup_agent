<template>
  <div class="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
    <button
      v-for="f in files"
      :key="f.id"
      class="file-card"
      @click="$emit('open', f)"
    >
      <div class="card-top">
        <div
          class="card-icon"
          :class="iconBg(f.type)"
        >
          <component :is="iconFor(f.type)" class="w-4.5 h-4.5" :class="iconFg(f.type)" />
        </div>
        <div class="card-body">
          <div class="card-name" :title="f.name">{{ f.name }}</div>
          <div class="card-meta">
            <span class="type-badge" :class="badgeClass(f.type)">{{ f.type_label }}</span>
            <span v-if="f.slide_count" class="meta-sep">·</span>
            <span v-if="f.slide_count">{{ f.slide_count }} 页</span>
            <span v-if="f.slide_count" class="meta-sep">·</span>
            <span>{{ f.size_formatted }}</span>
          </div>
          <div class="card-date">{{ f.created }}</div>
        </div>
      </div>

      <div class="card-actions">
        <button
          v-if="canRename(f.type)"
          class="action-icon"
          @click.stop="$emit('rename', f)"
          title="重命名"
        >
          <Pencil class="w-3.5 h-3.5" />
        </button>
        <button
          class="action-icon danger"
          @click.stop="$emit('delete', f)"
          title="删除"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import {
  FileText,
  Presentation,
  Image as ImageIcon,
  Music,
  GraduationCap,
  Lightbulb,
  Network,
  BookOpen,
  PenLine,
  ClipboardList,
  Trash2,
  Pencil,
  Video,
} from 'lucide-vue-next'
import type { GeneratedFile } from '@/types'

defineProps<{ files: GeneratedFile[] }>()

defineEmits<{
  open: [file: GeneratedFile]
  delete: [file: GeneratedFile]
  rename: [file: GeneratedFile]
}>()

function iconFor(type: string) {
  switch (type) {
    case 'ppt':
    case 'svg_ppt':
      return Presentation
    case 'lecture':
      return BookOpen
    case 'outline':
      return Network
    case 'speech':
      return PenLine
    case 'exercise':
      return GraduationCap
    case 'quiz':
      return ClipboardList
    case 'card':
      return Lightbulb
    case 'mindmap':
      return Network
    case 'content_text':
      return FileText
    case 'content_audio':
      return Music
    case 'content_image':
      return ImageIcon
    case 'video':
      return Video
    default:
      return FileText
  }
}

function iconBg(type: string) {
  switch (type) {
    case 'ppt':
    case 'svg_ppt':
      return 'icon-purple'
    case 'lecture':
    case 'outline':
    case 'speech':
      return 'icon-blue'
    case 'exercise':
    case 'quiz':
      return 'icon-orange'
    case 'card':
      return 'icon-green'
    case 'mindmap':
      return 'icon-rose'
    case 'content_image':
      return 'icon-rose'
    case 'content_audio':
      return 'icon-orange'
    case 'video':
      return 'icon-purple'
    default:
      return 'icon-neutral'
  }
}

function iconFg(type: string) {
  switch (type) {
    case 'ppt':
    case 'svg_ppt':
      return 'text-purple-600'
    case 'lecture':
    case 'outline':
    case 'speech':
      return 'text-sky-600'
    case 'exercise':
    case 'quiz':
      return 'text-amber-600'
    case 'card':
      return 'text-emerald-600'
    case 'mindmap':
      return 'text-rose-600'
    case 'content_image':
      return 'text-rose-600'
    case 'content_audio':
      return 'text-amber-600'
    case 'video':
      return 'text-purple-600'
    default:
      return 'text-ink-3'
  }
}

function badgeClass(type: string) {
  switch (type) {
    case 'ppt':
    case 'svg_ppt':
      return 'badge-purple'
    case 'lecture':
    case 'outline':
    case 'speech':
      return 'badge-blue'
    case 'exercise':
    case 'quiz':
      return 'badge-orange'
    case 'card':
      return 'badge-green'
    case 'mindmap':
      return 'badge-rose'
    case 'video':
      return 'badge-purple'
    default:
      return 'badge-neutral'
  }
}

function canRename(type: string) {
  return type !== 'svg_ppt' && type !== 'video'
}
</script>

<style scoped>
.file-card {
  text-align: left;
  padding: 14px;
  border-radius: 14px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  cursor: pointer;
  transition: all 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-card:hover {
  border-color: rgb(var(--ink-4-rgb));
  box-shadow: 0 4px 16px -4px rgb(0 0 0 / 0.06);
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-purple { background: rgb(var(--accent-purple-rgb) / 0.1); }
.icon-blue { background: rgb(var(--accent-rgb) / 0.1); }
.icon-orange { background: rgb(var(--accent-orange-rgb) / 0.1); }
.icon-green { background: rgb(var(--accent-green-rgb) / 0.1); }
.icon-rose { background: rgb(var(--accent-rose-rgb) / 0.1); }
.icon-neutral { background: rgb(var(--bg-subtle-rgb)); }

.card-body {
  flex: 1;
  min-width: 0;
}

.card-name {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 11.5px;
  color: rgb(var(--ink-4-rgb));
}

.type-badge {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 6px;
  font-size: 10.5px;
  font-weight: 500;
}

.badge-blue { background: rgb(var(--accent-rgb) / 0.08); color: rgb(var(--accent-rgb)); }
.badge-purple { background: rgb(var(--accent-purple-rgb) / 0.08); color: rgb(var(--accent-purple-rgb)); }
.badge-orange { background: rgb(var(--accent-orange-rgb) / 0.08); color: rgb(var(--accent-orange-rgb)); }
.badge-green { background: rgb(var(--accent-green-rgb) / 0.08); color: rgb(var(--accent-green-rgb)); }
.badge-rose { background: rgb(var(--accent-rose-rgb) / 0.08); color: rgb(var(--accent-rose-rgb)); }
.badge-neutral { background: rgb(var(--bg-subtle-rgb)); color: rgb(var(--ink-3-rgb)); }

.meta-sep {
  color: rgb(var(--ink-4-rgb));
}

.card-date {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  margin-top: 2px;
}

.card-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
  opacity: 0;
  transition: opacity 150ms;
}

.file-card:hover .card-actions {
  opacity: 1;
}

.action-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: transparent;
  border: none;
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  transition: all 150ms;
}

.action-icon:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

.action-icon.danger:hover {
  background: rgb(var(--accent-rose-rgb) / 0.1);
  color: rgb(var(--accent-rose-rgb));
}
</style>
