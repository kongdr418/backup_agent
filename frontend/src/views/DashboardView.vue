<template>
  <div class="h-full flex flex-col">
    <PageHeader title="仪表盘" description="智创空间 · 后端教育内容生成" />

    <div class="flex-1 overflow-y-auto">
      <div class="max-w-5xl mx-auto px-6 py-8 space-y-8">

        <!-- Hero greeting -->
        <div class="hero-block stagger-children">
          <div class="hero-badge">
            <span class="hero-badge-dot" />
            AI 内容生成平台
          </div>
          <h1 class="hero-title">开始你的创作</h1>
          <p class="hero-sub">从下方模块选择一个，开始生成 PPT、讲义、习题、图文或短视频脚本</p>
        </div>

        <!-- Main action grid — 3 primary modules -->
        <section class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            v-for="m in primary"
            :key="m.path"
            class="primary-card card-elevated group text-left"
            @click="m.path === 'quick' ? (quickOpen = true) : router.push(m.path)"
          >
            <div class="primary-icon" :class="m.iconBg">
              <component :is="m.icon" class="w-5 h-5" :class="m.iconFg" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="primary-label">{{ m.label }}</div>
              <div class="primary-desc">{{ m.desc }}</div>
            </div>
            <ArrowRight class="w-4 h-4 text-ink-tertiary group-hover:text-ink-secondary transition-colors shrink-0" />
          </button>
        </section>

        <!-- Recent files + stats row -->
        <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <!-- Recent files -->
          <section class="lg:col-span-3">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-[13px] font-semibold text-ink-1">最近文件</h2>
              <button
                class="text-[11.5px] text-ink-tertiary hover:text-ink-secondary inline-flex items-center gap-1 transition-colors"
                @click="router.push('/library')"
              >
                查看全部
                <ChevronRight class="w-3 h-3" />
              </button>
            </div>

            <div v-if="recentLoading" class="text-center text-[12px] text-ink-tertiary py-8">加载中...</div>
            <EmptyState
              v-else-if="recent.length === 0"
              :icon="FolderOpen"
              title="暂无文件"
              description="生成的内容会出现在这里"
            />
            <div v-else class="space-y-2">
              <router-link
                v-for="f in recent"
                :key="f.id"
                :to="{ path: '/library', query: { open: f.id } }"
                class="recent-item"
              >
                <div class="recent-icon">
                  <component :is="iconFor(f.type)" class="w-3.5 h-3.5" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-[12.5px] font-medium text-ink-primary truncate">{{ f.name }}</div>
                  <div class="text-[11px] text-ink-tertiary">{{ f.type_label }} · {{ f.created }}</div>
                </div>
                <ChevronRight class="w-3.5 h-3.5 text-ink-disabled shrink-0" />
              </router-link>
            </div>
          </section>

          <!-- Stats -->
          <section class="lg:col-span-2 space-y-5">
            <h2 class="text-[13px] font-semibold text-ink-1">数据概览</h2>
            <div class="stat-grid mt-6">
              <div class="stat-card">
                <div class="stat-num">{{ totalFiles }}</div>
                <div class="stat-label">总文件数</div>
              </div>
              <div class="stat-card">
                <div class="stat-num">{{ svgPptCount }}</div>
                <div class="stat-label">SVG PPT</div>
              </div>
              <div class="stat-card">
                <div class="stat-num">{{ sessionCount }}</div>
                <div class="stat-label">对话会话</div>
              </div>
              <div class="stat-card">
                <div class="stat-num">
                  <StatusPill :tone="healthTone" class="!text-[11px]">{{ healthText }}</StatusPill>
                </div>
                <div class="stat-label">服务状态</div>
              </div>
            </div>
          </section>
        </div>

      </div>
    </div>

    <QuickGenerateModal v-model:show="quickOpen" @submit="onQuickSubmit" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  MessageSquare,
  Presentation,
  FolderOpen,
  Settings,
  Sparkles,
  ChevronRight,
  FileText,
  BookOpen,
  GraduationCap,
  ArrowRight,
  Image as ImageIcon,
  Music,
  Lightbulb,
  Network,
  PenLine,
  ClipboardList,
  Video,
} from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import QuickGenerateModal from '@/components/ppt/QuickGenerateModal.vue'

import { useFileStore } from '@/stores/fileStore'
import { useSessionStore } from '@/stores/sessionStore'
import { usePptStore } from '@/stores/pptStore'
import { getHealth } from '@/api/meta'
import { listPptJobs } from '@/api/pptSvg'
import { usePptStream } from '@/composables/usePptStream'

import type { GeneratedFile, PptGenerateParams } from '@/types'

const router = useRouter()
const message = useMessage()

const fileStore = useFileStore()
const sessionStore = useSessionStore()
const pptStore = usePptStore()
const { generate } = usePptStream()

const recentLoading = ref(false)
const recent = ref<GeneratedFile[]>([])
const svgPptCount = ref(0)
const healthOk = ref<boolean | null>(null)
const quickOpen = ref(false)

const primary = [
  {
    label: '对话生成',
    path: '/chat',
    icon: MessageSquare,
    iconBg: 'bg-forest-pale',
    iconFg: 'text-brand-forest',
    desc: '生成讲义、习题、思维导图、图文、短视频脚本',
  },
  {
    label: 'PPT 工作台',
    path: '/ppt-studio',
    icon: Presentation,
    iconBg: 'bg-ppt-pale',
    iconFg: 'text-purple-600',
    desc: 'SVG 多 Agent 流水线，生成带备注的专业幻灯片',
  },
  {
    label: '文件库',
    path: '/library',
    icon: FolderOpen,
    iconBg: 'bg-amber-pale',
    iconFg: 'text-amber-700',
    desc: '查看和管理所有生成的文件',
  },
]

