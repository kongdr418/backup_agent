<template>
  <section class="summary-card">
    <div class="summary-head">
      <div>
        <span>画像草稿</span>
        <h3>这些信息是否符合你的实际情况？</h3>
      </div>
      <CircleCheckBig :size="22" />
    </div>

    <div class="summary-grid">
      <div><span>学习阶段</span><strong>{{ state.draft.basic.learning_stage }}</strong></div>
      <div><span>当前基础</span><strong>{{ state.draft.basic.learning_basis }}</strong></div>
      <div><span>学习目标</span><strong>{{ state.draft.preferences.goal }}</strong></div>
      <div><span>期望难度</span><strong>{{ state.draft.preferences.preferred_difficulty }}</strong></div>
      <div><span>内容偏好</span><strong>{{ state.draft.preferences.content_style.join('、') }}</strong></div>
      <div><span>辅导方式</span><strong>{{ state.draft.preferences.tutoring_style }}</strong></div>
      <div class="wide"><span>学习背景</span><strong>{{ state.draft.basic.background }}</strong></div>
      <div class="wide">
        <span>兴趣方向</span>
        <strong>{{ interestLabels }}</strong>
      </div>
    </div>

    <div class="summary-actions">
      <button type="button" class="secondary" :disabled="loading" @click="$emit('continue')">
        继续补充
      </button>
      <button type="button" class="primary" :disabled="loading" @click="$emit('confirm')">
        <LoaderCircle v-if="loading" class="spin" :size="16" />
        <Save v-else :size="16" />
        {{ loading ? '保存中' : '确认并保存画像' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheckBig, LoaderCircle, Save } from 'lucide-vue-next'
import type { ProfileOnboardingState } from '@/utils/profileOnboarding'

const props = defineProps<{
  state: ProfileOnboardingState
  loading: boolean
}>()

defineEmits<{
  continue: []
  confirm: []
}>()

const interestLabels = computed(() => (
  props.state.draft.global_traits.interest_directions
    .map((item) => item.label)
    .join('、')
))
</script>

<style scoped>
.summary-card {
  width: min(760px, 92%);
  margin: -8px 0 4px;
  padding: 20px;
  border: 1px solid rgb(var(--forest-rgb) / 0.22);
  border-radius: 18px;
  background:
    linear-gradient(145deg, rgb(var(--forest-rgb) / 0.06), transparent 54%),
    rgb(var(--bg-surface-rgb));
  box-shadow: var(--shadow-sm);
}

.summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgb(var(--forest-rgb));
}

.summary-head span,
.summary-grid span {
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
}

.summary-head h3 {
  margin: 4px 0 0;
  color: rgb(var(--ink-1-rgb));
  font-size: 15px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 15px;
}

.summary-grid > div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgb(var(--bg-subtle-rgb) / 0.72);
}

.summary-grid strong {
  overflow-wrap: anywhere;
  color: rgb(var(--ink-2-rgb));
  font-size: 12.5px;
}

.summary-grid .wide {
  grid-column: 1 / -1;
}

.summary-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.summary-actions button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 15px;
  border-radius: 9px;
  border: 0;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 600;
}

.summary-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.secondary {
  color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.primary {
  color: white;
  background: rgb(var(--forest-rgb));
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .summary-card { width: 100%; padding: 16px; }
  .summary-grid { grid-template-columns: 1fr; }
  .summary-grid .wide { grid-column: auto; }
  .summary-actions { flex-direction: column-reverse; }
  .summary-actions button { width: 100%; }
}
</style>
