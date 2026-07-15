<template>
  <div v-if="classroom && currentScene" class="player">
    <aside class="scene-list">
      <button class="back-btn" type="button" title="返回智慧课堂" @click="goBackToList">
        <ArrowLeft class="back-icon" />
        <span>返回智慧课堂</span>
      </button>
      <div class="scene-list-head">
        <div class="scene-list-title">课堂场景</div>
        <div class="scene-list-meta">{{ currentIndex + 1 }} / {{ displaySceneTotal }}</div>
      </div>

      <button
        v-for="(scene, idx) in orderedScenes"
        :key="scene.id"
        class="scene-btn"
        :class="{ active: idx === currentIndex, locked: scene.type === 'report' && !canOpenReportScene }"
        @click="selectScene(idx)"
      >
          <span class="scene-index">{{ idx + 1 }}</span>
          <span class="scene-copy">
          <span class="scene-title">{{ formatSceneTitle(scene) }}</span>
          <span class="scene-type">{{ sceneTypeLabel(scene.type) }}</span>
        </span>
      </button>

      <button
        v-for="scene in lockedPreviewScenes"
        :key="scene.id"
        class="scene-btn scene-btn-generating locked"
        type="button"
        disabled
      >
        <span class="scene-index locked-index">
          <Lock class="locked-icon" />
        </span>
        <span class="scene-copy">
          <span class="scene-title">{{ scene.title }}</span>
          <span class="scene-type">正在生成语音与页面</span>
        </span>
      </button>

      <div v-if="previewTailStatus" class="scene-generation-status">
        <span class="status-dot" />
        <span>{{ previewTailStatus }}</span>
      </div>
    </aside>

    <main class="stage">
      <section class="scene-body">
        <div v-if="currentScene.type === 'slide'" class="slide-wrap">
          <div v-if="sceneSvg" ref="svgStageRef" class="svg-stage">
            <div ref="svgBoxRef" class="svg-box" v-html="sanitizeSvg(sceneSvg)" />
            <div
              v-if="activeHighlight && highlightLayerStyle && highlightBoxStyle"
              class="highlight-layer"
              :style="highlightLayerStyle"
            >
              <Transition name="spotlight-mask">
                <div
                  v-if="activeHighlight.mode === 'spotlight'"
                  class="highlight-spotlight"
                  :style="highlightBoxStyle"
                />
              </Transition>
              <div
                class="highlight-box"
                :class="{ spotlight: activeHighlight.mode === 'spotlight' }"
                :style="highlightBoxStyle"
              />
            </div>
          </div>
          <pre v-else class="md-box">{{ sceneMarkdown || '本页暂无内容' }}</pre>
        </div>

        <div v-else-if="currentScene.type === 'mindmap'" class="mindmap-wrap">
          <MindmapScene
            :markdown="sceneMarkmapMd"
            :title="currentScene.title"
          />
        </div>

        <div v-else-if="currentScene.type === 'animation_lab'" class="animation-lab-wrap">
          <div class="animation-lab-panel">
            <div class="animation-lab-head">
              <div>
                <div class="animation-lab-kicker">互动动画实验</div>
                <h2>{{ currentScene.title }}</h2>
                <p>{{ animationLabSummary || '通过参数调节观察关键变量之间的关系。' }}</p>
              </div>
            </div>
            <iframe
              class="animation-lab-frame"
              sandbox="allow-scripts"
              :srcdoc="animationLabHtml"
            />
          </div>
        </div>

        <div v-else-if="currentScene.type === 'quiz'" class="quiz-wrap">
          <div v-for="(q, qIndex) in questions" :key="q.id" class="question-card">
            <div class="question-head">
              <span class="question-index">Q{{ qIndex + 1 }}</span>
              <div class="q-title">
                {{ q.question }}
                <span v-if="q.type === 'short_answer'" class="question-type-tag">简答题</span>
                <span v-else-if="q.type === 'multiple'" class="question-type-tag">多选题</span>
              </div>
            </div>

            <div v-if="q.type === 'short_answer'" class="short-answer-area">
              <textarea
                class="short-answer-input"
                :rows="5"
                :placeholder="currentQuizResult ? '已提交' : '请输入你的回答（提交后由 AI 评分）'"
                :value="(currentAnswers[q.id] && currentAnswers[q.id][0]) || ''"
                :disabled="!!currentQuizResult || submitting"
                @input="onShortAnswerInput(q.id, $event)"
              />
              <div v-if="!currentQuizResult" class="short-answer-hint">
                AI 会按准确性 / 完整性 / 表达 三个维度打分（0-100），80 分及以上视为掌握
              </div>
            </div>

            <div v-else class="option-list">
              <button
                v-for="opt in q.options"
                :key="opt.value"
                type="button"
                class="option-btn"
                :class="optionClass(q.id, opt.value)"
                @click="setAnswer(q.id, opt.value)"
              >
                <span class="option-key">{{ opt.value }}</span>
                <span class="option-text">{{ opt.label }}</span>
                <CheckCircle v-if="isCorrectOption(q.id, opt.value)" class="option-icon good" />
                <XCircle v-else-if="isWrongSelectedOption(q.id, opt.value)" class="option-icon bad" />
              </button>
            </div>

            <div v-if="resultByQuestion[q.id]" class="analysis-box">
              <template v-if="q.type === 'short_answer'">
                <div class="analysis-title analysis-row">
                  <span>
                    {{ resultByQuestion[q.id].correct ? '已掌握（≥80 分）' : '需要补强' }}
                  </span>
                  <span v-if="typeof resultByQuestion[q.id].score === 'number'" class="short-answer-score">
                    {{ resultByQuestion[q.id].score }} / 100
                  </span>
                </div>
                <div v-if="resultByQuestion[q.id].feedback" class="analysis-copy">
                  <strong>AI 评语：</strong>{{ resultByQuestion[q.id].feedback }}
                </div>
                <div v-if="resultByQuestion[q.id].analysis" class="analysis-copy analysis-muted">
                  参考要点：{{ resultByQuestion[q.id].analysis }}
                </div>
              </template>
              <template v-else>
                <div class="analysis-title">
                  {{ resultByQuestion[q.id].correct ? '回答正确' : '还需要巩固' }}
                </div>
                <div class="analysis-copy">{{ resultByQuestion[q.id].analysis || '暂无解析' }}</div>
              </template>
              <button
                type="button"
                class="analysis-to-discussion"
                @click="sendQuestionToDiscussion(q)"
              >
                <MessageSquare class="analysis-to-discussion-icon" />
                传至讨论
              </button>
            </div>
          </div>

          <div class="quiz-actions">
            <button class="primary-btn" :disabled="isGeneratingPreview || submitting || !allAnswered" @click="submitQuiz">
              {{ submitting ? '提交中...' : '提交答案' }}
            </button>
            <button class="secondary-btn" :disabled="isGeneratingPreview || submitting" @click="resetQuiz">重做</button>
            <button class="secondary-btn" :disabled="!currentQuizResult" @click="goNext">下一页</button>
          </div>

          <div v-if="currentQuizResult" class="result-box">
            <div class="score-ring">{{ currentQuizResult.score }}%</div>
            <div>
              <div class="result-summary">
                完成 {{ currentQuizResult.total }} 题，答对 {{ currentQuizResult.correct }} 题
              </div>
              <div class="result-tip">{{ feedbackText || '系统已记录本次答题结果。' }}</div>
            </div>
          </div>
        </div>

        <div v-else-if="currentScene.type === 'report'" class="report-page">
          <div v-if="reportLoading && !report" class="report-empty">
            <div class="report-kicker">课后学习报告</div>
            <h3>正在整理本节课堂表现...</h3>
          </div>

          <div v-else-if="report" class="report-sheet">
            <div class="report-hero">
              <div>
                <div class="report-kicker">课后学习报告</div>
                <h3>{{ report.topic }}</h3>
                <p>{{ report.next_recommendation }}</p>
              </div>
              <div class="report-score-card">
                <span>综合得分</span>
                <strong>{{ report.score }}%</strong>
              </div>
            </div>

            <div class="report-grid">
              <div class="report-metric">
                <span>答题进度</span>
                <strong>{{ report.answered_quiz_count }} / {{ report.quiz_scene_count }}</strong>
              </div>
              <div class="report-metric">
                <span>正确题数</span>
                <strong>{{ report.correct }} / {{ report.total }}</strong>
              </div>
              <div class="report-metric">
                <span>得分</span>
                <strong>{{ report.earned_points }} / {{ report.total_points }}</strong>
              </div>
            </div>

            <div class="report-columns">
              <section class="report-block">
                <div class="report-label">薄弱点</div>
                <div v-if="report.weak_points.length" class="tag-row">
                  <span v-for="point in report.weak_points" :key="point" class="tag weak">{{ point }}</span>
                </div>
                <p v-else class="muted-copy">本节暂无明显薄弱点，可以继续进入下一阶段学习。</p>
              </section>

              <section class="report-block">
                <div class="report-label">强项</div>
                <div v-if="report.strong_points.length" class="tag-row">
                  <span v-for="point in report.strong_points" :key="point" class="tag strong">{{ point }}</span>
                </div>
                <p v-else class="muted-copy">完成更多测验后，系统会沉淀更稳定的强项判断。</p>
              </section>
            </div>

            <section v-if="reportKnowledgeRows.length" class="report-block">
              <div class="report-label">知识点掌握度</div>
              <div class="mastery-list">
                <div v-for="row in reportKnowledgeRows" :key="row.name" class="mastery-row">
                  <span>{{ row.name }}</span>
                  <div class="mastery-bar"><i :style="{ width: row.mastery + '%' }" /></div>
                  <strong>{{ row.mastery }}%</strong>
                </div>
              </div>
            </section>

            <section v-if="reportKnowledgeEvidence.length" class="report-block">
              <div class="report-label">课程知识依据</div>
              <p class="muted-copy">以下知识点已关联到课程大纲标准条目，可用于精准复习。</p>
              <div class="knowledge-evidence-list">
                <div v-for="item in reportKnowledgeEvidence" :key="item.raw_name" class="evidence-row">
                  <div class="evidence-header">
                    <span class="evidence-label">{{ item.standard_label || item.raw_name }}</span>
                    <span v-if="item.match_confidence > 0" class="evidence-confidence">{{ Math.round(item.match_confidence * 100) }}% 匹配</span>
                  </div>
                  <div v-if="item.evidence.length" class="evidence-sources">
                    <div v-for="ev in item.evidence" :key="ev.chunk_id" class="evidence-chip">
                      <span class="evidence-source">{{ ev.evidence_label || ev.source_name }}</span>
                      <span v-if="ev.section" class="evidence-section">{{ ev.section }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section v-if="reportLearningPath.length" class="report-block learning-path-block">
              <div class="learning-path-head">
                <div>
                  <div class="report-label">个性化学习路径</div>
                  <p>系统根据答题证据、知识点掌握度和画像策略，规划本节后的连续学习动作。</p>
                </div>
                <span class="path-loop-label">诊断 → 规划 → 生成 → 评估</span>
              </div>
              <div class="learning-path-list">
                <article
                  v-for="(stage, idx) in reportLearningPath"
                  :key="stage.id"
                  class="learning-path-stage"
                  :class="stage.status"
                >
                  <div class="path-node">
                    <span>{{ idx + 1 }}</span>
                  </div>
                  <div class="path-stage-copy">
                    <div class="path-stage-meta">
                      <strong>{{ stage.agent_name }}</strong>
                      <em>{{ learningPathStatusLabel(stage.status) }}</em>
                      <span v-if="stage.metric">{{ stage.metric }}</span>
                    </div>
                    <h4>{{ stage.title }}</h4>
                    <p>{{ stage.description }}</p>
                    <div v-if="stage.knowledge_points.length" class="tag-row">
                      <span v-for="point in stage.knowledge_points" :key="`${stage.id}-${point}`" class="tag task-point">{{ point }}</span>
                    </div>
                  </div>
                  <button
                    v-if="canRunLearningPathStage(stage)"
                    class="task-action path-action"
                    :disabled="isLearningPathStageRunning(stage)"
                    @click="runLearningPathStage(stage)"
                  >
                    {{ learningPathButtonLabel(stage) }}
                  </button>
                </article>
              </div>
            </section>

          </div>
        </div>
      </section>

      <footer v-if="currentScene.type !== 'report'" class="narrator">
        <div class="narrator-card">
          <div class="narrator-body">
            <div class="teacher-mark">
              <div class="teacher-avatar">
                <Volume2 v-if="isAudioPlaying" class="icon avatar-pulse" />
                <VolumeX v-else class="icon" />
              </div>
              <div class="teacher-meta">
                <div class="teacher-name">AI 教师</div>
                <div class="play-status">{{ playbackStatusText }}</div>
              </div>
            </div>
            <div ref="speechTextRef" class="speech-text">
              <template v-if="currentSpeechParagraphs.length">
                <span
                  v-for="(paragraph, idx) in currentSpeechParagraphs"
                  :key="`${idx}-${paragraph.start_ratio}`"
                  :data-speech-segment-index="idx"
                  class="speech-segment"
                  :class="{
                    active: idx === activeSpeechParagraphIdx,
                    inactive: activeSpeechParagraphIdx >= 0 && idx !== activeSpeechParagraphIdx,
                  }"
                >
                  {{ paragraph.text }}
                </span>
              </template>
              <template v-else>{{ currentSpeechText || '当前场景暂无讲解词' }}</template>
            </div>
          </div>

          <template v-if="currentAudioUrl">
            <audio
              ref="audioRef"
              :key="currentAudioUrl"
              :src="currentAudioUrl"
              :autoplay="autoPlayEnabled && currentScene.type !== 'quiz'"
              @ended="handleAudioEnded"
              @play="isAudioPlaying = true"
              @pause="isAudioPlaying = false"
              @loadedmetadata="onAudioLoaded"
              @timeupdate="onAudioTimeUpdate"
              @volumechange="onAudioVolumeChange"
              @ratechange="onAudioRateChange"
            />
            <div class="audio-bar">
              <div class="audio-controls">
                <button
                  type="button"
                  class="audio-tool-btn"
                  :disabled="currentIndex === 0"
                  title="上一页"
                  @click="goPrev"
                >
                  <ChevronLeft class="audio-tool-icon" />
                </button>
                <button
                  type="button"
                  class="audio-tool-btn"
                  :class="{ active: autoPlayEnabled }"
                  :title="autoPlayEnabled ? '关闭自动播放' : '开启自动播放'"
                  @click="toggleAutoPlay"
                >
                  <PauseCircle v-if="autoPlayEnabled" class="audio-tool-icon" />
                  <PlayCircle v-else class="audio-tool-icon" />
                </button>
                <button
                  type="button"
                  class="audio-tool-btn"
                  :disabled="currentIndex >= orderedScenes.length - 1"
                  title="下一页"
                  @click="goNext"
                >
                  <ChevronRight class="audio-tool-icon" />
                </button>

                <span class="audio-time">
                  <em>{{ formatAudioTime(currentAudioTime) }}</em>
                  <i>/</i>
                  <span>{{ formatAudioTime(audioDuration) }}</span>
                </span>

                <div class="audio-volume">
                  <button
                    type="button"
                    class="audio-tool-btn"
                    :title="audioVolume === 0 ? '取消静音' : '静音'"
                    @click="toggleAudioMute"
                  >
                    <VolumeX v-if="audioVolume === 0" class="audio-tool-icon" />
                    <Volume2 v-else class="audio-tool-icon" />
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    :value="audioVolume"
                    class="audio-slider"
                    @input="onAudioVolumeInput"
                  />
                </div>

                <button
                  type="button"
                  class="audio-rate"
                  :title="`倍速 ${audioPlaybackRate}x`"
                  @click="cyclePlaybackRate"
                >
                  {{ audioPlaybackRate }}x
                </button>
              </div>
            </div>
          </template>
        </div>
      </footer>
    </main>

    <DiscussionSidebar
      ref="discussionRef"
      :messages="discussionMessages"
      :submitting="discussionSubmitting"
      :auto-advance-paused="discussionActive"
      :multi-agent-enabled="multiAgentDiscussionEnabled"
      @submit="handleDiscussionSubmit"
      @quick-action="handleDiscussionQuickAction"
      @clear-history="confirmClearDiscussionHistory"
      @update:multi-agent-enabled="multiAgentDiscussionEnabled = $event"
    />
  </div>

  <div v-else-if="isGeneratingPreview" class="player generating-player">
    <aside class="scene-list">
      <button class="back-btn" type="button" title="返回智慧课堂" @click="goBackToList">
        <ArrowLeft class="back-icon" />
        <span>返回智慧课堂</span>
      </button>
      <div class="scene-list-head">
        <div class="scene-list-title">课堂场景</div>
        <div class="scene-list-meta">生成中</div>
      </div>

      <button
        v-for="scene in initialLockedPreviewScenes"
        :key="scene.id"
        class="scene-btn scene-btn-generating locked"
        type="button"
        disabled
      >
        <span class="scene-index locked-index">
          <Lock class="locked-icon" />
        </span>
        <span class="scene-copy">
          <span class="scene-title">{{ scene.title }}</span>
          <span class="scene-type">等待解锁</span>
        </span>
      </button>
    </aside>

    <main class="stage loading-stage">
      <section class="classroom-loading-hero">
        <div class="loading-orbit">
          <Sparkles class="loading-orbit-icon" />
        </div>
        <div class="loading-copy">
          <span>智慧课堂生成中</span>
          <h2>正在准备第一段可播放内容</h2>
          <p>页面和语音会成对解锁，你可以在左侧看到后续课堂节点的生成队列。</p>
        </div>
        <div class="loading-steps">
          <div class="loading-step active">
            <i />
            <span>读取课件结构</span>
          </div>
          <div class="loading-step active">
            <i />
            <span>生成讲解与配音</span>
          </div>
          <div class="loading-step">
            <i />
            <span>解锁第一页</span>
          </div>
        </div>
      </section>
      <section class="stage-skeleton">
        <div class="stage-skeleton-slide">
          <div class="skeleton-line wide" />
          <div class="skeleton-line medium" />
          <div class="skeleton-line short" />
        </div>
        <div class="stage-skeleton-narrator">
          <div class="skeleton-avatar" />
          <div class="skeleton-copy">
            <div class="skeleton-line medium" />
            <div class="skeleton-line wide" />
          </div>
        </div>
      </section>
    </main>

    <aside class="discussion-loading">
      <div class="discussion-loading-title">课堂讨论</div>
      <div class="discussion-loading-card">
        <div class="skeleton-line medium" />
        <div class="skeleton-line wide" />
        <div class="skeleton-line short" />
      </div>
    </aside>
  </div>

  <div v-else class="loading">加载课堂中...</div>
