<template>
  <div class="param-panel">
    <div class="param-content">
      <!-- Topic -->
      <section class="param-section">
        <div class="param-label-row">
          <label class="param-label">
            课程主题 <span class="text-rose-500">*</span>
          </label>
          <button
            v-if="hasDraftText && !disabled"
            class="clear-draft-btn"
            type="button"
            title="清空课程主题和备注"
            @click="$emit('clear-draft')"
          >
            <RotateCcw class="w-3.5 h-3.5" />
            清空
          </button>
        </div>
        <n-input
          v-model:value="local.topic"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="例如：神经网络入门、量子力学基础、营销心理学..."
          :disabled="disabled"
        />
      </section>

      <!-- 备注 / 附加要求 -->
      <section class="param-section">
        <label class="param-label">
          备注 / 附加要求
          <span class="text-gray-400 text-xs font-normal">（可选）</span>
        </label>
        <n-input
          v-model:value="local.notes"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          placeholder="例如：面向高中生，例子用游戏类比；重点强调对比；尽量避免数学公式"
          :disabled="disabled"
          :maxlength="2000"
          show-count
        />
        <p class="advanced-hint" style="margin-top: 6px;">
          仅作为补充上下文喂给 LLM，不会覆盖页数 / 语言 / 风格等参数
        </p>
      </section>

      <!-- Style -->
      <section class="param-section">
        <label class="param-label">设计风格</label>
        <div class="style-list">
          <StyleCard
            v-for="opt in styleOptions"
            :key="opt.value"
            :label="opt.label"
            :description="opt.desc"
            :icon="opt.icon"
            :selected="local.style === opt.value"
            @select="local.style = opt.value"
          />
        </div>
      </section>

      <!-- Templates -->
      <section v-if="templateList.length > 0" class="param-section">
        <label class="param-label">布局模板 <span class="text-gray-400 text-xs font-normal">（可选）</span></label>
        <select
          class="template-select"
          :value="local.template_id"
          @change="onTemplateChange"
        >
          <option :value="undefined">不使用模板（AI 自由设计）</option>
          <optgroup v-for="(group, cat) in templateGroups" :key="cat" :label="group.label">
            <option
              v-for="tmpl in group.templates"
              :key="tmpl.template_id"
              :value="tmpl.template_id"
            >
              {{ tmpl.label }}
            </option>
          </optgroup>
        </select>
      </section>

      <!-- Pages -->
      <section class="param-section">
        <div class="param-row">
          <label class="param-label">页数</label>
          <span class="param-value">{{ pageDisplay }}</span>
        </div>
        <div class="page-control">
          <button
            class="auto-btn"
            :class="{ active: local.num_slides == null }"
            @click="local.num_slides = undefined"
          >
            自动
          </button>
          <n-slider
            v-model:value="sliderValue"
            :min="local.deep_research ? 5 : 3"
            :max="20"
            :step="1"
            class="flex-1"
          />
        </div>
      </section>

      <!-- Detail level -->
      <section class="param-section">
        <label class="param-label">详细程度</label>
        <n-radio-group v-model:value="local.detail_level" :disabled="disabled" size="small">
          <n-radio-button value="brief">简略</n-radio-button>
          <n-radio-button value="normal">正常</n-radio-button>
          <n-radio-button value="detailed">详细</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Language -->
      <section class="param-section">
        <label class="param-label">语言</label>
        <n-radio-group v-model:value="local.language" :disabled="disabled" size="small">
          <n-radio-button value="zh">中文</n-radio-button>
          <n-radio-button value="en">English</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Canvas format -->
      <section class="param-section">
        <label class="param-label">画布比例</label>
        <n-radio-group v-model:value="local.canvas_format" :disabled="disabled" size="small">
          <n-radio-button value="ppt169">16:9 (推荐)</n-radio-button>
          <n-radio-button value="ppt43">4:3</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Advanced -->
      <details class="advanced-group">
        <summary class="advanced-toggle">
          <ChevronRight
            class="w-3.5 h-3.5 transition-transform"
          />
          高级设置
        </summary>
        <div class="advanced-body">
          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-label">深度研究</span>
              <span class="toggle-desc">4-Pass 深度分析，内容更丰富但耗时更长</span>
            </div>
            <n-switch
              :value="local.deep_research"
              :disabled="disabled"
              size="small"
              @update:value="onDeepResearchChange"
            />
          </div>
          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-label">视觉审查</span>
              <span class="toggle-desc">VLM 视觉检查，需要多模态模型支持</span>
            </div>
            <n-switch v-model:value="local.visual_critic" :disabled="disabled" size="small" />
          </div>
          <div class="toggle-row">
            <div class="toggle-info">
              <span class="toggle-label">自动返修</span>
              <span class="toggle-desc">发现阻塞问题时让 AI 再修一次；关闭后生成更快但可能保留瑕疵</span>
            </div>
            <n-switch v-model:value="local.repair_enabled" :disabled="disabled" size="small" />
          </div>
          <p class="advanced-hint" style="margin-top: 10px;">模型在「设置 → PPT 生成模型」中统一配置</p>
        </div>
      </details>
    </div>

    <!-- Action -->
    <div class="action-area">
      <button
        v-if="!disabled"
        class="generate-btn"
        :disabled="!canSubmit"
        @click="$emit('generate')"
      >
        <Wand2 class="w-4 h-4" />
        开始生成
      </button>

      <button
        v-else
        class="cancel-btn"
        @click="$emit('cancel')"
      >
        <Square class="w-4 h-4" />
        停止生成
      </button>
      <p class="action-hint">
        生成耗时与页数相关，通常需要 6~7 分钟，页数较多时可能超过 10 分钟
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { NInput, NSlider, NRadioGroup, NRadioButton, NSwitch } from 'naive-ui'
import {
  GraduationCap,
  Microscope,
  Briefcase,
  Cpu,
  LayoutGrid,
  ChevronRight,
  Wand2,
  Square,
  RotateCcw,
} from 'lucide-vue-next'
import StyleCard from './StyleCard.vue'
import type { PptGenerateParams } from '@/types'
import { listTemplates, type TemplateItem } from '@/api/templates'

