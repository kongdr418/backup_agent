<template>
  <div class="learner-page">
    <div class="page-glow glow-a"></div>
    <div class="page-glow glow-b"></div>

    <main class="learner-shell">
      <header class="hero">
        <div class="hero-copy">
          <div class="eyebrow"><UserRound :size="15" /> 学习者中心</div>
          <h1>让每次生成，更懂你的学习方式</h1>
          <p>这份画像是智慧课堂的统一学习档案。当前先由你维护基本信息和偏好，后续课堂表现会在确认后逐步补充课程画像。</p>
        </div>
        <div class="hero-actions">
          <span class="save-state" :class="{ saved: !dirty && !loading }">
            <CircleCheckBig v-if="!dirty && !loading" :size="15" />
            <CircleDashed v-else :size="15" />
            {{ loading ? '正在读取' : dirty ? '有未保存修改' : '已同步到学习档案' }}
          </span>
          <button class="primary-btn" :disabled="!profileReady || loading || saving || !dirty" @click="handleSave">
            <LoaderCircle v-if="saving" class="spin" :size="16" />
            <Save v-else :size="16" />
            {{ saving ? '保存中' : '保存画像' }}
          </button>
        </div>
      </header>

      <section v-if="loadError" class="error-banner">
        <TriangleAlert :size="18" />
        <span>{{ loadError }}</span>
        <button @click="loadProfile">重新加载</button>
      </section>

      <section class="profile-layout" :class="{ loading, unavailable: !profileReady }">
        <aside class="profile-card identity-card">
          <div class="identity-mark">
            <span>{{ avatarText }}</span>
          </div>
          <div>
            <p class="card-kicker">当前学习档案</p>
            <h2>{{ profile.basic.display_name || '未命名学习者' }}</h2>
            <p class="identity-meta">
              {{ profile.basic.learning_stage || '学习阶段待补充' }}
              <span></span>
              {{ profile.basic.learning_basis || '基础待评估' }}
            </p>
          </div>

          <div class="profile-tags">
            <span v-if="profile.preferences.goal">{{ profile.preferences.goal }}</span>
            <span v-for="style in profile.preferences.content_style" :key="style">{{ style }}</span>
            <span v-if="profile.preferences.preferred_difficulty">
              {{ profile.preferences.preferred_difficulty }}难度
            </span>
            <span v-if="!summaryTags.length" class="empty-tag">等待你完善画像</span>
          </div>

          <div class="phase-note">
            <Sparkles :size="17" />
            <div>
              <strong>当前阶段：手动画像</strong>
              <p>课程掌握度、学习证据和 Agent 更新建议将在后续阶段接入。</p>
            </div>
          </div>
        </aside>

        <div class="form-stack">
          <section class="profile-card form-card">
            <div class="section-head">
              <div class="section-icon"><IdCard :size="19" /></div>
              <div>
                <h2>基本信息</h2>
                <p>帮助系统理解你的学习背景，不会直接出现在课堂讲稿中。</p>
              </div>
            </div>

            <div class="form-grid">
              <label class="field">
                <span>称呼</span>
                <n-input v-model:value="profile.basic.display_name" placeholder="例如：小林" maxlength="80" />
              </label>
              <label class="field">
                <span>年级 / 培养阶段</span>
                <n-select
                  v-model:value="profile.basic.learning_stage"
                  :options="stageOptions"
                  filterable
                  tag
                  placeholder="例如：大二"
                />
              </label>
              <label class="field">
                <span>当前基础</span>
                <n-select
                  v-model:value="profile.basic.learning_basis"
                  :options="basisOptions"
                  filterable
                  tag
                  placeholder="选择或描述当前基础"
                />
              </label>
              <label class="field field-wide">
                <span>学习背景</span>
                <n-input
                  v-model:value="profile.basic.background"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 5 }"
                  maxlength="300"
                  show-count
                  placeholder="例如：学过基础编程，希望系统讲解时多联系实际案例。"
                />
              </label>
            </div>
          </section>

          <section class="profile-card form-card">
            <div class="section-head">
              <div class="section-icon warm"><SlidersHorizontal :size="19" /></div>
              <div>
                <h2>学习偏好</h2>
                <p>这些偏好将转换为课堂生成策略，而不是直接拼进讲稿。</p>
              </div>
            </div>

            <div class="form-grid">
              <label class="field">
                <span>学习目标</span>
                <n-select
                  v-model:value="profile.preferences.goal"
                  :options="goalOptions"
                  filterable
                  tag
                  placeholder="选择或输入目标"
                />
              </label>
              <label class="field">
                <span>期望难度</span>
                <n-select
                  v-model:value="profile.preferences.preferred_difficulty"
                  :options="difficultyOptions"
                  placeholder="选择期望难度"
                />
              </label>
              <label class="field">
                <span>辅导方式</span>
                <n-select
                  v-model:value="profile.preferences.tutoring_style"
                  :options="tutoringOptions"
                  filterable
                  tag
                  placeholder="选择或输入辅导方式"
                />
              </label>
              <label class="field field-wide">
                <span>内容偏好</span>
                <n-select
                  v-model:value="profile.preferences.content_style"
                  :options="contentStyleOptions"
                  multiple
                  filterable
                  tag
                  placeholder="可多选，也可以输入自定义偏好"
                />
                <small>建议选择 1-3 项，系统会据此调整解释方式、案例和内容组织。</small>
              </label>
            </div>
          </section>

          <section class="future-grid">
            <article>
              <BookOpenCheck :size="20" />
              <div><strong>课程画像</strong><span>按课程累计知识点掌握度</span></div>
              <em>下一阶段</em>
            </article>
            <article>
              <History :size="20" />
              <div><strong>学习证据</strong><span>记录答题、复听和任务完成</span></div>
              <em>规划中</em>
            </article>
            <article>
              <Bot :size="20" />
              <div><strong>画像 Agent</strong><span>提出可确认的画像更新建议</span></div>
              <em>规划中</em>
            </article>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NInput, NSelect, useMessage, type SelectOption } from 'naive-ui'