</template>

<script setup lang="ts">
import { sanitizeSvg } from '@/utils/sanitizeSvg'
import { ArrowLeft, CheckCircle, ChevronLeft, ChevronRight, Lock, MessageSquare, Pause, PauseCircle, Play, PlayCircle, Sparkles, Volume2, VolumeX, XCircle } from 'lucide-vue-next'
import DiscussionSidebar from '@/components/classroom/DiscussionSidebar.vue'
import MindmapScene from '@/components/classroom/MindmapScene.vue'
import { useInteractiveClassroomPlayer } from '@/composables/classroom/useInteractiveClassroomPlayer'

const {
  route,
  router,
  dialog,
  message,
  settingStore,
  classroom,
  currentIndex,
  answersByScene,
  quizResultsByScene,
  classroomLoadVersion,
  previewExpectedSceneTotal,
  previewExpectedSlideTotal,
  previewGenerationStage,
  discussionRef,
  submitting,
  runningTaskId,
  reportLoading,
  report,
  nextLessonPlan,
  nextLessonLoading,
  nextLessonDraft,
  reportAutoShown,
  autoPlayEnabled,
  discussionMessages,
  discussionSubmitting,
  multiAgentDiscussionEnabled,
  visitedSceneIds,
  classroomCompletedEmitted,
  isAudioPlaying,
  currentAudioTime,
  audioDuration,
  audioVolume,
  audioPlaybackRate,
  playbackRateOptions,
  speechTextRef,
  svgStageRef,
  svgBoxRef,
  fallbackHighlightTargets,
  measuredHighlightTargets,
  svgMetrics,
  previewAbortCtrl,
  isGeneratingPreview,
  canRecordLearningEvents,
  onAudioLoaded,
  onAudioTimeUpdate,
  onAudioVolumeChange,
  onAudioRateChange,
  syncSpeechParagraphScroll,
  toggleAudioPlay,
  toggleAudioMute,
  onAudioVolumeInput,
  cyclePlaybackRate,
  formatAudioTime,
  audioRef,
  advanceTimer,
  baseScenes,
  reportScene,
  orderedScenes,
  lockedPreviewScenes,
  initialLockedPreviewScenes,
  displaySceneTotal,
  previewTailStatus,
  currentScene,
  playedSceneIds,
  sceneSvg,
  sceneMarkdown,
  sceneMarkmapMd,
  ANIMATION_LAB_EMBED_CSS,
  withAnimationLabEmbedCss,
  animationLabHtml,
  animationLabSummary,
  questions,
  resultByQuestion,
  currentAnswers,
  currentQuizResult,
  allAnswered,
  feedbackText,
  reportKnowledgeRows,
  reportKnowledgeEvidence,
  reportRecommendedTasks,
  reportLearningPath,
  reportTaskById,
  quizSceneIds,
  answeredQuizCount,
  answeredSceneIds,
  isClassroomComplete,
  canOpenReportScene,
  discussionActive,
  lastContentSceneIndex,
  sceneKindLabel,
  playbackStatusText,
  currentSpeechText,
  currentSpeechParagraphs,
  activeSpeechParagraphIdx,
  currentAudioUrl,
  currentSpeechAction,
  rawSceneHighlightTargets,
  sceneHighlightTargets,
  sceneHighlightCues,
  activeHighlight,
  highlightLayerStyle,
  highlightBoxStyle,
  refreshSvgHighlightMetrics,
  setAnswer,
  onShortAnswerInput,
  optionClass,
  isCorrectOption,
  isWrongSelectedOption,
  clearAdvanceTimer,
  shouldAutoAdvance,
  sendQuestionToDiscussion,
  syncDiscussionPersistence,
  migrateDiscussionStorage,
  clearDiscussionHistory,
  confirmClearDiscussionHistory,
  restoreDiscussionForCurrentScene,
  scheduleAutoAdvance,
  selectScene,
  goPrev,
  goNext,
  goBackToList,
  toggleAutoPlay,
  handleAudioEnded,
  requestDiscussion,
  handleDiscussionSubmit,
  handleDiscussionQuickAction,
  resetQuiz,
  applyFeedbackAction,
  submitQuiz,
  loadReport,
  loadNextLessonPlan,
  splitDraftPoints,
  openNextLessonInPptStudio,
  showReport,
  showReportAfterClassroomEnd,
  loadClassroom,
  stopGeneratingPreview,
  buildPreviewClassroom,
  upsertPreviewScene,
  loadGeneratingClassroom,
  settleGeneratingPreview,
  formatSceneTitle,
  sceneTypeLabel,
  taskPriorityLabel,
  learningPathStatusLabel,
  learningPathActionTask,
  canRunLearningPathStage,
  learningPathButtonLabel,
  isLearningPathStageRunning,
  runLearningPathStage,
  getTaskAction,
  canRunTask,
  taskButtonLabel,
  runTask,
} = useInteractiveClassroomPlayer()
</script>

<style scoped src="../assets/styles/interactive-classroom-player.css"></style>
