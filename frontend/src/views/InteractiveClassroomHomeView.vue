<template>
  <div class="classroom-home">
    <div class="panel">
      <h1 class="title">交互式课堂</h1>
      <p class="desc">先生成一节可播放、可答题、可反馈的真实课堂。</p>

      <div class="form-grid">
        <input v-model.trim="topic" class="field" placeholder="输入主题，例如：Python 循环语句" />
        <input v-model.trim="course" class="field" placeholder="课程名（可选）" />
        <input
          v-model.trim="pptJobId"
          class="field"
          placeholder="PPT Job ID（可选，用于复用 PPT Studio 内容）"
        />
      </div>

      <button class="primary-btn" :disabled="loading" @click="onGenerate">
        {{ loading ? '生成中...' : '生成课堂' }}
      </button>
    </div>

    <div class="panel">
      <div class="list-head">
        <h2>历史课堂</h2>
        <button class="ghost-btn" :disabled="loadingList" @click="loadList">刷新</button>
      </div>

      <div v-if="classrooms.length === 0" class="empty">暂无课堂记录</div>
      <div v-else class="list">
        <button
          v-for="item in classrooms"
          :key="item.id"
          class="list-item"
          @click="router.push(`/interactive-classroom/${item.id}`)"
        >
          <div class="item-title">{{ item.title }}</div>
          <div class="item-meta">{{ item.topic }} · {{ item.scene_count }} scenes</div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  generateInteractiveClassroom,
  listInteractiveClassrooms,
  type InteractiveClassroomListItem,
} from '@/api/interactiveClassroom'
import { useSettingStore } from '@/stores/settingStore'

const router = useRouter()
const message = useMessage()
const settingStore = useSettingStore()

const topic = ref('')
const course = ref('Python 程序设计')
const pptJobId = ref('')
const loading = ref(false)
const loadingList = ref(false)
const classrooms = ref<InteractiveClassroomListItem[]>([])

async function loadList() {
  loadingList.value = true
  try {
    classrooms.value = await listInteractiveClassrooms()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载失败')
  } finally {
    loadingList.value = false
  }
}

async function onGenerate() {
  if (!topic.value) {
    message.warning('请先输入主题')
    return
  }

  loading.value = true
  try {
    const res = await generateInteractiveClassroom({
      topic: topic.value,
      course: course.value || undefined,
      ppt_job_id: pptJobId.value || undefined,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
    })
    message.success('课堂已生成')
    await loadList()
    router.push(`/interactive-classroom/${res.classroom_id}`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '生成失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadList().catch(() => undefined)
})
</script>

<style scoped>
.classroom-home {
  height: 100%;
  overflow: auto;
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.panel {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb));
  padding: 16px;
}

.title {
  margin: 0;
  font-size: 22px;
}

.desc {
  margin: 8px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 14px;
}

.field {
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-base-rgb));
  padding: 0 12px;
  font-size: 14px;
}

.primary-btn {
  margin-top: 12px;
  height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.list-head h2 {
  margin: 0;
  font-size: 16px;
}

.ghost-btn {
  height: 32px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: transparent;
  padding: 0 10px;
  cursor: pointer;
}

.empty {
  margin-top: 10px;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.list {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.list-item {
  text-align: left;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  padding: 10px;
  cursor: pointer;
}

.item-title {
  font-size: 14px;
  color: rgb(var(--ink-1-rgb));
}

.item-meta {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}
</style>
