<template>
  <div class="h-full flex flex-col">
    <PageHeader title="仪表盘" description="智课源 · 后端教育内容生成 (PPT / 讲义 / 习题 / 图文 / 短视频脚本)">
      <template #actions>
        <StatusPill :tone="healthTone">{{ healthText }}</StatusPill>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-6xl mx-auto space-y-6">
        <!-- Quick actions / module cards -->
        <section>
          <div class="flex items-baseline justify-between mb-3">
            <h2 class="text-[14px] font-semibold text-ink-1">开始创作</h2>
            <span class="text-[12px] text-ink-3">点击模块进入工作台</span>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            <button
              v-for="m in modules"
              :key="m.path"
              class="text-left bg-bg-surface border border-line rounded-card p-4 hover:border-ink-4 hover:shadow-card-hover transition-all"
              @click="m.path === 'quick' ? (quickOpen = true) : router.push(m.path)"
            >
              <div
                class="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                :class="m.bg"
              >
                <component :is="m.icon" class="w-4 h-4" :class="m.fg" />
              </div>
              <div class="text-[13.5px] font-medium text-ink-1">{{ m.label }}</div>
              <div class="text-[11.5px] text-ink-3 mt-1 leading-relaxed line-clamp-2">{{ m.desc }}</div>
            </button>
          </div>
        </section>

        <!-- Recent files -->
        <section>
          <div class="flex items-baseline justify-between mb-3">
            <h2 class="text-[14px] font-semibold text-ink-1">最近文件</h2>
            <button
              class="text-[12px] text-ink-3 hover:text-ink-1 inline-flex items-center gap-1"
              @click="router.push('/library')"
            >
              查看全部
              <ChevronRight class="w-3.5 h-3.5" />
            </button>
          </div>

          <div v-if="recentLoading" class="text-center text-[12px] text-ink-3 py-6">加载中...</div>
          <EmptyState
            v-else-if="recent.length === 0"
            :icon="FolderOpen"
            title="暂无文件"
            description="生成的内容会出现在这里"
          />
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <router-link
              v-for="f in recent"
              :key="f.id"
              to="/library"
              class="bg-bg-surface border border-line rounded-card p-3.5 hover:border-ink-4 transition-all flex items-center gap-3"
            >
              <div class="w-9 h-9 rounded-lg bg-bg-subtle flex items-center justify-center shrink-0">
                <FileText class="w-4 h-4 text-ink-2" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-[13px] font-medium text-ink-1 truncate" :title="f.name">
                  {{ f.name }}
                </div>
                <div class="text-[11px] text-ink-3 mt-0.5 truncate">
                  {{ f.type_label }} · {{ f.created }}
                </div>
              </div>
            </router-link>
          </div>
        </section>

        <!-- Stats -->
        <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="bg-bg-surface border border-line rounded-card p-4">
            <div class="text-[11.5px] text-ink-3">总文件数</div>
            <div class="text-[20px] font-semibold text-ink-1 mt-1">{{ totalFiles }}</div>
          </div>
          <div class="bg-bg-surface border border-line rounded-card p-4">
            <div class="text-[11.5px] text-ink-3">SVG PPT</div>
            <div class="text-[20px] font-semibold text-ink-1 mt-1">{{ svgPptCount }}</div>
          </div>
          <div class="bg-bg-surface border border-line rounded-card p-4">
            <div class="text-[11.5px] text-ink-3">对话会话</div>
            <div class="text-[20px] font-semibold text-ink-1 mt-1">{{ sessionCount }}</div>
          </div>
          <div class="bg-bg-surface border border-line rounded-card p-4">
            <div class="text-[11.5px] text-ink-3">服务状态</div>
            <div class="text-[14px] font-medium mt-1.5">
              <StatusPill :tone="healthTone">{{ healthText }}</StatusPill>
            </div>
          </div>
        </section>
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
  Brain,
  Sparkles,
  ChevronRight,
  FileText,
  BookOpen,
  GraduationCap,
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

const modules = [
  {
    label: '对话生成',
    path: '/chat',
    icon: MessageSquare,
    bg: 'icon-blue',
    fg: 'text-sky-600',
    desc: '生成讲义/讲稿/习题/卡片/思维导图等',
  },
  {
    label: 'PPT 工作台',
    path: '/ppt-studio',
    icon: Presentation,
    bg: 'icon-purple',
    fg: 'text-purple-600',
    desc: '基于 SVG 多 Agent 流水线的 PPT 生成',
  },
  {
    label: '快速生成 PPT',
    path: 'quick',
    icon: Sparkles,
    bg: 'icon-green',
    fg: 'text-emerald-600',
    desc: '弹窗简化版,只需输入主题即可',
  },
  {
    label: '文件库',
    path: '/library',
    icon: FolderOpen,
    bg: 'icon-orange',
    fg: 'text-amber-600',
    desc: '查看与管理所有生成结果',
  },
  {
    label: '记忆',
    path: '/memory',
    icon: Brain,
    bg: 'icon-rose',
    fg: 'text-rose-600',
    desc: '查看和管理 AI 长期记忆',
  },
  {
    label: '讲义',
    path: '/chat',
    icon: BookOpen,
    bg: 'icon-blue',
    fg: 'text-sky-600',
    desc: '在对话中输入「生成讲义：主题」',
  },
  {
    label: '习题集',
    path: '/chat',
    icon: GraduationCap,
    bg: 'icon-orange',
    fg: 'text-amber-600',
    desc: '在对话中输入「习题集：主题」',
  },
  {
    label: '设置',
    path: '/settings',
    icon: Settings,
    bg: 'icon-neutral',
    fg: 'text-ink-3',
    desc: '配置语音/封面/PPT 默认参数',
  },
]

const totalFiles = computed(() => fileStore.files.length + svgPptCount.value)
const sessionCount = computed(() => sessionStore.sessions.length)

const healthTone = computed<'success' | 'danger' | 'neutral'>(() => {
  if (healthOk.value === true) return 'success'
  if (healthOk.value === false) return 'danger'
  return 'neutral'
})
const healthText = computed(() =>
  healthOk.value === true ? '后端在线' : healthOk.value === false ? '后端离线' : '检查中',
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
      .slice(0, 6)
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
  // Wait one tick for navigation, then start
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
.icon-blue { background: rgb(var(--accent-rgb) / 0.1); }
.icon-purple { background: rgb(var(--accent-purple-rgb) / 0.1); }
.icon-orange { background: rgb(var(--accent-orange-rgb) / 0.1); }
.icon-green { background: rgb(var(--accent-green-rgb) / 0.1); }
.icon-rose { background: rgb(var(--accent-rose-rgb) / 0.1); }
.icon-neutral { background: rgb(var(--bg-subtle-rgb)); }
</style>