import {
  BookOpenCheck,
  Bot,
  CircleDashed,
  CircleCheckBig,
  History,
  IdCard,
  LoaderCircle,
  Save,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  UserRound,
} from 'lucide-vue-next'
import { getLearnerProfile, saveLearnerProfile, type LearnerProfile } from '@/api/learnerProfile'
import {
  createEmptyLearnerProfile,
  mergeLegacyStudentProfile,
  readLegacyStudentProfile,
  shouldMigrateLegacyProfile,
  UNIVERSITY_STAGE_VALUES,
  writeLegacyStudentProfile,
} from '@/utils/learnerProfile'

const message = useMessage()
const profile = ref<LearnerProfile>(createEmptyLearnerProfile())
const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const profileReady = ref(false)
const loadError = ref('')
let stopWatching: (() => void) | null = null

const stageOptions: SelectOption[] = UNIVERSITY_STAGE_VALUES.map((value) => ({
  label: value,
  value,
}))
const basisOptions: SelectOption[] = [
  { label: '零基础', value: '零基础' },
  { label: '有基础', value: '有基础' },
  { label: '进阶学习', value: '进阶学习' },
]
const goalOptions: SelectOption[] = [
  { label: '概念理解', value: '概念理解' },
  { label: '考试通过', value: '考试通过' },
  { label: '项目实战', value: '项目实战' },
  { label: '能力提升', value: '能力提升' },
]
const difficultyOptions: SelectOption[] = [
  { label: '基础', value: '基础' },
  { label: '中等', value: '中等' },
  { label: '挑战', value: '挑战' },
]
const tutoringOptions: SelectOption[] = [
  { label: '引导式', value: '引导式' },
  { label: '分步讲解', value: '分步讲解' },
  { label: '直接反馈', value: '直接反馈' },
  { label: '启发提问', value: '启发提问' },
]
const contentStyleOptions: SelectOption[] = [
  { label: '图解', value: '图解' },
  { label: '案例', value: '案例' },
  { label: '步骤推导', value: '步骤推导' },
  { label: '对比辨析', value: '对比辨析' },
  { label: '代码实操', value: '代码实操' },
  { label: '精简总结', value: '精简总结' },
]

