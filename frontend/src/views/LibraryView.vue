<template>
  <div class="library-layout">
    <!-- Header (full width) -->
    <header class="library-header">
      <div class="header-left">
        <h1 class="library-title">文件库</h1>
        <p class="library-desc">管理所有 AI 生成的文件 — PPT / 讲义 / 图片 / 音频</p>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="refresh" title="刷新">
          <RefreshCw class="w-4 h-4" />
        </button>
        <button
          v-if="allFiles.length > 0"
          class="action-btn danger"
          @click="askClearAll"
          title="清空全部"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </header>

    <!-- Body: Sidebar + Main -->
    <div class="library-body">
      <!-- Left Sidebar -->
      <aside class="library-sidebar">
        <nav class="sidebar-nav">
          <button
            v-for="item in sidebarItems"
            :key="item.value"
            class="sidebar-item"
            :class="{ active: activeCat === item.value }"
            @click="activeCat = item.value"
          >
            <component :is="item.icon" class="sidebar-icon" />
            <span class="sidebar-label">{{ item.label }}</span>
            <span class="sidebar-count">{{ countByCat(item.value) }}</span>
          </button>
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="library-main">
        <div class="library-content">
          <div v-if="loading" class="loading-state">加载中...</div>

          <EmptyState
            v-else-if="filtered.length === 0"
            :icon="FolderOpen"
            title="暂无文件"
            description="生成内容后会出现在这里"
          />

          <div v-else class="file-grid">
            <button
              v-for="f in filtered"
              :key="f.id"
              class="file-card"
              @click="onOpen(f)"
            >
              <div class="card-icon-wrap" :class="iconBg(f.type)">
                <component :is="iconFor(f.type)" class="card-icon" :class="iconFg(f.type)" />
              </div>

              <div class="card-menu">
                <button class="menu-btn" @click.stop="toggleMenu(f.id)">
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <div v-if="openMenuId === f.id" class="menu-dropdown">
                  <button v-if="canRename(f.type)" class="menu-item" @click.stop="startRename(f); openMenuId = null">
                    <Pencil class="w-3.5 h-3.5" />
                    重命名
                  </button>
                  <button class="menu-item danger" @click.stop="askDelete(f); openMenuId = null">
                    <Trash2 class="w-3.5 h-3.5" />
                    删除
                  </button>
                </div>
              </div>

              <div class="card-body">
                <div class="card-name" :title="f.name">{{ f.name }}</div>
              </div>

              <div class="card-footer">
                <span class="card-type">{{ f.type_label }}</span>
                <span v-if="f.slide_count" class="card-dot">·</span>
                <span v-if="f.slide_count">{{ f.slide_count }} 页</span>
                <span class="card-dot">·</span>
                <span class="card-size">{{ f.size_formatted }}</span>
                <span class="card-dot">·</span>
                <span class="card-date">{{ f.created }}</span>
              </div>
            </button>
          </div>
        </div>
      </main>
    </div>

    <PreviewDrawer v-model:show="previewOpen" :file="previewFile" />

    <n-modal
      v-model:show="renameShow"
      preset="dialog"
      title="重命名文件"
      positive-text="确认"
      negative-text="取消"
      @positive-click="confirmRename"
    >
      <n-input v-model:value="renameValue" placeholder="新文件名" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NModal, NInput, useDialog, useMessage } from 'naive-ui'
import {
  FolderOpen,
  RefreshCw,
  Trash2,
  MoreHorizontal,
  Pencil,
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
  Video,
  Files,
} from 'lucide-vue-next'

import EmptyState from '@/components/common/EmptyState.vue'
import PreviewDrawer from '@/components/library/PreviewDrawer.vue'

import type { GeneratedFile } from '@/types'
import { useFileStore } from '@/stores/fileStore'
import { deletePptJob } from '@/api/pptSvg'

const route = useRoute()
const fileStore = useFileStore()
const dialog = useDialog()
const message = useMessage()

const loading = ref(false)
const activeCat = ref('all')
const openMenuId = ref<string | null>(null)

const allFiles = computed<GeneratedFile[]>(() => fileStore.files)

const sidebarItems = [
  { value: 'all', label: '全部文件', icon: Files },
  { value: 'ppt', label: 'PPT', icon: Presentation },
  { value: 'video', label: '微课视频', icon: Video },
  { value: 'lecture', label: '讲义', icon: BookOpen },
  { value: 'outline', label: '课程大纲', icon: Network },
  { value: 'speech', label: '讲稿', icon: PenLine },
  { value: 'exercise', label: '习题集', icon: GraduationCap },
  { value: 'quiz', label: '课堂测验', icon: ClipboardList },
  { value: 'card', label: '知识卡片', icon: Lightbulb },
  { value: 'mindmap', label: '思维导图', icon: Network },
  { value: 'content_text', label: '文案', icon: FileText },
  { value: 'content_audio', label: '音频', icon: Music },
  { value: 'content_image', label: '图片', icon: ImageIcon },
]

