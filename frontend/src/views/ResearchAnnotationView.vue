<template>
  <div class="h-full flex flex-col">
    <PageHeader title="研究标注" description="查看课堂交互样本，触发 AI 预标注并保存最终标注">
      <template #actions>
        <n-button quaternary size="small" :loading="loading" @click="refresh">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          刷新
        </n-button>
        <n-button
          type="primary"
          size="small"
          :loading="batchAnnotating"
          :disabled="loading || annotating || samples.length === 0"
          @click="runBatchAiAnnotation"
        >
          <Sparkles class="w-3.5 h-3.5 mr-1" />
          批量 AI 标注
        </n-button>
        <n-button quaternary size="small" tag="a" :href="researchExportUrl('csv')" target="_blank">
          <Download class="w-3.5 h-3.5 mr-1" />
          导出 CSV
        </n-button>
      </template>
    </PageHeader>

    <div class="research-shell">
      <aside class="sample-list">
        <div class="list-toolbar">
          <n-select
            v-model:value="sourceFilter"
            size="small"
            :options="sourceOptions"
            @update:value="refresh"
          />
          <n-input-number
            v-model:value="limit"
            size="small"
            :min="10"
            :max="500"
            :step="10"
            @update:value="refresh"
          />
        </div>
        <div v-if="batchAnnotating || batchProgress.total > 0" class="batch-status">
          <div class="batch-status-row">
            <span>AI 标注进度</span>
            <strong>{{ batchProgress.completed }} / {{ batchProgress.total }}</strong>
          </div>
          <n-progress
            type="line"
            :percentage="batchProgressPercent"
            :height="6"
            :show-indicator="false"
            status="success"
          />
          <div class="batch-status-row muted">
            <span>成功 {{ batchProgress.succeeded }}，失败 {{ batchProgress.failed }}</span>
            <span v-if="batchProgress.currentOutputId">当前 {{ batchProgress.currentOutputId }}</span>
          </div>
        </div>

        <button
          v-for="sample in samples"
          :key="sample.output_id"
          class="sample-row"
          :class="{ active: selected?.output_id === sample.output_id }"
          @click="selectSample(sample)"
        >
          <span class="sample-meta">
            {{ sample.source || 'sample' }} · {{ sample.research_label || sample.research_user_id || sample.learner_id }}
          </span>
          <strong>
            {{ sample.task_id || sample.output_id }}
            <span class="sample-status" :class="annotationStatus(sample.output_id).source || 'none'">
              {{ annotationStatus(sample.output_id).label }}
            </span>
          </strong>
          <span>{{ sample.prompt || '无学生输入' }}</span>
        </button>

        <div v-if="!loading && samples.length === 0" class="empty-text">
          暂无样本。先使用互动课堂提问，系统会自动记录。
        </div>
      </aside>

      <main class="sample-detail">
        <div v-if="selected" class="detail-grid">
          <section class="detail-panel">
            <div class="panel-title">
              <FileText class="w-4 h-4" />
              样本内容
            </div>
            <dl class="meta-grid">
              <div>
                <dt>output_id</dt>
                <dd>{{ selected.output_id }}</dd>
              </div>
              <div>
                <dt>research user</dt>
                <dd>{{ selected.research_label || selected.research_user_id || selected.user_id || 'unknown' }}</dd>
              </div>
              <div>
                <dt>source</dt>
                <dd>{{ selected.source }}</dd>
              </div>
              <div>
                <dt>task</dt>
                <dd>{{ selected.task_id }}</dd>
              </div>
              <div>
                <dt>time</dt>
                <dd>{{ selected.timestamp }}</dd>
              </div>
            </dl>

            <div class="content-block">
              <h3>学生输入</h3>
              <p>{{ selected.prompt || '无' }}</p>
            </div>
            <div class="content-block">
              <h3>AI 回复</h3>
              <p>{{ selected.response || '无' }}</p>
            </div>
            <div class="content-block">
              <h3>上下文与记忆</h3>
              <pre>{{ prettyContext }}</pre>
            </div>
          </section>

          <section class="detail-panel">
            <div class="panel-title">
              <Sparkles class="w-4 h-4" />
              标注
            </div>
            <div class="annotation-actions">
              <n-button
                type="primary"
                size="small"
                :loading="annotating"
                :disabled="batchAnnotating"
                @click="runAiAnnotation"
              >
                <Sparkles class="w-3.5 h-3.5 mr-1" />
                AI 初步标注
              </n-button>
              <n-button size="small" :disabled="!annotation" @click="saveFinal">
                <Save class="w-3.5 h-3.5 mr-1" />
                保存最终标注
              </n-button>
            </div>
            <div v-if="selected" class="persisted-status" :class="currentAnnotationSource || 'none'">
              {{ currentAnnotationStatusText }}
            </div>

            <div v-if="annotation" class="annotation-form">
              <label>
                A 轴
                <n-select v-model:value="annotation.a_memory_failure_type" :options="aOptions" size="small" />
              </label>
              <label>
                B 轴
                <n-select v-model:value="annotation.b_pedagogical_boundary_type" :options="bOptions" size="small" />
              </label>
              <label>
                C 类
                <n-select v-model:value="annotation.c_compliance_flag" :options="cOptions" size="small" />
              </label>
              <label>
                严重度
                <n-select v-model:value="annotation.severity" :options="severityOptions" size="small" />
              </label>
              <label>
                A/B 关系
                <n-select v-model:value="annotation.relation_between_a_and_b" :options="relationOptions" size="small" />
              </label>
              <label class="wide">
                证据片段
                <n-input v-model:value="annotation.evidence_span" type="textarea" size="small" />
              </label>
              <label class="wide">
                评分理由
                <n-input v-model:value="annotation.rationale" type="textarea" size="small" />
              </label>
              <label class="wide">
                建议纠偏
                <n-input v-model:value="annotation.suggested_correction" type="textarea" size="small" />
              </label>
              <n-checkbox v-model:checked="annotation.teacher_review_needed">
                需要教师复核
              </n-checkbox>
            </div>

            <div v-else class="empty-text annotation-empty">
              选择样本后点击“AI 初步标注”。AI 结果只作为预标注，保存前可以人工修改。
            </div>
          </section>
        </div>

        <div v-else class="empty-state">
          <FileText class="w-8 h-8" />
          <p>从左侧选择一条研究样本</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCheckbox, NInput, NInputNumber, NProgress, NSelect, useMessage } from 'naive-ui'
