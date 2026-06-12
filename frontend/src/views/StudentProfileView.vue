<template>
  <div class="learner-page">
    <div class="page-glow glow-a"></div>
    <div class="page-glow glow-b"></div>

    <main class="learner-shell">
      <header class="hero">
        <div class="hero-copy">
          <div class="eyebrow"><UserRound :size="15" /> 学习者中心</div>
          <h1>让每次生成，更懂你的学习方式</h1>
          <p>这是你的个性化学习档案。系统会结合你的偏好和学习表现，持续调整课堂内容与练习。</p>
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
              <strong>Profile Agent 已接入</strong>
              <p>课堂表现只会生成学习建议，未经你的确认不会改变个性化学习设置。</p>
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
              <button
                type="button"
                class="clear-section-btn"
                :disabled="!profileReady || loading || saving"
                @click="confirmClearBasic"
              >
                <Trash2 :size="14" />
                清空
              </button>
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
              <button
                type="button"
                class="clear-section-btn"
                :disabled="!profileReady || loading || saving"
                @click="confirmClearPreferences"
              >
                <Trash2 :size="14" />
                清空
              </button>
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

          <section class="profile-card form-card">
            <div class="section-head">
              <div class="section-icon"><BrainCircuit :size="19" /></div>
              <div>
                <h2>认知与兴趣</h2>
                <p>这是跨课程生效的全局画像，保存后会影响课堂讲解方式和案例语境。</p>
              </div>
            </div>

            <div class="form-grid">
              <label class="field field-wide">
                <span>认知偏好</span>
                <n-select
                  v-model:value="selectedCognitivePreferences"
                  :options="cognitivePreferenceOptions"
                  multiple
                  placeholder="选择更容易理解内容的方式"
                />
                <small>可多选。手动保存的偏好会作为已确认特征进入生成策略。</small>
              </label>
              <label class="field field-wide">
                <span>兴趣方向</span>
                <n-select
                  v-model:value="selectedInterestDirections"
                  :options="interestDirectionOptions"
                  multiple
                  filterable
                  tag
                  placeholder="选择或输入感兴趣的应用方向"
                />
                <small>兴趣方向用于选择案例背景，不会改变课程知识目标。</small>
              </label>
            </div>
          </section>

          <section class="profile-card insight-card">
            <div class="section-head">
              <div class="section-icon"><BookOpenCheck :size="19" /></div>
              <div>
                <h2>我的课程学习情况</h2>
                <p>查看知识点掌握情况、当前学习卡点和知识应用情况。</p>
              </div>
              <button
                type="button"
                class="clear-section-btn"
                :disabled="!profileReady || loading || saving || !courseProfiles.length"
                @click="confirmClearAllCourses"
              >
                <Trash2 :size="14" />
                全部清空
              </button>
            </div>
            <div v-if="courseProfiles.length" class="course-grid">
              <article v-for="course in courseProfiles" :key="course.course_id" class="course-card">
                <div class="course-head">
                  <div>
                    <strong>{{ course.course_name || '未命名课程' }}</strong>
                    <span>{{ trendLabel(course.recent_trend) }}</span>
                  </div>
                  <div class="course-meta-actions">
                    <em>{{ Object.keys(course.mastery || {}).length }} 个知识点</em>
                    <button
                      type="button"
                      class="clear-course-btn"
                      :disabled="!profileReady || loading || saving"
                      @click="confirmClearCourse(course.course_id, course.course_name)"
                    >
                      清空
                    </button>
                  </div>
                </div>
                <div class="mastery-mini-list">
                  <div
                    v-for="(point, pointId) in course.mastery"
                    :key="pointId"
                    class="mastery-mini-row"
                  >
                    <span>{{ point.name }}</span>
                    <div><i :style="{ width: `${point.score}%` }"></i></div>
                    <strong>{{ point.score }}%</strong>
                  </div>
                </div>
                <div class="course-trait-grid">
                  <div>
                    <span>当前学习卡点</span>
                    <div class="trait-chips">
                      <em
                        v-for="pattern in confirmedErrorPatterns(course)"
                        :key="pattern"
                      >
                        {{ errorPatternLabel(pattern) }}
                      </em>
                      <small v-if="!confirmedErrorPatterns(course).length">暂未发现稳定的学习卡点</small>
                    </div>
                  </div>
                  <div>
                    <span>知识应用情况</span>
                    <strong>{{ transferAbilityText(course) }}</strong>
                  </div>
                </div>
              </article>
            </div>
            <div v-else class="empty-panel">完成课堂和练习后，这里会逐步形成你的课程学习分析。</div>
          </section>

          <section class="profile-card insight-card">
            <div class="section-head">
              <div class="section-icon warm"><Bot :size="19" /></div>
              <div>
                <h2>学习分析建议</h2>
                <p>你可以决定是否将分析结果用于后续个性化课堂和练习。</p>
              </div>
            </div>
            <div v-if="pendingUpdates.length" class="update-list">
              <article v-for="update in pendingUpdates" :key="update.id" class="update-card">
                <div class="update-head">
                  <div>
                    <span>{{ update.course_name || '课程学习情况' }}</span>
                    <strong>{{ profileUpdateTitle(update) }}</strong>
                  </div>
                  <em>分析可信度 {{ Math.round((update.confidence || 0) * 100) }}%</em>
                </div>
                <div class="change-value">
                  {{ formatProfileUpdateChange(update) }}
                </div>
                <p>{{ update.reason || '系统根据近期学习证据提出此建议。' }}</p>
                <small>根据 {{ update.evidence_ids?.length || 0 }} 次学习表现分析</small>
                <div class="update-actions">
                  <button
                    class="accept-btn"
                    :disabled="resolvingUpdateId === update.id"
                    @click="handleUpdate(update, 'accept')"
                  >
                    应用到个性化学习
                  </button>
                  <label v-if="update.type === 'mastery_adjustment'">
                    <input
                      v-model.number="modifiedScores[update.id]"
                      type="number"
                      min="0"
                      max="100"
                    />
                    <button
                      :disabled="resolvingUpdateId === update.id"
                      @click="handleUpdate(update, 'modify')"
                    >
                      按此分值确认
                    </button>
                  </label>
                  <button
                    class="ignore-btn"
                    :disabled="resolvingUpdateId === update.id"
                    @click="handleUpdate(update, 'ignore')"
                  >
                    暂不采用
                  </button>
                </div>
              </article>
            </div>
            <div v-else class="empty-panel">当前没有新的学习分析建议。</div>
          </section>

          <section class="profile-card insight-card">
            <div class="section-head">
              <div class="section-icon"><History :size="19" /></div>
              <div>
                <h2>下一步建议</h2>
                <p>根据最近课堂表现和已确认的课程学习情况推荐。</p>
              </div>
            </div>
            <div v-if="recentRecommendations.length" class="recommendation-list">
              <article v-for="item in recentRecommendations" :key="`${item.classroom_id}-${item.id}`">
                <strong>{{ item.title }}</strong>
                <span>{{ item.description }}</span>
                <small v-if="item.reason">{{ item.reason }}</small>
              </article>
            </div>
            <div v-else class="empty-panel">完成课堂报告后，这里会显示可执行的后续学习建议。</div>
          </section>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NInput, NSelect, useDialog, useMessage, type SelectOption } from 'naive-ui'