const filtered = computed(() => {
  if (activeCat.value === 'all') return allFiles.value
  return allFiles.value.filter((f) => f.type === activeCat.value)
})

function countByCat(v: string) {
  if (v === 'all') return allFiles.value.length
  return allFiles.value.filter((f) => f.type === v).length
}

function iconFor(type: string) {
  switch (type) {
    case 'ppt':
    case 'svg_ppt':
      return Presentation
    case 'lecture':
      return BookOpen
    case 'outline':
    case 'mindmap':
      return Network
    case 'speech':
      return PenLine
    case 'exercise':
      return GraduationCap
    case 'quiz':
      return ClipboardList
    case 'card':
      return Lightbulb
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
      return 'text-purple'
    case 'lecture':
    case 'outline':
    case 'speech':
      return 'text-blue'
    case 'exercise':
    case 'quiz':
      return 'text-orange'
    case 'card':
      return 'text-green'
    case 'mindmap':
      return 'text-rose'
    case 'content_image':
      return 'text-rose'
    case 'content_audio':
      return 'text-orange'
    case 'video':
      return 'text-purple'
    default:
      return 'text-neutral'
  }
}

function canRename(type: string) {
  return type !== 'svg_ppt' && type !== 'video'
}

function toggleMenu(id: string) {
  openMenuId.value = openMenuId.value === id ? null : id
}

const previewOpen = ref(false)
const previewFile = ref<GeneratedFile | null>(null)

function onOpen(f: GeneratedFile) {
  previewFile.value = f
  previewOpen.value = true
}

const renameShow = ref(false)
const renameValue = ref('')
const renameTarget = ref<GeneratedFile | null>(null)

function startRename(f: GeneratedFile) {
  renameTarget.value = f
  renameValue.value = f.name
  renameShow.value = true
}

async function confirmRename() {
  if (!renameTarget.value) return
  const v = renameValue.value.trim()
  if (!v) return
  try {
    await fileStore.renameFile(renameTarget.value.path, v)
    message.success('重命名成功')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '重命名失败')
  }
  renameShow.value = false
}