import { Download, FileText, RefreshCw, Save, Sparkles } from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import {
  aiAnnotateResearchSample,
  listAiResearchAnnotations,
  listFinalResearchAnnotations,
  listResearchSamples,
  researchExportUrl,
  saveFinalResearchAnnotation,
  type ResearchAnnotation,
  type ResearchAnnotationRecord,
  type ResearchSample,
} from '@/api/researchLogging'
import {
  buildLatestAnnotationByOutputId,
  clonePersistedAnnotation,
  pickPersistedAnnotation,
  type AnnotationByOutputId,
  type PersistedAnnotationSource,
} from '@/utils/researchAnnotationPersistence'
import {
  runResearchBatchAnnotation,
  type ResearchBatchAnnotationState,
} from '@/utils/researchBatchAnnotation'

const message = useMessage()
const loading = ref(false)
const annotating = ref(false)
const batchAnnotating = ref(false)
const samples = ref<ResearchSample[]>([])
const selected = ref<ResearchSample | null>(null)
const annotation = ref<ResearchAnnotation | null>(null)
const currentAnnotationSource = ref<PersistedAnnotationSource>('')
const aiAnnotationByOutputId = ref<AnnotationByOutputId<ResearchAnnotationRecord>>({})
const finalAnnotationByOutputId = ref<AnnotationByOutputId<ResearchAnnotationRecord>>({})
const sourceFilter = ref('classroom_discussion')
const limit = ref(100)
const batchProgress = ref<ResearchBatchAnnotationState<ResearchAnnotation>>({
  total: 0,
  completed: 0,
  succeeded: 0,
  failed: 0,
  currentOutputId: '',
  lastAnnotation: null,
  errors: [],
})