import {
  BookOpenCheck,
  Bot,
  BrainCircuit,
  CircleDashed,
  CircleCheckBig,
  History,
  IdCard,
  LoaderCircle,
  Save,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  Trash2,
  UserRound,
} from 'lucide-vue-next'
import {
  getLearnerProfile,
  resolveLearnerProfileUpdate,
  saveLearnerProfile,
  type LearnerProfile,
  type LearnerCourseProfile,
  type LearnerProfileUpdate,
} from '@/api/learnerProfile'
import {
  clearLearnerCourseProfile,
  clearLearnerCourses,
  clearLearnerProfileBasic,
  clearLearnerProfilePreferences,
  createEmptyLearnerProfile,
  mergeLegacyStudentProfile,
  readLegacyStudentProfile,
  shouldMigrateLegacyProfile,
  UNIVERSITY_STAGE_VALUES,
  writeLegacyStudentProfile,
} from '@/utils/learnerProfile'
import {
  formatProfileUpdateChange,
  pendingProfileUpdates,
  profileUpdateTitle,
  trendLabel,
} from '@/utils/learnerProfileUpdates'

const message = useMessage()
const dialog = useDialog()
const profile = ref<LearnerProfile>(createEmptyLearnerProfile())
const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const profileReady = ref(false)
const loadError = ref('')
const resolvingUpdateId = ref('')
const modifiedScores = ref<Record<string, number>>({})
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
const cognitivePreferenceOptions: SelectOption[] = [
  { label: '图示结构', value: 'visual_structure' },
  { label: '案例理解', value: 'example_based' },
  { label: '步骤推导', value: 'step_by_step' },
  { label: '对比辨析', value: 'comparison' },
  { label: '文字概括', value: 'text_summary' },
  { label: '实践操作', value: 'hands_on' },
]
const interestDirectionOptions: SelectOption[] = [
  { label: '人工智能应用', value: '人工智能应用' },
  { label: '软件开发', value: '软件开发' },
  { label: '数据分析', value: '数据分析' },
  { label: '工程实践', value: '工程实践' },
  { label: '生活应用', value: '生活应用' },
]

