<template>
  <div class="h-full flex flex-col">
    <PageHeader title="记忆" description="查看 AI 的长期记忆摘要,管理记忆数据">
      <template #actions>
        <n-button quaternary size="small" @click="refresh">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          刷新
        </n-button>
        <n-button quaternary size="small" @click="onSave">
          <Save class="w-3.5 h-3.5 mr-1" />
          保存当前
        </n-button>
        <n-button quaternary type="warning" size="small" @click="askClearDaily">
          <Eraser class="w-3.5 h-3.5 mr-1" />
          清今日
        </n-button>
        <n-button quaternary type="error" size="small" @click="askClearAll">
          <Trash2 class="w-3.5 h-3.5 mr-1" />
          清空全部
        </n-button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-3xl mx-auto space-y-5">
        <!-- Search -->
        <div class="surface-card p-4">
          <div class="flex items-center gap-2">
            <n-input
              v-model:value="searchQuery"
              placeholder="搜索记忆..."
              clearable
              size="small"
              @keyup.enter="doSearch"
            >
              <template #prefix>
                <Search class="w-3.5 h-3.5 text-ink-3" />
              </template>
            </n-input>
            <n-button size="small" @click="doSearch">搜索</n-button>
          </div>

          <div v-if="searchResults.length > 0" class="mt-3 space-y-2">
            <div
              v-for="(r, i) in searchResults"
              :key="i"
              class="bg-bg-subtle rounded-lg p-2.5 text-[12.5px] text-ink-2 border border-line"
            >
              <pre class="whitespace-pre-wrap break-words font-mono text-[11.5px]">{{ formatResult(r) }}</pre>
            </div>
          </div>
          <div
            v-else-if="searched && searchResults.length === 0"
            class="mt-3 text-[12px] text-ink-3 text-center py-3"
          >
            未找到匹配记录
          </div>
        </div>

        <!-- Summary -->
        <div class="surface-card p-5">
          <div class="text-[13px] font-medium text-ink-1 mb-3">记忆摘要</div>
          <div v-if="store.loading" class="text-[12px] text-ink-3 text-center py-6">加载中...</div>
          <pre
            v-else-if="store.summary"
            class="whitespace-pre-wrap break-words text-[12.5px] text-ink-2 leading-relaxed bg-bg-subtle rounded-lg p-3.5 border border-line max-h-[60vh] overflow-y-auto"
          >{{ store.summary }}</pre>
          <EmptyState v-else :icon="Brain" title="暂无记忆" description="多轮对话后系统会自动生成记忆摘要" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NInput, NButton, useDialog, useMessage } from 'naive-ui'
import { Brain, RefreshCw, Save, Trash2, Eraser, Search } from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useMemoryStore } from '@/stores/memoryStore'

const store = useMemoryStore()
const dialog = useDialog()
const message = useMessage()

const searchQuery = ref('')
const searchResults = ref<Array<Record<string, unknown>>>([])
const searched = ref(false)

async function refresh() {
  try {
    await store.fetchSummary()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载失败')
  }
}

async function onSave() {
  try {
    await store.save()
    await refresh()
    message.success('已保存当前会话记忆')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  }
}

function askClearAll() {
  dialog.warning({
    title: '清空全部记忆',
    content: '将删除所有长期记忆数据,操作不可恢复。',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.clearAll()
        message.success('已清空')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}

function askClearDaily() {
  dialog.warning({
    title: '清空今日记忆',
    content: '仅删除今天的临时记忆,长期摘要保留。',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.clearDaily()
        message.success('已清空今日记忆')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}

async function doSearch() {
  searched.value = true
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  try {
    searchResults.value = await store.search(searchQuery.value.trim())
  } catch (e) {
    message.error(e instanceof Error ? e.message : '搜索失败')
  }
}

function formatResult(r: Record<string, unknown>): string {
  return JSON.stringify(r, null, 2)
}

onMounted(refresh)
</script>

<style scoped>
/* ============ Mobile ============ */
@media (max-width: 767px) {
  .p-6 {
    padding: 14px;
  }
}
</style>