const props = defineProps<{
  modelValue: PptGenerateParams
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PptGenerateParams]
  generate: []
  cancel: []
  'clear-draft': []
}>()

const local = reactive<PptGenerateParams>({ ...props.modelValue })
if (local.repair_enabled == null) {
  local.repair_enabled = false
}

const hasDraftText = computed(() => !!local.topic?.trim() || !!local.notes?.trim())

watch(
  () => props.modelValue,
  (v) => {
    Object.assign(local, v)
    if (local.repair_enabled == null) {
      local.repair_enabled = false
    }
  },
  { deep: true },
)

watch(local, (v) => emit('update:modelValue', { ...v }), { deep: true })

function onDeepResearchChange(val: boolean) {
  local.deep_research = val
  if (val && local.num_slides != null && local.num_slides < 5) {
    local.num_slides = 5
  }
}

const templateList = ref<TemplateItem[]>([])
const templateGroups = computed(() => {
  const groups: Record<string, { label: string; templates: TemplateItem[] }> = {}
  for (const t of templateList.value) {
    const cat = t.category || 'other'
    if (!groups[cat]) {
      groups[cat] = { label: cat, templates: [] }
    }
    groups[cat].templates.push(t)
  }
  return groups
})

onMounted(async () => {
  try {
    templateList.value = await listTemplates()
  } catch {
    // silently fail
  }
})

function onTemplateChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  local.template_id = val || undefined
}

const styleOptions: Array<{
  value: 'education' | 'academic' | 'consulting' | 'tech' | 'general'
  label: string
  desc: string
  icon: typeof GraduationCap
}> = [
  { value: 'education', label: '教育课件', desc: '简洁清晰，适合教学场景', icon: GraduationCap },
  { value: 'academic', label: '学术', desc: '严谨规范，论文报告范式', icon: Microscope },
  { value: 'consulting', label: '咨询', desc: '商务专业，数据驱动叙事', icon: Briefcase },
  { value: 'tech', label: '科技', desc: '现代极简，产品介绍风', icon: Cpu },
  { value: 'general', label: '通用', desc: '中性百搭，适配各类话题', icon: LayoutGrid },
]

const sliderValue = computed({
  get: () => local.num_slides ?? 8,
  set: (v: number) => {
    local.num_slides = v
  },
})

const pageDisplay = computed(() =>
  local.num_slides == null ? '由 AI 自动决定' : `${local.num_slides} 页`,
)

const canSubmit = computed(
  () => !!local.topic && local.topic.trim().length > 0 && !props.disabled,
)
</script>

<style scoped>
.param-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.param-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.param-section {
  margin-bottom: 20px;
}

.param-section:last-child {
  margin-bottom: 0;
}

.param-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
  margin-bottom: 8px;
  letter-spacing: 0.01em;
}

.param-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.param-label-row .param-label {
  margin-bottom: 0;
}

.clear-draft-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 6px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease, background 150ms ease;
}

.clear-draft-btn:hover {
  border-color: rgb(var(--line-strong-rgb));
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

.param-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.param-value {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.style-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.template-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d4d4d4;
  border-radius: 8px;
  font-size: 13px;
  color: #111;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition: border-color 200ms ease;
}
.template-select:focus {
  border-color: #111;
}

.page-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auto-btn {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  transition: all 150ms ease;
  flex-shrink: 0;
}

.auto-btn:hover {
  border-color: rgb(var(--line-strong-rgb));
  color: rgb(var(--ink-2-rgb));
}

.auto-btn.active {
  border-color: rgb(var(--ink-1-rgb));
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

/* Advanced */
.advanced-group {
  margin-top: 4px;
}

.advanced-toggle {
  cursor: pointer;
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  transition: color 150ms ease;
}

.advanced-toggle:hover {
  color: rgb(var(--ink-2-rgb));
}

.advanced-toggle::-webkit-details-marker {
  display: none;
}

.advanced-group[open] .advanced-toggle :deep(svg) {
  transform: rotate(90deg);
}

.advanced-body {
  margin-top: 10px;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.toggle-row + .toggle-row {
  border-top: 1px solid rgb(var(--line-rgb));
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toggle-label {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
}

.toggle-desc {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
}

.advanced-hint {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  line-height: 1.5;
}

/* Action Area */
.action-area {
  flex-shrink: 0;
  padding: 16px 24px 20px;
  border-top: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
}

.generate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms ease;
}

.generate-btn:hover:not(:disabled) {
  background: rgb(var(--ink-2-rgb));
}

.generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cancel-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: rgb(254 226 226);
  color: rgb(185 28 28);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms ease;
}

.cancel-btn:hover {
  background: rgb(254 202 202);
}

.action-hint {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  margin-top: 10px;
  text-align: center;
  line-height: 1.5;
}
</style>
