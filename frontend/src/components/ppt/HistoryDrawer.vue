<template>
  <n-drawer v-model:show="visible" :width="drawerWidth" placement="right">
    <n-drawer-content title="历史记录" closable>
      <template #header>
        <div class="flex items-center justify-between w-full pr-4">
          <span>历史记录</span>
          <button
            v-if="jobs.length > 0"
            class="text-[12px] text-rose-500 hover:text-rose-600 transition-colors"
            @click.stop="$emit('clear-all')"
          >
            清空全部
          </button>
        </div>
      </template>
      <div class="history-list">
        <div v-if="loading" class="history-state">
          加载中...
        </div>

        <div
          v-else-if="jobs.length === 0"
          class="history-state empty"
        >
          <FolderOpen class="history-empty-icon" />
          暂无历史
        </div>

        <article
          v-for="job in jobs"
          :key="job.job_id"
          class="history-card"
        >
          <button class="history-main" type="button" @click="$emit('open', job.job_id)">
            <span class="history-title">{{ job.topic || '未命名' }}</span>
            <span class="history-meta">
              <span>{{ formatPptJobCreatedAt(job.created_at) }}</span>
              <span v-if="job.num_slides" class="meta-divider" aria-hidden="true"></span>
              <span v-if="job.num_slides">{{ job.num_slides }} 页</span>
              <span v-if="job.style" class="style-chip">{{ getPptStyleLabel(job.style) }}</span>
            </span>
          </button>

          <div class="history-actions">
            <div class="history-primary-actions">
              <button
                v-if="job.has_pptx"
                class="history-action classroom"
                type="button"
                title="转交互式课堂"
                @click="$emit('classroom', job.job_id)"
              >
                <GraduationCap class="history-action-icon" />
                转课堂
              </button>
              <router-link
                v-if="job.has_pptx && !isMobile"
                :to="`/pptist-preview/${job.job_id}`"
                class="history-action"
              >
                <Edit3 class="history-action-icon" />
                编辑
              </router-link>
              <a
                v-if="job.has_pptx"
                :href="downloadUrl(job.job_id)"
                :download="job.pptx_filename"
                target="_blank"
                rel="noopener"
                class="history-action"
              >
                <Download class="history-action-icon" />
                下载
              </a>
            </div>
            <button
              class="history-delete"
              type="button"
              title="删除"
              @click="$emit('delete', job.job_id)"
            >
              <Trash2 class="history-action-icon" />
            </button>
          </div>
        </article>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NDrawer, NDrawerContent } from 'naive-ui'
import { FolderOpen, Download, GraduationCap, Trash2, Edit3 } from 'lucide-vue-next'
import type { PptJob } from '@/types'
import { pptDownloadUrl } from '@/api/pptSvg'
import { getUserId } from '@/composables/useUserId'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { formatPptJobCreatedAt, getPptStyleLabel } from '@/utils/pptHistory'

const props = defineProps<{
  show: boolean
  jobs: PptJob[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:show': [v: boolean]
  open: [jobId: string]
  delete: [jobId: string]
  classroom: [jobId: string]
  'clear-all': []
}>()

const visible = computed({
  get: () => props.show,
  set: (v: boolean) => emit('update:show', v),
})

const drawerWidth = ref(420)
const { isMobile } = useBreakpoint()

function updateWidth() {
  drawerWidth.value = window.innerWidth <= 767 ? window.innerWidth : 420
}

onMounted(() => {
  updateWidth()
  window.addEventListener('resize', updateWidth)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateWidth)
})

function downloadUrl(jobId: string) {
  return `${pptDownloadUrl(jobId)}?user_id=${encodeURIComponent(getUserId())}`
}
</script>

<style scoped>
.history-list {
  display: grid;
  gap: 10px;
}

.history-state {
  padding: 24px 0;
  color: var(--ink-tertiary);
  font-size: 12px;
  text-align: center;
}

.history-state.empty {
  padding: 40px 0;
}

.history-empty-icon {
  width: 24px;
  height: 24px;
  margin: 0 auto 8px;
  color: var(--ink-quaternary);
}

.history-card {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--bg-surface);
  transition: border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
}

.history-card:hover {
  border-color: rgba(15, 23, 42, 0.2);
  box-shadow: 0 8px 22px -18px rgba(15, 23, 42, 0.55);
}

.history-main {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 12px 13px 10px;
  cursor: pointer;
  display: grid;
  gap: 7px;
  text-align: left;
}

.history-main:hover {
  background: rgba(15, 23, 42, 0.018);
}

.history-title {
  overflow: hidden;
  color: var(--ink-primary);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  min-width: 0;
  color: var(--ink-tertiary);
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  line-height: 20px;
}

.meta-divider {
  width: 3px;
  height: 3px;
  border-radius: 999px;
  background: var(--ink-quaternary);
}

.style-chip {
  overflow: hidden;
  max-width: 92px;
  border-radius: 999px;
  background: var(--bg-subtle);
  padding: 0 7px;
  color: var(--ink-secondary);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-actions {
  border-top: 1px solid rgba(226, 232, 240, 0.72);
  padding: 8px 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.history-primary-actions {
  display: flex;
  align-items: center;
  gap: 5px;
}

.history-action,
.history-delete {
  height: 28px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--bg-surface);
  color: var(--ink-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 650;
  text-decoration: none;
  transition: background var(--duration-fast) var(--ease-out),
    border-color var(--duration-fast) var(--ease-out),
    color var(--duration-fast) var(--ease-out);
}

.history-action {
  padding: 0 9px;
}

.history-action:hover {
  border-color: rgba(15, 23, 42, 0.18);
  background: var(--bg-base);
  color: var(--ink-primary);
}

.history-action.classroom {
  border-color: rgba(45, 80, 22, 0.18);
  color: var(--forest);
}

.history-action.classroom:hover {
  background: rgba(45, 80, 22, 0.06);
}

.history-delete {
  width: 28px;
  flex: 0 0 auto;
  cursor: pointer;
}

.history-delete:hover {
  border-color: rgba(225, 29, 72, 0.2);
  background: rgba(255, 241, 242, 0.9);
  color: #be123c;
}

.history-action-icon {
  width: 12px;
  height: 12px;
}
</style>