function askDelete(f: GeneratedFile) {
  dialog.warning({
    title: '删除文件',
    content: `确定删除「${f.name}」?该操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        if (f.id.startsWith('svg_ppt_')) {
          const jobId = f.id.replace(/^svg_ppt_/, '')
          await deletePptJob(jobId)
          fileStore.files = fileStore.files.filter((x) => x.id !== f.id)
        } else {
          await fileStore.deleteFile(f.path)
        }
        message.success('已删除')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

function askClearAll() {
  dialog.warning({
    title: '清空全部',
    content: '将删除全部生成的文件（含微课视频），操作不可恢复。',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await fileStore.clearAllFiles()
        message.success('已清空')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}

async function refresh() {
  loading.value = true
  try {
    await fileStore.fetchFiles()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await refresh()
  const openId = route.query.open as string
  if (openId) {
    const file = allFiles.value.find((f) => f.id === openId)
    if (file) onOpen(file)
  }
})
</script>

<style scoped>
/* Layout */
.library-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Header */
.library-header {
  height: 74px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  border-bottom: 1px solid var(--line);
  background: var(--bg-surface);
}

/* Body */
.library-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* Sidebar */
.library-sidebar {
  width: 180px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--line);
  overflow-y: auto;
  padding: 16px 8px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 150ms ease;
  text-align: left;
  width: 100%;
}

.sidebar-item:hover {
  background: var(--bg-subtle);
}

.sidebar-item.active {
  background: var(--bg-subtle);
  color: var(--ink-primary);
}

.sidebar-item.active .sidebar-label {
  font-weight: 500;
}

.sidebar-icon {
  width: 16px;
  height: 16px;
  color: var(--ink-tertiary);
  flex-shrink: 0;
}

.sidebar-item.active .sidebar-icon {
  color: var(--ink-primary);
}

.sidebar-label {
  flex: 1;
  font-size: 13px;
  color: var(--ink-secondary);
  line-height: 1;
}

.sidebar-item.active .sidebar-label {
  color: var(--ink-primary);
}

.sidebar-count {
  font-size: 12px;
  color: var(--ink-tertiary);
  font-variant-numeric: tabular-nums;
}

/* Main Content */
.library-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.library-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.3;
}

.library-desc {
  font-size: 13px;
  color: var(--ink-tertiary);
  margin: 0;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--bg-surface);
  color: var(--ink-secondary);
  cursor: pointer;
  transition: all 150ms ease;
}

.action-btn:hover {
  background: var(--bg-subtle);
  color: var(--ink-primary);
  border-color: var(--line-strong);
}

.action-btn.danger:hover {
  background: var(--danger-bg);
  color: var(--danger);
  border-color: var(--danger);
}

/* Content Area */
.library-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  font-size: 13px;
  color: var(--ink-tertiary);
}

/* File Grid - 3 columns */
.file-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

/* File Card */
.file-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--bg-surface);
  border: 1px solid var(--line);
  border-radius: 16px;
  cursor: pointer;
  transition: all 200ms ease;
  text-align: left;
  width: 100%;
}

.file-card:hover {
  border-color: var(--line-strong);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px -4px rgba(0, 0, 0, 0.06);
}

.card-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.icon-purple { background: rgba(124, 74, 140, 0.1); }
.icon-blue { background: rgba(45, 107, 124, 0.1); }
.icon-orange { background: rgba(201, 150, 60, 0.1); }
.icon-green { background: rgba(45, 80, 22, 0.1); }
.icon-rose { background: rgba(188, 74, 74, 0.1); }
.icon-neutral { background: var(--bg-subtle); }

.card-icon {
  width: 20px;
  height: 20px;
}

.text-purple { color: #7C4A8C; }
.text-blue { color: #2D6B7C; }
.text-orange { color: #C9963C; }
.text-green { color: #2D5016; }
.text-rose { color: #B84A2B; }
.text-neutral { color: var(--ink-tertiary); }

/* Dark mode colors */
:root.dark .text-purple { color: #c9a3db; }
:root.dark .text-blue { color: #7ec8e3; }
:root.dark .text-orange { color: #e8c87a; }
:root.dark .text-green { color: #9fd482; }
:root.dark .text-rose { color: #e8a0a0; }
:root.dark .icon-purple { background: rgba(201, 163, 219, 0.15); }
:root.dark .icon-blue { background: rgba(126, 200, 227, 0.15); }
:root.dark .icon-orange { background: rgba(232, 200, 122, 0.15); }
:root.dark .icon-green { background: rgba(159, 212, 130, 0.15); }
:root.dark .icon-rose { background: rgba(232, 160, 160, 0.15); }

.card-menu {
  position: absolute;
  top: 12px;
  right: 12px;
}

.menu-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--ink-tertiary);
  cursor: pointer;
  transition: all 150ms ease;
}

.menu-btn:hover {
  background: var(--bg-subtle);
  color: var(--ink-primary);
}

.menu-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--bg-surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 4px;
  min-width: 120px;
  box-shadow: var(--shadow-lg);
  z-index: 10;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--ink-secondary);
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: all 100ms ease;
}

.menu-item:hover {
  background: var(--bg-subtle);
  color: var(--ink-primary);
}

.menu-item.danger:hover {
  background: var(--danger-bg);
  color: var(--danger);
}

.card-body {
  flex: 1;
  margin-bottom: 12px;
}

.card-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-tertiary);
}

.card-type {
  color: var(--ink-secondary);
}

.card-dot {
  color: var(--ink-disabled);
}

/* Responsive */
@media (max-width: 1200px) {
  .file-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .file-grid {
    grid-template-columns: 1fr;
  }
}

/* ============ Mobile ============ */
@media (max-width: 767px) {
  .library-header {
    height: auto;
    padding: 12px 16px;
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .library-title {
    font-size: 18px;
  }

  .library-desc {
    display: none;
  }

  /* Sidebar → horizontal scroll tabs */
  .library-body {
    flex-direction: column;
  }

  .library-sidebar {
    width: 100%;
    flex-shrink: 0;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 10px 12px;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .sidebar-nav {
    flex-direction: row;
    gap: 4px;
    flex-wrap: nowrap;
    white-space: nowrap;
  }

  .sidebar-item {
    flex-shrink: 0;
    width: auto;
    padding: 0 14px;
    height: 32px;
    border-radius: 16px;
    font-size: 12px;
  }

  .sidebar-label {
    font-size: 12px;
  }

  .sidebar-count {
    font-size: 11px;
  }

  /* Main content */
  .library-content {
    padding: 16px 12px;
  }

  .file-card {
    padding: 16px;
    border-radius: 12px;
  }

  .card-name {
    font-size: 13px;
  }

  .card-footer {
    font-size: 11px;
  }
}
</style>