const sourceOptions = [
  { label: '课堂讨论', value: 'classroom_discussion' },
  { label: '全部样本', value: '' },
  { label: '课堂生成', value: 'classroom_generation' },
]
const aOptions = ['none', 'stale_memory', 'false_memory', 'misattribution', 'contradiction'].map(value => ({ label: value, value }))
const bOptions = ['none', 'overhelp', 'solution_leak', 'dependency_signal', 'dependency_loop'].map(value => ({ label: value, value }))
const cOptions = ['none', 'privacy_exposure', 'sensitive_personal_data', 'data_minimization_violation'].map(value => ({ label: value, value }))
const severityOptions = ['L0', 'L1', 'L2', 'L3', 'cannot_judge'].map(value => ({ label: value, value }))
const relationOptions = ['none', 'co_occurring', 'memory_induced', 'memory_amplified', 'cannot_judge'].map(value => ({ label: value, value }))

const prettyContext = computed(() => {
  if (!selected.value) return ''
  return JSON.stringify({
    task_context: selected.value.task_context,
    memory_ids: selected.value.memory_ids,
    memory_context: selected.value.memory_context,
    memory_evidence: selected.value.memory_evidence,
    conversation_window: selected.value.conversation_window,
  }, null, 2)
})

const batchProgressPercent = computed(() => {
  if (!batchProgress.value.total) return 0
  return Math.round((batchProgress.value.completed / batchProgress.value.total) * 100)
})

const currentAnnotationStatusText = computed(() => {
  if (currentAnnotationSource.value === 'final') return '当前显示：已保存的最终标注'
  if (currentAnnotationSource.value === 'ai') return '当前显示：已保存的 AI 初标，可修改后保存为最终标注'
  return '当前样本暂无已保存标注'
})

function setAnnotationFromPersistence(outputId: string) {
  const picked = pickPersistedAnnotation(
    outputId,
    aiAnnotationByOutputId.value,
    finalAnnotationByOutputId.value,
  )
  annotation.value = picked.annotation as ResearchAnnotation | null
  currentAnnotationSource.value = picked.source
}

function annotationStatus(outputId: string) {
  if (finalAnnotationByOutputId.value[outputId]) {
    return { source: 'final', label: '终标' }
  }
  if (aiAnnotationByOutputId.value[outputId]) {
    return { source: 'ai', label: 'AI' }
  }
  return { source: '', label: '未标' }
}