const selectedCognitivePreferences = computed<string[]>({
  get: () => Object.entries(profile.value.global_traits?.cognitive_preferences || {})
    .filter(([, trait]) => trait.status === 'confirmed')
    .map(([key]) => key),
  set: (keys) => {
    const previous = profile.value.global_traits?.cognitive_preferences || {}
    profile.value.global_traits.cognitive_preferences = Object.fromEntries(
      keys.map((key) => [
        key,
        {
          ...(previous[key] || {}),
          weight: previous[key]?.weight || 1,
          confidence: 1,
          source: 'self_reported',
          status: 'confirmed',
          evidence_ids: previous[key]?.evidence_ids || [],
        },
      ]),
    )
  },
})

const selectedInterestDirections = computed<string[]>({
  get: () => (profile.value.global_traits?.interest_directions || [])
    .filter((trait) => trait.status === 'confirmed')
    .map((trait) => trait.label),
  set: (labels) => {
    const previous = new Map(
      (profile.value.global_traits?.interest_directions || [])
        .map((trait) => [trait.label, trait]),
    )
    profile.value.global_traits.interest_directions = labels.map((label) => ({
      ...(previous.get(label) || {}),
      label,
      weight: previous.get(label)?.weight || 1,
      confidence: 1,
      source: 'self_reported',
      status: 'confirmed',
      evidence_ids: previous.get(label)?.evidence_ids || [],
    }))
  },
})

const avatarText = computed(() => profile.value.basic.display_name.trim().slice(0, 1) || '学')
const summaryTags = computed(() => [
  profile.value.preferences.goal,
  ...profile.value.preferences.content_style,
  profile.value.preferences.preferred_difficulty,
  ...selectedCognitivePreferences.value.map(cognitivePreferenceLabel),
  ...selectedInterestDirections.value,
].filter(Boolean))
const courseProfiles = computed(() => Object.values(profile.value.courses || {}))
const pendingUpdates = computed(() => pendingProfileUpdates(profile.value.pending_updates || []))
const recentRecommendations = computed(() => (
  [...(profile.value.recent_recommendations || [])].reverse().slice(0, 6)
))

function startDirtyWatch() {
  stopWatching?.()
  stopWatching = watch(profile, () => {
    dirty.value = true
  }, { deep: true })
}

function confirmProfileClear(options: {
  title: string
  content: string
  positiveText: string
  apply: (current: LearnerProfile) => LearnerProfile
  success: string
}) {
  dialog.warning({
    title: options.title,
    content: options.content,
    positiveText: options.positiveText,
    negativeText: '取消',
    onPositiveClick: async () => {
      saving.value = true
      try {
        const nextProfile = options.apply(profile.value)
        const saved = await saveLearnerProfile(nextProfile)
        stopWatching?.()
        profile.value = saved
        writeLegacyStudentProfile(localStorage, saved)
        dirty.value = false
        startDirtyWatch()
        message.success(options.success)
      } catch (error) {
        message.error(error instanceof Error ? error.message : '清空失败')
      } finally {
        saving.value = false
      }
    },
  })
}

