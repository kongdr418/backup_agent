<template>
  <div class="profile-page">
    <section class="profile-panel">
      <div class="profile-head">
        <div>
          <h1>用户画像</h1>
          <p>用于智慧课堂的讲解深度、题目难度和反馈建议。</p>
        </div>
        <button class="ghost-btn" @click="handleReset">恢复默认</button>
      </div>

      <div class="profile-grid">
        <div class="profile-field">
          <span>学习基础</span>
          <n-select v-model:value="profile.basis" :options="basisOptions" size="small" />
        </div>

        <div class="profile-field">
          <span>学习目标</span>
          <n-select v-model:value="profile.goal" :options="goalOptions" size="small" />
        </div>

        <div class="profile-field">
          <span>讲解偏好</span>
          <n-select v-model:value="profile.style" :options="styleOptions" size="small" />
        </div>

        <div class="profile-field">
          <span>题目难度</span>
          <n-select v-model:value="profile.difficulty" :options="difficultyOptions" size="small" />
        </div>
      </div>

      <div class="summary">
        <div class="summary-title">当前画像</div>
        <div class="tag-row">
          <span>{{ profile.basis }}</span>
          <span>{{ profile.goal }}</span>
          <span>{{ profile.style }}</span>
          <span>{{ profile.difficulty }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { SelectOption } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { useStudentProfile } from '@/composables/useStudentProfile'

const message = useMessage()
const { profile, resetProfile } = useStudentProfile()

const basisOptions: SelectOption[] = [
  { label: '零基础', value: '零基础' },
  { label: '有基础', value: '有基础' },
  { label: '进阶学习', value: '进阶学习' },
]
const goalOptions: SelectOption[] = [
  { label: '考试通过', value: '考试通过' },
  { label: '项目实战', value: '项目实战' },
  { label: '概念理解', value: '概念理解' },
]
const styleOptions: SelectOption[] = [
  { label: '图解+案例', value: '图解+案例' },
  { label: '步骤推导', value: '步骤推导' },
  { label: '对比辨析', value: '对比辨析' },
]
const difficultyOptions: SelectOption[] = [
  { label: '基础', value: '基础' },
  { label: '中等', value: '中等' },
  { label: '挑战', value: '挑战' },
]

function handleReset() {
  resetProfile()
  message.success('已恢复默认画像')
}
</script>

<style scoped>
.profile-page {
  height: 100%;
  overflow: auto;
  padding: 20px;
}

.profile-panel {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb));
  padding: 18px;
}

.profile-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.profile-head h1 {
  margin: 0;
  color: rgb(var(--ink-1-rgb));
  font-size: 22px;
}

.profile-head p {
  margin: 8px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.ghost-btn {
  height: 34px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: transparent;
  color: rgb(var(--ink-2-rgb));
  padding: 0 12px;
  cursor: pointer;
}

.ghost-btn:hover {
  border-color: rgb(15 118 110 / 0.35);
  color: #0f766e;
}

.profile-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.profile-field {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.profile-field span,
.summary-title {
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.field {
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-1-rgb));
  padding: 0 12px;
  font-size: 14px;
}

.summary {
  margin-top: 18px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-base-rgb));
  padding: 12px;
}

.tag-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-row span {
  border-radius: 999px;
  background: rgb(15 118 110 / 0.10);
  color: #0f766e;
  padding: 5px 10px;
  font-size: 12px;
}

@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .profile-head {
    align-items: stretch;
    flex-direction: column;
  }

  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
