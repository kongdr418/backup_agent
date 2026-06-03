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
        <label class="profile-field">
          <span>学习基础</span>
          <select v-model="profile.basis" class="field">
            <option value="零基础">零基础</option>
            <option value="有基础">有基础</option>
            <option value="进阶学习">进阶学习</option>
          </select>
        </label>

        <label class="profile-field">
          <span>学习目标</span>
          <select v-model="profile.goal" class="field">
            <option value="考试通过">考试通过</option>
            <option value="项目实战">项目实战</option>
            <option value="概念理解">概念理解</option>
          </select>
        </label>

        <label class="profile-field">
          <span>讲解偏好</span>
          <select v-model="profile.style" class="field">
            <option value="图解+案例">图解+案例</option>
            <option value="步骤推导">步骤推导</option>
            <option value="对比辨析">对比辨析</option>
          </select>
        </label>

        <label class="profile-field">
          <span>题目难度</span>
          <select v-model="profile.difficulty" class="field">
            <option value="基础">基础</option>
            <option value="中等">中等</option>
            <option value="挑战">挑战</option>
          </select>
        </label>
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
import { useMessage } from 'naive-ui'
import { useStudentProfile } from '@/composables/useStudentProfile'

const message = useMessage()
const { profile, resetProfile } = useStudentProfile()

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