const secondary = [
  { label: '讲义', path: '/chat', icon: BookOpen, iconBg: 'bg-forest-pale', iconFg: 'text-brand-forest' },
  { label: '习题集', path: '/chat', icon: GraduationCap, iconBg: 'bg-amber-pale', iconFg: 'text-amber-700' },
  { label: '快速 PPT', path: 'quick', icon: Sparkles, iconBg: 'bg-forest-pale', iconFg: 'text-brand-forest' },
  { label: '设置', path: '/settings', icon: Settings, iconBg: 'bg-bg-subtle', iconFg: 'text-ink-tertiary' },
]

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

const totalFiles = computed(() => fileStore.files.length + svgPptCount.value)
const sessionCount = computed(() => sessionStore.sessions.length)

const healthTone = computed<'success' | 'danger' | 'neutral'>(() => {
  if (healthOk.value === true) return 'success'
  if (healthOk.value === false) return 'danger'
  return 'neutral'
})
const healthText = computed(() =>
  healthOk.value === true ? '在线' : healthOk.value === false ? '离线' : '检查中',
)

async function checkHealth() {
  try {
    const h = await getHealth()
    healthOk.value = h.status === 'healthy' || h.status === 'ok'
  } catch {
    healthOk.value = false
  }
}

async function loadRecent() {
  recentLoading.value = true
  try {
    await fileStore.fetchFiles()
    recent.value = [...fileStore.files]
      .sort((a, b) => (b.created < a.created ? -1 : 1))
      .slice(0, 3)
  } catch {
    recent.value = []
  } finally {
    recentLoading.value = false
  }
}

async function loadSvgPptCount() {
  try {
    const jobs = await listPptJobs()
    svgPptCount.value = jobs.length
  } catch {
    svgPptCount.value = 0
  }
}

async function onQuickSubmit(params: PptGenerateParams) {
  pptStore.params = { ...pptStore.params, ...params }
  await router.push('/ppt-studio')
  setTimeout(() => {
    generate({ ...pptStore.params })
      .then(() => message.success('生成启动'))
      .catch((e) => message.error(e instanceof Error ? e.message : '启动失败'))
  }, 50)
}

onMounted(() => {
  checkHealth()
  loadRecent()
  loadSvgPptCount()
})
</script>

<style scoped>
/* ── Hero ── */
.hero-block {
  padding: 8px 0 4px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--ink-tertiary);
  margin-bottom: 10px;
  letter-spacing: 0.02em;
}
.hero-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--forest);
  animation: pulse-soft 2s ease-in-out infinite;
}
.hero-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--ink-primary);
  line-height: 1.15;
  margin: 0 0 8px;
}
.hero-sub {
  font-size: 14px;
  color: var(--ink-tertiary);
  line-height: 1.6;
  margin: 0;
  max-width: 520px;
}

/* ── Primary cards ── */
.primary-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 20px;
  background: var(--bg-surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-base) var(--ease-out),
              border-color var(--duration-base) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.primary-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--line-strong);
  transform: translateY(-2px);
}
.primary-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bg-forest-pale { background: var(--forest-pale); }
.bg-ppt-pale { background: rgba(240, 232, 245, 0.8); }
.bg-amber-pale { background: var(--amber-pale); }
.primary-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 4px;
  font-family: 'DM Sans', sans-serif;
}
.primary-desc {
  font-size: 12px;
  color: var(--ink-tertiary);
  line-height: 1.5;
}

/* ── Section header ── */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-title {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--ink-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Secondary cards ── */
.secondary-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.secondary-card:hover {
  border-color: var(--line-strong);
  background: var(--bg-subtle);
}
.secondary-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.secondary-label {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--ink-secondary);
}

/* ── Recent items ── */
.recent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  transition: background var(--duration-fast) var(--ease-out);
  text-decoration: none;
}
.recent-item:hover {
  background: var(--bg-subtle);
}
.recent-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: var(--bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-tertiary);
  flex-shrink: 0;
}

/* ── Stats ── */
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-num {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink-primary);
  line-height: 1;
}
.stat-label {
  font-size: 11.5px;
  color: var(--ink-tertiary);
}

/* ── Stagger animation ── */
.stagger-children > * { opacity: 0; animation: slideUpFade var(--duration-slow) var(--ease-out) forwards; }
.stagger-children > *:nth-child(1) { animation-delay: 0ms; }
.stagger-children > *:nth-child(2) { animation-delay: 80ms; }
.stagger-children > *:nth-child(3) { animation-delay: 160ms; }
.stagger-children > *:nth-child(4) { animation-delay: 240ms; }

@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes pulse-soft {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ============ Mobile ============ */
@media (max-width: 767px) {
  .hero-block {
    padding: 4px 0 0;
  }

  .hero-badge {
    font-size: 10.5px;
    margin-bottom: 8px;
  }

  .hero-title {
    font-size: 24px;
  }

  .hero-sub {
    font-size: 13px;
    max-width: 100%;
  }

  .primary-card {
    padding: 16px;
    gap: 12px;
  }

  .primary-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
  }

  .primary-label {
    font-size: 13px;
  }

  .primary-desc {
    font-size: 11px;
  }

  .stat-grid {
    gap: 8px;
  }

  .stat-card {
    padding: 14px 12px;
  }

  .stat-num {
    font-size: 18px;
  }

  .stat-label {
    font-size: 10.5px;
  }
}
</style>