async function refresh() {
  loading.value = true
  try {
    const [nextSamples, aiAnnotations, finalAnnotations] = await Promise.all([
      listResearchSamples(limit.value || 100, sourceFilter.value),
      listAiResearchAnnotations(),
      listFinalResearchAnnotations(),
    ])
    samples.value = nextSamples
    aiAnnotationByOutputId.value = buildLatestAnnotationByOutputId(aiAnnotations)
    finalAnnotationByOutputId.value = buildLatestAnnotationByOutputId(finalAnnotations)
    if (selected.value) {
      selected.value = samples.value.find(item => item.output_id === selected.value?.output_id) || null
    }
    if (selected.value) {
      setAnnotationFromPersistence(selected.value.output_id)
    } else {
      annotation.value = null
      currentAnnotationSource.value = ''
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载样本失败')
  } finally {
    loading.value = false
  }
}

function selectSample(sample: ResearchSample) {
  selected.value = sample
  setAnnotationFromPersistence(sample.output_id)
}

async function runAiAnnotation() {
  if (!selected.value || batchAnnotating.value) return
  annotating.value = true
  try {
    const saved = await aiAnnotateResearchSample(selected.value.output_id)
    aiAnnotationByOutputId.value = {
      ...aiAnnotationByOutputId.value,
      [selected.value.output_id]: saved,
    }
    annotation.value = clonePersistedAnnotation(saved)
    currentAnnotationSource.value = 'ai'
    message.success('AI 预标注完成')
  } catch (e) {
    message.error(e instanceof Error ? e.message : 'AI 标注失败')
  } finally {
    annotating.value = false
  }
}

async function runBatchAiAnnotation() {
  if (batchAnnotating.value || samples.value.length === 0) return
  batchAnnotating.value = true
  const outputIds = samples.value.map(sample => sample.output_id)
  batchProgress.value = {
    total: outputIds.length,
    completed: 0,
    succeeded: 0,
    failed: 0,
    currentOutputId: '',
    lastAnnotation: null,
    errors: [],
  }

  try {
    const result = await runResearchBatchAnnotation<ResearchAnnotation>({
      outputIds,
      annotate: async outputId => {
        const result = await aiAnnotateResearchSample(outputId)
        aiAnnotationByOutputId.value = {
          ...aiAnnotationByOutputId.value,
          [outputId]: result,
        }
        if (selected.value?.output_id === outputId && !finalAnnotationByOutputId.value[outputId]) {
          annotation.value = clonePersistedAnnotation(result)
          currentAnnotationSource.value = 'ai'
        }
        return result
      },
      onProgress: state => {
        batchProgress.value = state
      },
    })

    batchProgress.value = result
    if (result.failed) {
      message.warning(`批量标注完成：成功 ${result.succeeded}，失败 ${result.failed}`)
    } else {
      message.success(`批量标注完成：成功 ${result.succeeded} 条`)
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : '批量标注失败')
  } finally {
    batchAnnotating.value = false
  }
}

async function saveFinal() {
  if (!selected.value || !annotation.value) return
  try {
    const saved = await saveFinalResearchAnnotation(selected.value.output_id, annotation.value)
    finalAnnotationByOutputId.value = {
      ...finalAnnotationByOutputId.value,
      [selected.value.output_id]: saved,
    }
    annotation.value = clonePersistedAnnotation(saved)
    currentAnnotationSource.value = 'final'
    message.success('最终标注已保存')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.research-shell {
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  min-height: 0;
  flex: 1;
  border-top: 1px solid var(--line);
}

.sample-list {
  min-height: 0;
  overflow-y: auto;
  border-right: 1px solid var(--line);
  background: var(--bg-subtle);
  padding: 14px;
}

.list-toolbar {
  display: grid;
  grid-template-columns: 1fr 96px;
  gap: 8px;
  margin-bottom: 12px;
}

.batch-status {
  display: grid;
  gap: 6px;
  padding: 10px;
  margin-bottom: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
}

.batch-status-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink-2);
  font-size: 12px;
}

.batch-status-row strong {
  color: var(--ink-1);
}

.batch-status-row.muted {
  color: var(--ink-3);
}

.sample-row {
  width: 100%;
  display: grid;
  gap: 4px;
  text-align: left;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  color: var(--ink-2);
  margin-bottom: 8px;
  cursor: pointer;
}

.sample-row.active {
  border-color: var(--brand-forest);
  background: #f4fbf7;
}

.sample-row strong {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink-1);
  font-size: 13px;
}

.sample-status {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--line);
  color: var(--ink-3);
  background: var(--bg-subtle);
}

.sample-status.ai {
  color: #2563eb;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.sample-status.final {
  color: #047857;
  border-color: #a7f3d0;
  background: #ecfdf5;
}

.sample-row span {
  font-size: 12px;
  line-height: 1.4;
}

.sample-meta {
  color: var(--ink-3);
}

.sample-detail {
  min-height: 0;
  overflow: auto;
  padding: 18px;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
}

.detail-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  padding: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-1);
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0 0 14px;
}

.meta-grid dt {
  font-size: 11px;
  color: var(--ink-3);
}

.meta-grid dd {
  margin: 2px 0 0;
  color: var(--ink-2);
  font-size: 12px;
  word-break: break-all;
}

.content-block {
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 12px;
}

.content-block h3 {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--ink-3);
  font-weight: 600;
}

.content-block p,
.content-block pre {
  margin: 0;
  color: var(--ink-2);
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.annotation-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.persisted-status {
  padding: 8px 10px;
  margin-bottom: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink-3);
  background: var(--bg-subtle);
  font-size: 12px;
}

.persisted-status.ai {
  color: #1d4ed8;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.persisted-status.final {
  color: #047857;
  border-color: #a7f3d0;
  background: #ecfdf5;
}

.annotation-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.annotation-form label {
  display: grid;
  gap: 6px;
  color: var(--ink-3);
  font-size: 12px;
}

.annotation-form .wide,
.annotation-form :deep(.n-checkbox) {
  grid-column: 1 / -1;
}

.empty-text,
.empty-state {
  color: var(--ink-3);
  font-size: 13px;
  text-align: center;
  padding: 28px 12px;
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 360px;
}

.annotation-empty {
  border: 1px dashed var(--line);
  border-radius: 8px;
}

@media (max-width: 1024px) {
  .research-shell,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .sample-list {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    max-height: 320px;
  }
}
</style>