const avatarText = computed(() => profile.value.basic.display_name.trim().slice(0, 1) || '学')
const summaryTags = computed(() => [
  profile.value.preferences.goal,
  ...profile.value.preferences.content_style,
  profile.value.preferences.preferred_difficulty,
].filter(Boolean))

function startDirtyWatch() {
  stopWatching?.()
  stopWatching = watch(profile, () => {
    dirty.value = true
  }, { deep: true })
}

async function loadProfile() {
  loading.value = true
  profileReady.value = false
  loadError.value = ''
  stopWatching?.()
  try {
    let loaded = await getLearnerProfile()
    const legacy = readLegacyStudentProfile(localStorage)
    if (shouldMigrateLegacyProfile(loaded, legacy)) {
      loaded = await saveLearnerProfile(mergeLegacyStudentProfile(loaded, legacy!))
      message.success('已迁移原有课堂画像')
    }
    profile.value = loaded
    dirty.value = false
    profileReady.value = true
    startDirtyWatch()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '学习档案加载失败'
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const saved = await saveLearnerProfile(profile.value)
    stopWatching?.()
    profile.value = saved
    writeLegacyStudentProfile(localStorage, saved)
    dirty.value = false
    startDirtyWatch()
    message.success('学习画像已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadProfile)
onBeforeUnmount(() => stopWatching?.())
</script>

<style scoped>
.learner-page {
  position: relative;
  height: 100%;
  overflow: auto;
  background:
    linear-gradient(135deg, rgb(var(--bg-base-rgb)) 0%, rgb(var(--bg-inset-rgb) / 0.72) 100%);
  color: rgb(var(--ink-1-rgb));
}

.page-glow {
  position: fixed;
  pointer-events: none;
  border-radius: 999px;
  filter: blur(4px);
  opacity: 0.58;
}

.glow-a {
  width: 340px;
  height: 340px;
  top: 84px;
  right: 5%;
  background: radial-gradient(circle, rgb(var(--nav-classroom-rgb) / 0.12), transparent 68%);
}

.glow-b {
  width: 280px;
  height: 280px;
  left: 3%;
  bottom: 3%;
  background: radial-gradient(circle, rgb(var(--amber-rgb) / 0.10), transparent 70%);
}

.learner-shell {
  position: relative;
  z-index: 1;
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
  padding: 34px 0 48px;
}

.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 28px;
  margin-bottom: 24px;
  animation: rise-in 420ms var(--ease-out) both;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: rgb(var(--nav-classroom-rgb));
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.hero h1 {
  margin: 10px 0 8px;
  max-width: 680px;
  font-family: "HarmonyOS Sans SC", "Microsoft YaHei", sans-serif;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.12;
  letter-spacing: -0.035em;
}

.hero p {
  max-width: 720px;
  margin: 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 14px;
  line-height: 1.75;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.save-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgb(var(--warning-rgb));
  font-size: 12px;
  white-space: nowrap;
}

.save-state.saved {
  color: rgb(var(--success-rgb));
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  border: 0;
  border-radius: 9px;
  background: rgb(var(--nav-classroom-rgb));
  color: white;
  padding: 0 17px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 8px 22px rgb(var(--nav-classroom-rgb) / 0.18);
  transition: transform var(--duration-fast), opacity var(--duration-fast);
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  border: 1px solid rgb(var(--danger-rgb) / 0.25);
  border-radius: 10px;
  background: rgb(var(--danger-rgb) / 0.07);
  color: rgb(var(--danger-rgb));
  padding: 11px 14px;
  font-size: 13px;
}

.error-banner button {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: inherit;
  font-weight: 700;
  cursor: pointer;
}

.profile-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 18px;
  transition: opacity var(--duration-base);
}

.profile-layout.loading {
  opacity: 0.48;
  pointer-events: none;
}

.profile-layout.unavailable {
  pointer-events: none;
  user-select: none;
}

.profile-card {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 16px;
  background: rgb(var(--bg-surface-rgb) / 0.92);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(16px);
}

.identity-card {
  position: sticky;
  top: 20px;
  align-self: start;
  overflow: hidden;
  padding: 24px;
  animation: rise-in 480ms 60ms var(--ease-out) both;
}

.identity-card::before {
  position: absolute;
  content: "";
  inset: 0 0 auto;
  height: 5px;
  background: linear-gradient(90deg, rgb(var(--nav-classroom-rgb)), rgb(var(--amber-rgb)));
}

.identity-mark {
  display: grid;
  place-items: center;
  width: 66px;
  height: 66px;
  margin-bottom: 22px;
  border: 1px solid rgb(var(--nav-classroom-rgb) / 0.18);
  border-radius: 18px 18px 18px 5px;
  background:
    linear-gradient(145deg, rgb(var(--nav-classroom-rgb) / 0.16), rgb(var(--amber-rgb) / 0.10));
  color: rgb(var(--nav-classroom-rgb));
  font-size: 26px;
  font-weight: 750;
}

.card-kicker {
  margin: 0 0 6px;
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.identity-card h2 {
  margin: 0;
  font-size: 21px;
}

.identity-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 7px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.identity-meta span {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgb(var(--ink-4-rgb));
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 22px 0;
}

.profile-tags span {
  border-radius: 999px;
  background: rgb(var(--nav-classroom-rgb) / 0.09);
  color: rgb(var(--nav-classroom-rgb));
  padding: 5px 9px;
  font-size: 11px;
}

.profile-tags .empty-tag {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
}

.phase-note {
  display: flex;
  gap: 10px;
  border-radius: 12px;
  background: rgb(var(--amber-rgb) / 0.09);
  color: rgb(var(--amber-rgb));
  padding: 13px;
}

.phase-note svg {
  flex-shrink: 0;
  margin-top: 1px;
}

.phase-note strong {
  display: block;
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
}

.phase-note p {
  margin: 4px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
  line-height: 1.55;
}

.form-stack {
  display: grid;
  gap: 16px;
}

.form-card {
  padding: 22px;
  animation: rise-in 500ms 100ms var(--ease-out) both;
}

.form-card:nth-child(2) {
  animation-delay: 160ms;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: rgb(var(--nav-classroom-rgb) / 0.10);
  color: rgb(var(--nav-classroom-rgb));
}

.section-icon.warm {
  background: rgb(var(--amber-rgb) / 0.11);
  color: rgb(var(--amber-rgb));
}

.section-head h2 {
  margin: 0;
  font-size: 16px;
}

.section-head p {
  margin: 4px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 17px 14px;
}

.field {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.field > span {
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
  font-weight: 650;
}

.field small {
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
}

.field-wide {
  grid-column: 1 / -1;
}

.future-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  animation: rise-in 520ms 220ms var(--ease-out) both;
}

.future-grid article {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 11px;
  border: 1px dashed rgb(var(--line-strong-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb) / 0.55);
  color: rgb(var(--ink-4-rgb));
  padding: 14px;
}

.future-grid strong,
.future-grid span {
  display: block;
}

.future-grid strong {
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
}

.future-grid span {
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.4;
}

.future-grid em {
  grid-column: 2;
  width: fit-content;
  border-radius: 999px;
  background: rgb(var(--bg-subtle-rgb));
  padding: 3px 7px;
  font-size: 9px;
  font-style: normal;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes rise-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 900px) {
  .hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-layout {
    grid-template-columns: 1fr;
  }

  .identity-card {
    position: static;
  }

  .future-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .learner-shell {
    width: min(100% - 24px, 1180px);
    padding-top: 22px;
  }

  .hero-actions {
    width: 100%;
    align-items: stretch;
    flex-direction: column;
  }

  .primary-btn {
    width: 100%;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: auto;
  }
}
</style>