function confirmClearBasic() {
  confirmProfileClear({
    title: '清空基本信息',
    content: '将清空称呼、学习阶段、当前基础和学习背景，并立即写入学习档案。',
    positiveText: '清空基本信息',
    apply: clearLearnerProfileBasic,
    success: '已清空基本信息',
  })
}

function confirmClearPreferences() {
  confirmProfileClear({
    title: '清空学习偏好',
    content: '将清空学习目标、期望难度、辅导方式和内容偏好，并立即写入学习档案。',
    positiveText: '清空学习偏好',
    apply: clearLearnerProfilePreferences,
    success: '已清空学习偏好',
  })
}

function confirmClearAllCourses() {
  confirmProfileClear({
    title: '清空全部课程学习情况',
    content: '将删除所有已确认的知识点掌握情况，并移除相关学习分析建议和推荐。',
    positiveText: '全部清空',
    apply: clearLearnerCourses,
    success: '已清空全部课程学习情况',
  })
}

function confirmClearCourse(courseId: string, courseName?: string) {
  confirmProfileClear({
    title: '清空课程学习情况',
    content: `将删除“${courseName || '该课程'}”的知识点掌握情况，并移除相关学习分析建议和推荐。`,
    positiveText: '清空该课程',
    apply: (current) => clearLearnerCourseProfile(current, courseId),
    success: '已清空该课程学习情况',
  })
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

async function handleUpdate(
  update: LearnerProfileUpdate,
  action: 'accept' | 'modify' | 'ignore',
) {
  const modifiedAfter = action === 'modify' && update.type === 'mastery_adjustment'
    ? modifiedScores.value[update.id] ?? Number(update.after || 0)
    : undefined
  if (
    action === 'modify'
    && update.type === 'mastery_adjustment'
    && (modifiedAfter === undefined || modifiedAfter < 0 || modifiedAfter > 100)
  ) {
    message.warning('请输入 0-100 的掌握度')
    return
  }
  resolvingUpdateId.value = update.id
  try {
    const saved = await resolveLearnerProfileUpdate(update.id, action, modifiedAfter)
    stopWatching?.()
    profile.value = saved
    dirty.value = false
    startDirtyWatch()
    message.success(action === 'ignore' ? '已暂不采用这条建议' : '已应用到个性化学习')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '画像建议处理失败')
  } finally {
    resolvingUpdateId.value = ''
  }
}

const ERROR_PATTERN_LABELS: Record<string, string> = {
  concept_confusion: '容易混淆相近概念',
  prerequisite_gap: '建议先补充相关基础知识',
  procedural_error: '解题步骤还不稳定',
  application_failure: '将知识用于新问题时有困难',
  careless_error: '需要加强题目条件检查',
  expression_gap: '思路基本正确，但表达不够完整',
}

const TRANSFER_LEVEL_LABELS: Record<string, string> = {
  unobserved: '完成更多练习后生成分析',
  recall: '已能理解基础概念',
  near_transfer: '能完成相似类型的问题',
  far_transfer: '能解决新的应用问题',
  integrated_problem_solving: '能综合运用多个知识点',
}

function cognitivePreferenceLabel(key: string): string {
  return String(cognitivePreferenceOptions.find((item) => item.value === key)?.label || key)
}

function confirmedErrorPatterns(course: LearnerCourseProfile): string[] {
  return Object.entries(course.error_patterns || {})
    .filter(([, pattern]) => pattern.status === 'confirmed')
    .map(([key]) => key)
}

function errorPatternLabel(key: string): string {
  return ERROR_PATTERN_LABELS[key] || key
}

function transferAbilityText(course: LearnerCourseProfile): string {
  const transfer = course.transfer_ability
  if (!transfer || transfer.status !== 'confirmed') return '完成更多练习后生成分析'
  const label = TRANSFER_LEVEL_LABELS[transfer.level] || transfer.level
  return label
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

.section-head > div:nth-child(2) {
  min-width: 0;
  flex: 1;
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

.clear-section-btn,
.clear-course-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px solid rgb(var(--danger-rgb) / 0.18);
  border-radius: 8px;
  background: rgb(var(--danger-rgb) / 0.06);
  color: rgb(var(--danger-rgb));
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background var(--duration-fast),
    border-color var(--duration-fast),
    transform var(--duration-fast),
    opacity var(--duration-fast);
}

.clear-section-btn {
  height: 32px;
  padding: 0 10px;
}

.clear-course-btn {
  height: 26px;
  padding: 0 9px;
  font-size: 11px;
}

.clear-section-btn:hover:not(:disabled),
.clear-course-btn:hover:not(:disabled) {
  border-color: rgb(var(--danger-rgb) / 0.30);
  background: rgb(var(--danger-rgb) / 0.10);
  transform: translateY(-1px);
}

.clear-section-btn:disabled,
.clear-course-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
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

.insight-card {
  padding: 22px;
  animation: rise-in 520ms 220ms var(--ease-out) both;
}

.course-grid,
.update-list,
.recommendation-list {
  display: grid;
  gap: 12px;
}

.empty-panel {
  border: 1px dashed rgb(var(--line-strong-rgb));
  border-radius: 12px;
  color: rgb(var(--ink-4-rgb));
  padding: 18px;
  text-align: center;
  font-size: 12px;
}

.course-card,
.update-card,
.recommendation-list article {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-inset-rgb) / 0.46);
  padding: 15px;
}

.course-head,
.update-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.course-head strong,
.course-head span,
.update-head span,
.update-head strong {
  display: block;
}

.course-head strong,
.update-head strong,
.recommendation-list strong {
  color: rgb(var(--ink-1-rgb));
  font-size: 13px;
}

.course-head span,
.update-head span {
  margin-top: 3px;
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
}

.course-head em,
.update-head em {
  color: rgb(var(--nav-classroom-rgb));
  font-size: 10px;
  font-style: normal;
}

.course-meta-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.mastery-mini-list {
  display: grid;
  gap: 9px;
  margin-top: 14px;
}

.mastery-mini-row {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) minmax(120px, 2fr) 42px;
  align-items: center;
  gap: 10px;
  font-size: 11px;
}

.mastery-mini-row > div {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgb(var(--line-rgb));
}

.mastery-mini-row i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: rgb(var(--nav-classroom-rgb));
}

.course-trait-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(120px, 0.8fr);
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgb(var(--line-rgb));
}

.course-trait-grid > div {
  min-width: 0;
}

.course-trait-grid > div > span {
  display: block;
  margin-bottom: 7px;
  color: rgb(var(--ink-4-rgb));
  font-size: 10px;
  font-weight: 650;
}

.course-trait-grid strong {
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
}

.trait-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.trait-chips em {
  border-radius: 999px;
  background: rgb(var(--amber-rgb) / 0.10);
  color: rgb(var(--amber-rgb));
  padding: 4px 8px;
  font-size: 10px;
  font-style: normal;
}

.trait-chips small {
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
}

.change-value {
  margin: 12px 0 6px;
  color: rgb(var(--nav-classroom-rgb));
  font-size: 18px;
  font-weight: 750;
}

.update-card p,
.recommendation-list span,
.recommendation-list small {
  display: block;
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
  line-height: 1.65;
}

.update-card small {
  color: rgb(var(--ink-4-rgb));
}

.update-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 13px;
}

.update-actions label {
  display: flex;
}

.update-actions input {
  width: 62px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 7px 0 0 7px;
  padding: 0 8px;
}

.update-actions button {
  min-height: 32px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 7px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  padding: 0 11px;
  cursor: pointer;
}

.update-actions label button {
  border-left: 0;
  border-radius: 0 7px 7px 0;
}

.update-actions .accept-btn {
  border-color: rgb(var(--nav-classroom-rgb));
  background: rgb(var(--nav-classroom-rgb));
  color: white;
}

.update-actions .ignore-btn {
  color: rgb(var(--ink-4-rgb));
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

  .course-trait-grid {
    grid-template-columns: 1fr;
  }
}
</style>
