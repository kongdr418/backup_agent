<template>
  <div class="study-tools-page h-full flex flex-col">
    <PageHeader title="学习工具" description="错题本 + 闪卡复习 · 越用越懂你">
      <template #actions>
        <n-button quaternary size="small" @click="refreshAll">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          刷新
        </n-button>
      </template>
    </PageHeader>

    <div class="study-tools-scroll flex-1 overflow-y-auto">
      <div class="study-shell">
        <main class="study-main">
        <!-- 顶部两个统计入口卡 -->
        <div class="study-stats-grid">
          <button
            class="stat-tile text-left"
            @click="activeTab = 'mistakes'"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="stat-tile-icon stat-tile-icon-mistakes">
                <BookMarked class="w-4 h-4" />
              </div>
              <span class="text-[11px] text-ink-3">{{ mistakeProgressText }}</span>
            </div>
            <div class="text-[22px] font-semibold text-ink-1 leading-none">
              {{ stats?.mistakes.unmastered ?? '—' }}
            </div>
            <div class="text-[12px] text-ink-3 mt-1.5">未掌握错题 / 共 {{ stats?.mistakes.total ?? 0 }} 条</div>
          </button>
          <button
            class="stat-tile text-left"
            @click="activeTab = 'flashcards'"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="stat-tile-icon stat-tile-icon-flashcards">
                <Layers class="w-4 h-4" />
              </div>
              <span class="text-[11px] text-ink-3">连续 {{ stats?.flashcards.streak_days ?? 0 }} 天</span>
            </div>
            <div class="text-[22px] font-semibold text-ink-1 leading-none">
              {{ stats?.flashcards.due_today ?? '—' }}
            </div>
            <div class="text-[12px] text-ink-3 mt-1.5">今日待复习 / 共 {{ stats?.flashcards.total ?? 0 }} 张</div>
          </button>
        </div>

        <!-- Tab 切换 -->
        <div class="study-tab-bar">
          <button
            class="study-tab-btn"
            :class="activeTab === 'mistakes' ? 'study-tab-btn-active' : ''"
            type="button"
            @click="activeTab = 'mistakes'"
          >
            <BookMarked class="w-3.5 h-3.5" />
            错题本
          </button>
          <button
            class="study-tab-btn"
            :class="activeTab === 'flashcards' ? 'study-tab-btn-active' : ''"
            type="button"
            @click="activeTab = 'flashcards'"
          >
            <Layers class="w-3.5 h-3.5" />
            闪卡复习
          </button>
          <button
            class="study-tab-btn"
            :class="activeTab === 'labs' ? 'study-tab-btn-active' : ''"
            type="button"
            @click="activeTab = 'labs'"
          >
            <Code2 class="w-3.5 h-3.5" />
            实操实验
          </button>
        </div>

        <!-- 主体 Tab -->
        <div class="study-panel">
          <n-tabs
            v-model:value="activeTab"
            type="line"
            animated
            :bar-width="20"
            class="study-tabs"
          >
            <!-- ───────── 错题本 ───────── -->
            <n-tab-pane name="mistakes" tab="错题本">
              <div class="pt-2">
                <!-- 批量操作工具条(选中错题后显示) -->
                <transition name="batch-bar">
                  <div v-if="selectedMistakeIds.size > 0" class="batch-bar mb-3">
                    <div class="flex items-center gap-2 text-[12.5px] text-ink-1">
                      <CheckSquare class="w-3.5 h-3.5 text-hue-study" />
                      <span>已选 <strong>{{ selectedMistakeIds.size }}</strong> 道</span>
                      <n-button size="tiny" quaternary @click="clearSelection">清空选择</n-button>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <n-popselect
                        v-model:value="batchAddToCollectionId"
                        :options="collectionOptionsForBatch"
                        placeholder="选择错题集"
                        size="small"
                        :disabled="store.collections.length === 0"
                        @update:value="onBatchAddToCollection"
                      >
                        <n-button size="small" type="primary" :disabled="store.collections.length === 0">
                          <FolderPlus class="w-3.5 h-3.5 mr-1" />
                          加入错题集
                        </n-button>
                      </n-popselect>
                      <n-button size="small" quaternary @click="onBatchDeleteSelected">
                        <Trash2 class="w-3.5 h-3.5 mr-1" />
                        删除
                      </n-button>
                    </div>
                  </div>
                </transition>

                <div class="study-toolbar mb-4">
                  <div class="study-toolbar-left">
                    <n-button
                      size="small"
                      type="primary"
                      :disabled="unmasteredMistakes.length === 0"
                      @click="startBatchRedo"
                    >
                      <Play class="w-3.5 h-3.5 mr-1" />
                      开始重做
                      <span v-if="unmasteredMistakes.length" class="ml-1.5 text-[11px] opacity-80">
                        ({{ unmasteredMistakes.length }})
                      </span>
                    </n-button>
                    <!-- 筛选标签 + 下拉 -->
                    <div class="study-toolbar-chips">
                      <span class="toolbar-chip toolbar-chip-active">
                        全部
                        <span class="toolbar-chip-badge">{{ store.mistakesTotal || store.mistakes.length }}</span>
                      </span>
                      <n-select
                        v-model:value="mistakeFilter.mastered"
                        :options="masteredOptions"
                        size="small"
                        style="width: 90px"
                        @update:value="onMistakeFilterChange"
                      />
                    </div>
                    <n-input
                      v-model:value="mistakeFilter.q"
                      size="small"
                      placeholder="搜索题干 / 知识点..."
                      clearable
                      style="width: 220px"
                      @keyup.enter="onMistakeFilterChange"
                    >
                      <template #prefix>
                        <Search class="w-3.5 h-3.5 text-ink-3" />
                      </template>
                    </n-input>
                  </div>
                  <div class="study-toolbar-right">
                    <n-button class="study-secondary-button" size="small" @click="mistakeAddShow = true">
                      <Plus class="w-3.5 h-3.5 mr-1" />
                      新建错题
                    </n-button>
                    <n-button class="study-secondary-button" size="small" @click="openManageCollections">
                      <Settings class="w-3.5 h-3.5 mr-1" />
                      批量管理
                    </n-button>
                  </div>
                </div>

                <div v-if="store.mistakesLoading" class="text-center text-[12px] text-ink-3 py-8">加载中...</div>
                <EmptyState
                  v-else-if="store.mistakes.length === 0"
                  :icon="BookMarked"
                  :title="activeCollectionId ? '该错题集下还没有错题' : '还没有错题'"
                  :description="activeCollectionId ? '勾选其他错题后用顶部「加入错题集」工具添加' : '手动添加或去互动课堂答错自动同步'"
                >
                  <n-button size="small" type="primary" @click="mistakeAddShow = true">添加第一道错题</n-button>
                </EmptyState>
                <div v-else class="study-list">
                  <div
                    v-for="m in store.mistakes"
                    :key="m.id"
                    class="mistake-card"
                    :class="[m.mastered ? 'mistake-card-mastered' : '', redoingIds.has(m.id) ? 'mistake-card-redoing' : '', selectedMistakeIds.has(m.id) ? 'mistake-card-selected' : '']"
                  >
                    <!-- 卡片头部：标签行 -->
                    <div class="mistake-card-head">
                      <div class="mistake-card-title-row">
                        <n-checkbox
                          :checked="selectedMistakeIds.has(m.id)"
                          size="small"
                          @update:checked="(v: boolean) => toggleSelect(m.id, v)"
                        />
                        <span class="study-chip study-chip-source">
                          {{ formatMistakeSourceLabel(m.source) }}
                        </span>
                        <span v-if="m.knowledge_point_name" class="study-chip study-chip-info">
                          {{ m.knowledge_point_name }}
                        </span>
                        <span v-if="m.course_name" class="study-chip">
                          {{ m.course_name }}
                        </span>
                        <span
                          v-for="cid in (m.collection_ids || []).slice(0, 2)"
                          :key="cid"
                          class="study-chip study-chip-collection"
                        >
                          <Tag class="w-2.5 h-2.5" />
                          {{ collectionNameById(cid) }}
                        </span>
                      </div>
                      <div class="mistake-card-right">
                        <span class="mistake-date">{{ formatDate(m.first_added_at) }}</span>
                        <div class="mistake-menu-wrap">
                          <button
                            class="mistake-menu-btn"
                            type="button"
                            :data-menu-anchor="m.id"
                            @click.stop="toggleMistakeMenu(m.id, $event)"
                          >
                            <MoreHorizontal class="w-4 h-4" />
                          </button>
                          <teleport to="body">
                            <div
                              v-if="mistakeMenuId === m.id"
                              class="mistake-menu-overlay"
                              @click="mistakeMenuId = null"
                            />
                            <div
                              v-if="mistakeMenuId === m.id"
                              class="mistake-menu-dropdown"
                              :style="mistakeMenuStyle"
                            >
                              <button class="mistake-menu-item" @click="onPeek(m); mistakeMenuId = null">
                                <Eye class="w-3.5 h-3.5" />
                                查看答案
                              </button>
                              <button class="mistake-menu-item" @click="openRedo(m); mistakeMenuId = null">
                                <PenLine class="w-3.5 h-3.5" />
                                重新作答
                              </button>
                              <button class="mistake-menu-item" @click="onConvertToCard(m); mistakeMenuId = null">
                                <Layers class="w-3.5 h-3.5" />
                                转闪卡
                              </button>
                              <div class="mistake-menu-divider" />
                              <button class="mistake-menu-item mistake-menu-item-danger" @click="askDelete(m); mistakeMenuId = null">
                                <Trash2 class="w-3.5 h-3.5" />
                                删除
                              </button>
                            </div>
                          </teleport>
                        </div>
                      </div>
                    </div>

                    <!-- 题干 -->
                    <div class="mistake-stem">
                      {{ m.stem }}
                    </div>

                    <!-- 图片附件 -->
                    <NImageGroup
                      v-if="m.attachments && m.attachments.length"
                    >
                      <div class="attachment-strip mb-2">
                        <NImage
                          v-for="a in m.attachments"
                          :key="a.id"
                          :src="a.url"
                          :alt="a.name"
                          width="64"
                          height="64"
                          object-fit="cover"
                          class="attachment-thumb"
                          show-toolbar
                        />
                      </div>
                    </NImageGroup>

                    <!-- 已掌握：直接展示答案 -->
                    <div v-if="m.mastered" class="mistake-meta-list">
                      <div v-if="m.correct_answer" class="mistake-meta">
                        <span class="text-ink-3">正确答案</span>
                        <span class="text-ink-1">{{ m.correct_answer }}</span>
                      </div>
                      <div v-if="m.user_answer" class="mistake-meta">
                        <span class="text-ink-3">原错答</span>
                        <span class="text-danger">{{ m.user_answer }}</span>
                      </div>
                      <div v-if="m.analysis" class="mistake-meta">
                        <span class="text-ink-3">解析</span>
                        <span class="text-ink-2">{{ m.analysis }}</span>
                      </div>
                    </div>

                    <!-- 重做输入区 -->
                    <div v-else-if="redoingIds.has(m.id)" class="redo-panel">
                      <div v-if="!redoRevealed[m.id]" class="space-y-2">
                        <template v-if="m.question_type === 'single' && m.options?.length">
                          <div class="choice-hint">选择一个选项</div>
                          <div class="study-choice-list">
                            <button
                              v-for="(label, idx) in m.options"
                              :key="idx"
                              type="button"
                              class="study-choice"
                              :class="redoChoiceClass(m, label, idx)"
                              @click="onSelectRedoChoice(m, label, idx)"
                            >
                              <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
                              <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
                              <Check
                                v-if="selectedRedoLetters(m).includes(getChoiceLetter(label, idx))"
                                class="study-choice-icon selected"
                              />
                            </button>
                          </div>
                        </template>
                        <template v-else-if="m.question_type === 'multiple' && m.options?.length">
                          <div class="choice-hint">可多选</div>
                          <div class="study-choice-list">
                            <button
                              v-for="(label, idx) in m.options"
                              :key="idx"
                              type="button"
                              class="study-choice"
                              :class="redoChoiceClass(m, label, idx)"
                              @click="onSelectRedoChoice(m, label, idx)"
                            >
                              <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
                              <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
                              <Check
                                v-if="selectedRedoLetters(m).includes(getChoiceLetter(label, idx))"
                                class="study-choice-icon selected"
                              />
                            </button>
                          </div>
                        </template>
                        <template v-else>
                          <div class="text-[11.5px] text-ink-3">写下你的答案,再查看正确答案</div>
                          <n-input
                            v-model:value="redoAnswer[m.id]"
                            type="textarea"
                            placeholder="试着回忆一下答案..."
                            :autosize="{ minRows: 2, maxRows: 5 }"
                            size="small"
                          />
                        </template>
                        <div class="flex items-center gap-2">
                          <n-button
                            type="primary"
                            size="small"
                            :disabled="!hasRedoAnswer(m)"
                            @click="onSubmitRedo(m)"
                          >
                            <Send class="w-3 h-3 mr-1" />
                            提交并查看
                          </n-button>
                          <n-button size="small" quaternary @click="onRevealRedo(m)">
                            <Eye class="w-3 h-3 mr-1" />
                            直接查看答案
                          </n-button>
                          <n-button size="small" quaternary class="ml-auto" @click="closeRedo(m)">
                            收起
                          </n-button>
                        </div>
                      </div>
                      <div v-else class="redo-result-layout">
                        <div class="redo-result-main">
                          <div v-if="m.options?.length" class="study-choice-list">
                            <button
                              v-for="(label, idx) in m.options"
                              :key="idx"
                              type="button"
                              class="study-choice is-submitted"
                              :class="redoChoiceClass(m, label, idx, true)"
                              disabled
                            >
                              <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
                              <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
                              <Check v-if="isCorrectChoice(m.correct_answer, label, idx)" class="study-choice-icon correct" />
                              <XIcon v-if="isRedoChoiceWrong(m, label, idx)" class="study-choice-icon wrong" />
                            </button>
                          </div>
                          <div class="redo-explain-card">
                            <div v-if="hasRedoAnswer(m)" class="mistake-meta">
                              <span class="text-ink-3">你的答案</span>
                              <span :class="isRedoCorrect(m) ? 'text-success' : 'text-danger'">
                                {{ formatRedoAnswer(m) }}
                              </span>
                              <span v-if="isRedoCorrect(m)" class="text-success text-[11px]">✓ 答对</span>
                              <span v-else class="text-warning text-[11px]">✕ 需要巩固</span>
                            </div>
                            <div v-if="m.correct_answer" class="mistake-meta">
                              <span class="text-ink-3">正确答案</span>
                              <span class="text-ink-1">{{ m.correct_answer }}</span>
                            </div>
                            <div v-if="m.user_answer" class="mistake-meta">
                              <span class="text-ink-3">原错答</span>
                              <span class="text-danger">{{ m.user_answer }}</span>
                            </div>
                            <div v-if="m.analysis" class="mistake-meta">
                              <span class="text-ink-3">解析</span>
                              <span class="text-ink-2">{{ m.analysis }}</span>
                            </div>
                            <button v-if="!isRedoCorrect(m)" type="button" class="redo-convert-link" @click="onConvertToCard(m)">
                              <Layers class="w-3.5 h-3.5" />
                              转闪卡反复练
                            </button>
                          </div>
                          <div class="flex items-center gap-2 pt-1">
                            <n-button
                              v-if="isRedoCorrect(m) && !m.mastered"
                              type="primary"
                              size="small"
                              @click="onMarkMastered(m)"
                            >
                              <Check class="w-3 h-3 mr-1" />
                              标记掌握
                            </n-button>
                            <n-button size="small" quaternary class="ml-auto" @click="closeRedo(m)">
                              关闭
                            </n-button>
                          </div>
                        </div>
                        <aside class="redo-knowledge-card">
                          <div class="redo-knowledge-title">
                            <BookMarked class="w-3.5 h-3.5" />
                            知识点
                          </div>
                          <div>{{ m.knowledge_point_name || m.course_name || '本题关键概念' }}</div>
                        </aside>
                      </div>
                    </div>

                    <!-- 默认：隐藏答案 -->
                    <div v-else class="reveal-hint">
                      <span class="text-[11.5px] text-ink-3">
                        答案已隐藏 · 先试着回忆, 再查看解析
                      </span>
                      <n-button size="tiny" quaternary type="primary" @click="openRedo(m)">
                        <PenLine class="w-3 h-3 mr-1" />
                        重新作答
                      </n-button>
                      <n-button size="tiny" quaternary @click="onPeek(m)">
                        <Eye class="w-3 h-3 mr-1" />
                        查看答案
                      </n-button>
                    </div>

                    <!-- 标签 -->
                    <div v-if="safeMistakeTags(m.tags).length" class="mistake-tags">
                      <span
                        v-for="t in safeMistakeTags(m.tags)"
                        :key="t"
                        class="study-tag"
                      >
                        {{ formatMistakeTagLabel(t) }}
                      </span>
                    </div>

                    <!-- 来源标签 + 操作 -->
                    <div class="mistake-source-row">
                      <span class="text-[11px] text-ink-3 source-tag-inline">
                        {{ formatMistakeSourceLabel(m.source) }}
                      </span>
                    </div>

                    <div class="mistake-action-bar">
                      <n-button
                        v-if="!m.mastered"
                        size="tiny"
                        type="primary"
                        ghost
                        @click="onMarkMastered(m)"
                      >
                        <Check class="w-3 h-3 mr-1" />
                        标记掌握
                      </n-button>
                      <n-button
                        v-else
                        size="tiny"
                        quaternary
                        type="success"
                        @click="onUnmarkMastered(m)"
                      >
                        <CheckCheck class="w-3 h-3 mr-1" />
                        已掌握
                      </n-button>
                      <n-button size="tiny" quaternary @click="onConvertToCard(m)">
                        <Layers class="w-3 h-3 mr-1" />
                        转闪卡
                      </n-button>
                      <n-popover
                        trigger="click"
                        placement="bottom-end"
                        :show-arrow="false"
                        style="padding: 8px 0; min-width: 260px"
                      >
                        <template #trigger>
                          <n-button size="tiny" quaternary>
                            <Paperclip class="w-3 h-3 mr-1" />
                            附件
                            <span
                              v-if="(m.attachments || []).length"
                              class="ml-1 text-[10px] opacity-70"
                            >
                              ({{ (m.attachments || []).length }})
                            </span>
                          </n-button>
                        </template>
                        <div class="px-3 pb-2 pt-1 text-[11px] text-ink-3 border-b border-line-subtle flex items-center justify-between">
                          <span>图片附件(共 {{ (m.attachments || []).length }} 张)</span>
                          <span class="text-[10.5px] text-ink-4">最多 9 张</span>
                        </div>
                        <div class="max-h-56 overflow-y-auto py-1">
                          <div
                            v-if="!(m.attachments || []).length"
                            class="px-3 py-3 text-[12px] text-ink-3"
                          >
                            暂无附件
                          </div>
                          <div
                            v-for="a in m.attachments || []"
                            :key="a.id"
                            class="attachment-popover-row"
                          >
                            <img :src="a.url" :alt="a.name" class="attachment-popover-thumb" />
                            <div class="flex-1 min-w-0">
                              <div class="text-[12px] text-ink-1 truncate">{{ a.name }}</div>
                              <div class="text-[10.5px] text-ink-3">{{ formatSize(a.size) }}</div>
                            </div>
                            <n-button
                              size="tiny"
                              quaternary
                              type="error"
                              :loading="removingAttId === a.id"
                              @click="onRemoveAttachment(m, a.id)"
                            >
                              <Trash2 class="w-3 h-3" />
                            </n-button>
                          </div>
                        </div>
                        <div class="px-3 pt-2 border-t border-line-subtle">
                          <label class="attachment-add-row">
                            <Paperclip class="w-3 h-3" />
                            <span class="text-[12px]">{{ addingFor === m.id ? '上传中…' : '追加图片' }}</span>
                            <input
                              type="file"
                              accept="image/png,image/jpeg,image/gif,image/webp,image/bmp"
                              multiple
                              class="hidden"
                              :disabled="addingFor === m.id || (m.attachments || []).length >= 9"
                              @change="onPickAttachments(m, $event)"
                            />
                          </label>
                        </div>
                      </n-popover>
                      <n-popover
                        trigger="click"
                        placement="bottom-end"
                        :show-arrow="false"
                        style="padding: 8px 0; min-width: 220px"
                      >
                        <template #trigger>
                          <n-button size="tiny" quaternary>
                            <Tag class="w-3 h-3 mr-1" />
                            加入错题集
                            <span v-if="(m.collection_ids || []).length" class="ml-1 text-[10px] opacity-70">
                              ({{ (m.collection_ids || []).length }})
                            </span>
                          </n-button>
                        </template>
                        <div class="px-3 pb-2 pt-1 text-[11px] text-ink-3 border-b border-line-subtle">
                          选择错题集(可多选)
                        </div>
                        <div class="max-h-64 overflow-y-auto py-1">
                          <div
                            v-if="store.collections.length === 0"
                            class="px-3 py-3 text-[12px] text-ink-3"
                          >
                            还没有错题集,先在顶部创建一个
                          </div>
                          <label
                            v-for="c in store.collections"
                            :key="c.id"
                            class="collection-popover-row"
                          >
                            <n-checkbox
                              :checked="(m.collection_ids || []).includes(c.id)"
                              @update:checked="(v: boolean) => onToggleMistakeInCollection(m, c.id, v)"
                            />
                            <span class="flex-1 truncate">{{ c.name }}</span>
                            <span class="text-[10px] text-ink-4">{{ c.count }}</span>
                          </label>
                        </div>
                        <div class="px-3 pt-2 border-t border-line-subtle">
                          <n-button size="tiny" block quaternary @click="openCreateCollection">
                            <Plus class="w-3 h-3 mr-0.5" />
                            新建错题集
                          </n-button>
                        </div>
                      </n-popover>
                      <n-button size="tiny" quaternary type="error" class="ml-auto" @click="askDelete(m)">
                        <Trash2 class="w-3 h-3" />
                      </n-button>
                    </div>
                  </div>
                </div>
              </div>
            </n-tab-pane>

            <!-- ───────── 闪卡 ───────── -->
            <n-tab-pane name="flashcards" tab="闪卡复习">
              <div class="pt-2">
                <div class="study-toolbar mb-4">
                  <div class="study-toolbar-left">
                    <n-button
                      size="small"
                      type="primary"
                      :disabled="(store.flashcards?.length ?? 0) === 0"
                      @click="startReview"
                    >
                      <Play class="w-3.5 h-3.5 mr-1" />
                      今日复习
                      <span v-if="store.dueCards?.length" class="ml-1.5 text-[11px] opacity-80">
                        ({{ store.dueCards.length }})
                      </span>
                    </n-button>
                    <n-button
                      size="small"
                      :disabled="store.flashcards.length === 0"
                      @click="startReviewAll"
                    >
                      <RotateCw class="w-3.5 h-3.5 mr-1" />
                      复习全部
                      <span v-if="store.flashcards.length" class="ml-1.5 text-[11px] opacity-80">
                        ({{ store.flashcards.length }})
                      </span>
                    </n-button>
                    <n-input
                      v-model:value="cardFilter.q"
                      size="small"
                      placeholder="搜索卡片内容..."
                      clearable
                      style="width: 220px"
                      @keyup.enter="onCardFilterChange"
                    >
                      <template #prefix>
                        <Search class="w-3.5 h-3.5 text-ink-3" />
                      </template>
                    </n-input>
                  </div>
                  <n-button class="study-secondary-button" size="small" @click="cardAddShow = true">
                    <Plus class="w-3.5 h-3.5 mr-1" />
                    新建闪卡
                  </n-button>
                </div>

                <div v-if="store.flashcardsLoading" class="text-center text-[12px] text-ink-3 py-8">加载中...</div>
                <EmptyState
                  v-else-if="store.flashcards.length === 0"
                  :icon="Layers"
                  title="还没有闪卡"
                  description="手动新建、从错题转、或用 AI 一键生成"
                >
                  <n-button size="small" type="primary" @click="cardAddShow = true">新建第一张</n-button>
                </EmptyState>
                <div v-else class="study-list">
                  <div
                    v-for="c in store.flashcards"
                    :key="c.id"
                    class="card-row"
                  >
                    <div class="card-row-head">
                      <span v-if="c.knowledge_point_name" class="study-chip study-chip-info">
                        {{ c.knowledge_point_name }}
                      </span>
                      <span v-if="c.course_name" class="study-chip">
                        {{ c.course_name }}
                      </span>
                      <span class="study-chip study-chip-source-mistake" v-if="sourceLabel(c.source) === '错题'">
                        {{ sourceLabel(c.source) }}
                      </span>
                      <span class="text-[11px] text-ink-3 ml-auto">
                        {{ formatDate(c.created_at) }}
                      </span>
                      <div class="card-menu-wrap">
                        <button
                          class="mistake-menu-btn"
                          type="button"
                          :data-menu-anchor="'card-' + c.id"
                          @click.stop="toggleCardMenu(c.id, $event)"
                        >
                          <MoreHorizontal class="w-4 h-4" />
                        </button>
                        <teleport to="body">
                          <div
                            v-if="cardMenuId === c.id"
                            class="mistake-menu-overlay"
                            @click="cardMenuId = null"
                          />
                          <div
                            v-if="cardMenuId === c.id"
                            class="mistake-menu-dropdown"
                            :style="cardMenuStyle"
                          >
                            <button class="mistake-menu-item" @click="startReviewOne(c); cardMenuId = null">
                              <Play class="w-3.5 h-3.5" />
                              重学
                            </button>
                            <div class="mistake-menu-divider" />
                            <button class="mistake-menu-item mistake-menu-item-danger" @click="askDeleteCard(c); cardMenuId = null">
                              <Trash2 class="w-3.5 h-3.5" />
                              删除
                            </button>
                          </div>
                        </teleport>
                      </div>
                    </div>
                    <div class="card-row-front">
                      {{ c.front }}
                    </div>
                    <div class="card-row-back">
                      {{ c.back }}
                    </div>
                    <div class="card-row-footer">
                      <div class="card-row-meta">
                        <span>
                          <Calendar class="w-3 h-3 inline -mt-0.5 mr-0.5" />
                          {{ c.sm2?.due_date || '—' }}
                        </span>
                        <span>EF {{ (c.sm2?.ease_factor ?? 2.5).toFixed(2) }}</span>
                        <span>重复 {{ c.sm2?.repetitions ?? 0 }} 次</span>
                      </div>
                      <div class="card-row-actions">
                        <n-button size="tiny" quaternary type="primary" @click="startReviewOne(c)">
                          <Play class="w-3 h-3 mr-0.5" />
                          重学
                        </n-button>
                        <n-button size="tiny" quaternary type="error" @click="askDeleteCard(c)">
                          <Trash2 class="w-3 h-3" />
                        </n-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </n-tab-pane>

            <n-tab-pane name="labs" tab="实操实验">
              <div class="practice-lab-layout pt-2">
                <section class="practice-lab-builder">
                  <div class="practice-lab-section-head">
                    <div>
                      <div class="practice-lab-title">生成实操资产</div>
                      <div class="practice-lab-subtitle">动画演示 / 视频分镜 / 代码练习</div>
                    </div>
                    <n-tag size="small" :bordered="false" type="success">课堂可嵌入</n-tag>
                  </div>

                  <div class="practice-type-switch">
                    <button
                      type="button"
                      class="practice-type-btn"
                      :class="labForm.type === 'animation' ? 'practice-type-btn-active' : ''"
                      @click="labForm.type = 'animation'"
                    >
                      <Film class="w-3.5 h-3.5" />
                      动画演示
                    </button>
                    <button
                      type="button"
                      class="practice-type-btn"
                      :class="labForm.type === 'code' ? 'practice-type-btn-active' : ''"
                      @click="labForm.type = 'code'"
                    >
                      <Code2 class="w-3.5 h-3.5" />
                      代码实操
                    </button>
                  </div>

                  <n-input v-model:value="labForm.topic" size="small" placeholder="主题，例如：梯度下降可视化 / 二分查找" />
                  <n-input v-model:value="labForm.course" size="small" placeholder="课程名称，例如：人工智能导论" />
                  <n-input v-model:value="labForm.knowledgePointsText" size="small" placeholder="知识点，用顿号或逗号分隔" />
                  <n-input
                    v-if="labForm.type === 'code'"
                    v-model:value="labForm.starterCode"
                    type="textarea"
                    :autosize="{ minRows: 6, maxRows: 10 }"
                    placeholder="可选：function solve(input) { return Number(input) * Number(input) }"
                  />

                  <n-button
                    type="primary"
                    size="small"
                    :loading="labsLoading"
                    :disabled="!labForm.topic.trim()"
                    @click="onGenerateLab"
                  >
                    <Play class="w-3.5 h-3.5 mr-1" />
                    生成实验
                  </n-button>
                </section>

                <section class="practice-lab-list-panel">
                  <div class="practice-lab-section-head">
                    <div>
                      <div class="practice-lab-title">实验资产</div>
                      <div class="practice-lab-subtitle">共 {{ labsTotal }} 个</div>
                    </div>
                    <n-button quaternary size="tiny" @click="fetchLabs">
                      <RefreshCw class="w-3.5 h-3.5" />
                    </n-button>
                  </div>

                  <div v-if="labsLoading && labs.length === 0" class="text-center text-[12px] text-ink-3 py-8">加载中...</div>
                  <EmptyState
                    v-else-if="labs.length === 0"
                    :icon="Code2"
                    title="还没有实操实验"
                    description="生成一个动画演示或代码练习，用来补齐多模态与动手学习场景"
                  />
                  <div v-else class="practice-lab-list">
                    <button
                      v-for="lab in labs"
                      :key="lab.id"
                      type="button"
                      class="practice-lab-card"
                      :class="selectedLabId === lab.id ? 'practice-lab-card-active' : ''"
                      @click="selectedLabId = lab.id"
                    >
                      <div class="practice-lab-card-main">
                        <span class="practice-lab-kind">
                          <component :is="lab.type === 'code' ? Code2 : Film" class="w-3 h-3" />
                          {{ lab.type === 'code' ? '代码实操' : '动画演示' }}
                          · {{ lab.content.generation_mode === 'llm' ? 'LLM 生成' : '模板回退' }}
                        </span>
                        <strong>{{ lab.title }}</strong>
                        <span>{{ lab.summary }}</span>
                      </div>
                      <n-button size="tiny" quaternary type="error" @click.stop="onDeleteLab(lab.id)">
                        <Trash2 class="w-3 h-3" />
                      </n-button>
                    </button>
                  </div>
                </section>
              </div>

              <section v-if="selectedLab" class="practice-lab-preview">
                <div class="practice-lab-preview-head">
                  <div>
                    <div class="practice-lab-title">{{ selectedLab.title }}</div>
                    <div class="practice-lab-subtitle">{{ selectedLab.course || '通用课程' }} · {{ selectedLab.topic }}</div>
                  </div>
                  <div class="flex items-center gap-2">
                    <n-tag size="small" :bordered="false" :type="selectedLab.content.generation_mode === 'llm' ? 'success' : 'warning'">
                      {{ selectedLab.content.generation_mode === 'llm' ? 'LLM 生成' : '模板回退' }}
                    </n-tag>
                    <n-tag
                      v-for="point in selectedLab.knowledge_points.slice(0, 3)"
                      :key="point"
                      size="small"
                      :bordered="false"
                    >
                      {{ point }}
                    </n-tag>
                  </div>
                </div>

                <div v-if="selectedLab.type === 'animation'" class="video-prompt-box">
                  <MonitorPlay class="w-4 h-4 text-hue-study" />
                  <div>
                    <div class="text-[12px] font-medium text-ink-1 mb-1">视频生成提示词</div>
                    <div class="text-[12px] text-ink-2 leading-relaxed">{{ selectedLab.content.video_prompt }}</div>
                  </div>
                </div>

                <iframe
                  :key="`${selectedLab.id}-${selectedLab.updated_at}`"
                  class="practice-lab-frame"
                  sandbox="allow-scripts"
                  :srcdoc="selectedLab.content.html || ''"
                />
              </section>
            </n-tab-pane>
          </n-tabs>
        </div>
        </main>
      </div>
    </div>

    <!-- 添加错题 -->
    <AddMistakeModal v-model:show="mistakeAddShow" @submit="onAddMistake" />

    <!-- 添加闪卡 -->
    <AddFlashcardModal v-model:show="cardAddShow" @submit="onAddCard" />

    <!-- 复习会话(全屏) -->
    <n-modal
      :show="reviewing"
      preset="card"
      style="width: 640px; max-width: 92vw"
      :mask-closable="false"
      :closable="false"
      :close-on-esc="false"
      :bordered="false"
      title="今日复习"
      @update:show="(v: boolean) => { if (!v) closeReview() }"
    >
      <div v-if="reviewIndex >= 0 && reviewIndex < reviewQueue.length" class="space-y-4">
        <div class="text-[11px] text-ink-3 text-right">
          {{ reviewIndex + 1 }} / {{ reviewQueue.length }}
        </div>

        <div class="flash-stage" @click="onFlip">
          <div class="flash-card" :class="{ 'flash-card-flipped': reviewFlipped }">
            <div class="flash-face flash-face-front">
              <div class="text-[11px] text-ink-3 mb-2">正面</div>
              <div class="text-[15px] text-ink-1 leading-relaxed whitespace-pre-wrap">
                {{ reviewQueue[reviewIndex].front }}
              </div>
            </div>
            <div class="flash-face flash-face-back">
              <div class="text-[11px] text-ink-3 mb-2">背面</div>
              <div class="text-[14px] text-ink-1 leading-relaxed whitespace-pre-wrap">
                {{ reviewQueue[reviewIndex].back }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="!reviewFlipped" class="text-center">
          <n-button type="primary" size="medium" @click="onFlip">显示答案</n-button>
        </div>
        <div v-else class="grid grid-cols-4 gap-2">
          <n-button size="medium" @click="onGrade(0)" class="grade-btn grade-btn-0">
            <span class="text-[11px] opacity-70">0</span>
            <span class="ml-1">重来</span>
          </n-button>
          <n-button size="medium" @click="onGrade(1)" class="grade-btn grade-btn-1">
            <span class="text-[11px] opacity-70">1</span>
            <span class="ml-1">困难</span>
          </n-button>
          <n-button size="medium" @click="onGrade(3)" class="grade-btn grade-btn-3">
            <span class="text-[11px] opacity-70">3</span>
            <span class="ml-1">良好</span>
          </n-button>
          <n-button size="medium" @click="onGrade(5)" class="grade-btn grade-btn-5">
            <span class="text-[11px] opacity-70">5</span>
            <span class="ml-1">容易</span>
          </n-button>
        </div>
      </div>
      <div v-else class="text-center py-8">
        <div class="text-[15px] text-ink-1 font-medium mb-2">今日复习完成 🎉</div>
        <div class="text-[12px] text-ink-3 mb-5">已复习 {{ reviewDoneCount }} 张</div>
        <n-button type="primary" @click="closeReview">完成</n-button>
      </div>
    </n-modal>

    <!-- 错题集中重做会话(全屏) -->
    <n-modal
      :show="batchRedoing"
      preset="card"
      style="width: 720px; max-width: 92vw"
      :mask-closable="false"
      :closable="false"
      :close-on-esc="false"
      :bordered="false"
      title="错题重做"
      @update:show="(v: boolean) => { if (!v) closeBatchRedo() }"
    >
      <div v-if="batchIndex >= 0 && batchIndex < batchQueue.length" class="space-y-4">
        <div class="flex items-center justify-between text-[11px] text-ink-3">
          <div class="flex items-center gap-1.5">
            <n-tag v-if="batchQueue[batchIndex].knowledge_point_name" size="tiny" :bordered="false" type="info">
              {{ batchQueue[batchIndex].knowledge_point_name }}
            </n-tag>
            <n-tag v-if="batchQueue[batchIndex].course_name" size="tiny" :bordered="false">
              {{ batchQueue[batchIndex].course_name }}
            </n-tag>
          </div>
          <span>{{ batchIndex + 1 }} / {{ batchQueue.length }}</span>
        </div>

        <div class="batch-stem">
          {{ batchQueue[batchIndex].stem }}
        </div>

        <div v-if="!batchRevealed" class="space-y-2">
          <template v-if="batchQueue[batchIndex].question_type === 'single' && batchQueue[batchIndex].options?.length">
            <div class="choice-hint">选择一个选项</div>
            <div class="study-choice-list">
              <button
                v-for="(label, idx) in batchQueue[batchIndex].options"
                :key="idx"
                type="button"
                class="study-choice"
                :class="batchChoiceClass(label, idx)"
                @click="onSelectBatchChoice(label, idx)"
              >
                <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
                <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
                <Check
                  v-if="selectedBatchLetters().includes(getChoiceLetter(label, idx))"
                  class="study-choice-icon selected"
                />
              </button>
            </div>
          </template>
          <template v-else-if="batchQueue[batchIndex].question_type === 'multiple' && batchQueue[batchIndex].options?.length">
            <div class="choice-hint">可多选</div>
            <div class="study-choice-list">
              <button
                v-for="(label, idx) in batchQueue[batchIndex].options"
                :key="idx"
                type="button"
                class="study-choice"
                :class="batchChoiceClass(label, idx)"
                @click="onSelectBatchChoice(label, idx)"
              >
                <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
                <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
                <Check
                  v-if="selectedBatchLetters().includes(getChoiceLetter(label, idx))"
                  class="study-choice-icon selected"
                />
              </button>
            </div>
          </template>
          <template v-else>
            <div class="text-[11.5px] text-ink-3">写下你的答案,再点"提交并查看"</div>
            <n-input
              v-model:value="batchAnswer"
              type="textarea"
              placeholder="试着回忆一下答案..."
              :autosize="{ minRows: 3, maxRows: 7 }"
            />
          </template>
          <div class="flex items-center gap-2">
            <n-button
              type="primary"
              :disabled="!hasBatchAnswer()"
              @click="onBatchSubmit"
            >
              <Send class="w-3.5 h-3.5 mr-1" />
              提交并查看
            </n-button>
            <n-button quaternary @click="onBatchReveal">
              <Eye class="w-3.5 h-3.5 mr-1" />
              直接查看答案
            </n-button>
            <n-button quaternary class="ml-auto" @click="closeBatchRedo">
              退出
            </n-button>
          </div>
        </div>

        <div v-else class="space-y-2">
          <div v-if="batchQueue[batchIndex].options?.length" class="study-choice-list">
            <button
              v-for="(label, idx) in batchQueue[batchIndex].options"
              :key="idx"
              type="button"
              class="study-choice is-submitted"
              :class="batchChoiceClass(label, idx, true)"
              disabled
            >
              <span class="study-choice-letter">{{ getChoiceLetter(label, idx) }}</span>
              <span class="study-choice-text">{{ getChoiceText(label, idx) }}</span>
              <Check v-if="isCorrectChoice(batchQueue[batchIndex].correct_answer, label, idx)" class="study-choice-icon correct" />
              <XIcon v-if="isBatchChoiceWrong(label, idx)" class="study-choice-icon wrong" />
            </button>
          </div>
          <div v-if="hasBatchAnswer()" class="mistake-meta">
            <span class="text-ink-3">你的答案</span>
            <span :class="isBatchCorrect() ? 'text-success' : 'text-danger'">
              {{ formatBatchAnswer() }}
            </span>
            <span v-if="isBatchCorrect()" class="text-success text-[11px]">✓ 答对</span>
            <span v-else class="text-warning text-[11px]">✗ 还需巩固</span>
          </div>
          <div v-if="batchQueue[batchIndex].correct_answer" class="mistake-meta">
            <span class="text-ink-3">正确答案</span>
            <span class="text-ink-1">{{ batchQueue[batchIndex].correct_answer }}</span>
          </div>
          <div v-if="batchQueue[batchIndex].user_answer" class="mistake-meta">
            <span class="text-ink-3">原错答</span>
            <span class="text-danger">{{ batchQueue[batchIndex].user_answer }}</span>
          </div>
          <div v-if="batchQueue[batchIndex].analysis" class="mistake-meta">
            <span class="text-ink-3">解析</span>
            <span class="text-ink-2 whitespace-pre-wrap">{{ batchQueue[batchIndex].analysis }}</span>
          </div>
          <div class="flex items-center gap-2 pt-1">
            <n-button
              v-if="isBatchCorrect()"
              type="primary"
              @click="onBatchMarkMastered"
            >
              <Check class="w-3.5 h-3.5 mr-1" />
              标记掌握
            </n-button>
            <n-button
              v-else
              quaternary
              type="primary"
              @click="onBatchConvertToCard"
            >
              <Layers class="w-3.5 h-3.5 mr-1" />
              转闪卡反复练
            </n-button>
            <n-button @click="onBatchNext" class="ml-auto">
              {{ batchIndex + 1 < batchQueue.length ? '下一题' : '完成' }}
              <ChevronRight class="w-3.5 h-3.5 ml-1" />
            </n-button>
          </div>
        </div>
      </div>
      <div v-else class="text-center py-8">
        <div class="text-[15px] text-ink-1 font-medium mb-2">重做完成 🎉</div>
        <div class="text-[12px] text-ink-3 mb-1">已重做 {{ batchDoneCount }} 道</div>
        <div class="text-[12px] text-ink-3 mb-5">
          答对 {{ batchCorrectCount }} 道 · 答错 {{ batchDoneCount - batchCorrectCount }} 道
        </div>
        <n-button type="primary" @click="closeBatchRedo">完成</n-button>
      </div>
    </n-modal>

    <!-- 新建 / 重命名错题集 -->
    <n-modal
      :show="collectionEditorShow"
      preset="card"
      style="width: 420px; max-width: 92vw"
      :mask-closable="false"
      :title="collectionEditor.id ? '重命名错题集' : '新建错题集'"
      :bordered="false"
      @update:show="(v: boolean) => { if (!v) closeCollectionEditor() }"
    >
      <div class="space-y-3">
        <div>
          <label class="form-label">名称 <span class="text-danger">*</span></label>
          <n-input
            v-model:value="collectionEditor.name"
            placeholder="如:Python 错题集"
            maxlength="32"
            show-count
            @keyup.enter="onSubmitCollectionEditor"
          />
          <div v-if="collectionEditor.error" class="text-[12px] text-danger mt-1.5">
            {{ collectionEditor.error }}
          </div>
        </div>
        <div class="text-[11.5px] text-ink-3">
          {{ collectionEditor.id
            ? '重命名后会立即生效,不影响该错题集下的错题'
            : '创建后可在顶部"全部"右侧看到,再把错题批量加入进来' }}
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button quaternary @click="closeCollectionEditor">取消</n-button>
          <n-button type="primary" :loading="collectionEditor.submitting" @click="onSubmitCollectionEditor">
            {{ collectionEditor.id ? '保存' : '创建' }}
          </n-button>
        </div>
      </template>
    </n-modal>

    <!-- 错题集管理 -->
    <n-modal
      :show="collectionManageShow"
      preset="card"
      style="width: 520px; max-width: 92vw"
      :title="'错题集管理'"
      :bordered="false"
      @update:show="(v: boolean) => { if (!v) collectionManageShow = false }"
    >
      <div class="space-y-2.5">
        <div class="flex items-center justify-between">
          <div class="text-[12px] text-ink-3">
            共 <strong class="text-ink-1">{{ store.collections.length }}</strong> 个错题集
          </div>
          <n-button size="small" type="primary" @click="openCreateCollection">
            <Plus class="w-3.5 h-3.5 mr-1" />
            新建错题集
          </n-button>
        </div>
        <div
          v-if="store.collections.length === 0"
          class="text-center py-8 text-[12px] text-ink-3 border border-dashed border-line rounded-lg"
        >
          还没有错题集<br />
          <span class="text-[11px]">点击右上角"新建错题集"开始</span>
        </div>
        <div v-else class="space-y-2 max-h-[420px] overflow-y-auto pr-1">
          <div
            v-for="c in store.collections"
            :key="c.id"
            class="collection-manage-row"
            :class="activeCollectionId === c.id ? 'collection-manage-row-active' : ''"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <Tag class="w-3.5 h-3.5 text-hue-study" />
                <span class="text-[13.5px] font-medium text-ink-1 truncate">{{ c.name }}</span>
              </div>
              <div class="text-[11px] text-ink-3">
                共 {{ c.count }} 道 · 未掌握 {{ c.unmastered_count }} 道
                <span class="text-ink-4 ml-2">创建于 {{ formatDate(c.created_at) }}</span>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <n-button size="tiny" quaternary @click="openRenameCollection(c)">
                <Pencil class="w-3 h-3" />
              </n-button>
              <n-button size="tiny" quaternary type="error" @click="askDeleteCollection(c)">
                <Trash2 class="w-3 h-3" />
              </n-button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end">
          <n-button @click="collectionManageShow = false">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  NButton, NCheckbox, NImage, NImageGroup, NInput, NModal, NPopover, NPopselect, NSelect, NTabPane, NTabs, NTag,
  useDialog, useMessage,
} from 'naive-ui'
import {
  BookMarked, Calendar, Check, CheckCheck, CheckSquare, ChevronRight, Eye, FolderOpen,
  FolderPlus, Layers, MoreHorizontal, Paperclip, PenLine, Pencil, Play, Plus, RefreshCw, RotateCw, Search, Send,
  Settings, Tag, Trash2, X as XIcon, Code2, Film, MonitorPlay,
} from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AddMistakeModal from '@/components/studyTools/AddMistakeModal.vue'
import AddFlashcardModal from '@/components/studyTools/AddFlashcardModal.vue'
import { useStudyToolsStore } from '@/stores/studyToolsStore'
import { useSettingStore } from '@/stores/settingStore'
import type { FlashcardItem, MistakeCollection, MistakeItem, PracticeLabItem, PracticeLabType } from '@/api/studyTools'
import { createPracticeLab, deletePracticeLab, listPracticeLabs } from '@/api/studyTools'
import {
  formatMistakeSourceLabel,
  formatMistakeTagLabel,
  getChoiceLetter,
  getChoiceText,
} from '@/utils/studyToolsDisplay'

const store = useStudyToolsStore()
const settingStore = useSettingStore()
const message = useMessage()
const dialog = useDialog()

type TabName = 'mistakes' | 'flashcards' | 'labs'
const activeTab = ref<TabName>('mistakes')

// 错题过滤(NSelect 不接 boolean,改用字符串映射)
type MasteredFilter = 'all' | 'unmastered' | 'mastered'
const mistakeFilter = reactive<{ mastered: MasteredFilter; q: string }>({
  mastered: 'all',
  q: '',
})
const masteredOptions: Array<{ label: string; value: MasteredFilter }> = [
  { label: '全部', value: 'all' },
  { label: '未掌握', value: 'unmastered' },
  { label: '已掌握', value: 'mastered' },
]

// 闪卡过滤
const cardFilter = reactive<{ q: string }>({ q: '' })

// Modal 开关
const mistakeAddShow = ref(false)
const cardAddShow = ref(false)

// 复习会话
const reviewing = ref(false)
const reviewQueue = ref<FlashcardItem[]>([])
const reviewIndex = ref(0)
const reviewFlipped = ref(false)
const reviewDoneCount = ref(0)

// ─── 错题重做状态 ───
const redoingIds = ref<Set<string>>(new Set())
const redoAnswer = reactive<Record<string, string>>({})
const redoMultiAnswer = reactive<Record<string, string[]>>({})
const redoRevealed = reactive<Record<string, boolean>>({})
// 集中重做:全屏模式
const batchRedoing = ref(false)
const batchQueue = ref<MistakeItem[]>([])
const batchIndex = ref(0)
const batchAnswer = ref('')
const batchMultiAnswer = ref<string[]>([])
const batchRevealed = ref(false)
const batchDoneCount = ref(0)
const batchCorrectCount = ref(0)

// ─── 实操实验室 ───
const labs = ref<PracticeLabItem[]>([])
const labsTotal = ref(0)
const labsLoading = ref(false)
const selectedLabId = ref('')
const labForm = reactive<{
  type: PracticeLabType
  topic: string
  course: string
  knowledgePointsText: string
  starterCode: string
}>({
  type: 'animation',
  topic: '',
  course: '',
  knowledgePointsText: '',
  starterCode: '',
})

const selectedLab = computed(() => labs.value.find((lab) => lab.id === selectedLabId.value) || labs.value[0] || null)

function parseKnowledgePoints(text: string): string[] {
  return text
    .split(/[，,、/|]/)
    .map((row) => row.trim())
    .filter(Boolean)
    .slice(0, 10)
}

function isRequestTimeout(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err || '')
  return /timeout|exceeded|超时/i.test(message)
}

function getRequestErrorMessage(err: unknown): string {
  const data = (err as { response?: { data?: { message?: string; error?: string } } })?.response?.data
  return data?.message || data?.error || ''
}

async function fetchLabs() {
  labsLoading.value = true
  try {
    const result = await listPracticeLabs({ page_size: 50 })
    labs.value = result.items
    labsTotal.value = result.total
    if (!selectedLabId.value && result.items[0]) selectedLabId.value = result.items[0].id
    if (selectedLabId.value && !result.items.some((lab) => lab.id === selectedLabId.value)) {
      selectedLabId.value = result.items[0]?.id || ''
    }
  }
  catch (err) {
    console.error(err)
    message.error('实操实验加载失败')
  }
  finally {
    labsLoading.value = false
  }
}

async function onGenerateLab() {
  const topic = labForm.topic.trim()
  if (!topic) return
  labsLoading.value = true
  try {
    const lab = await createPracticeLab({
      type: labForm.type,
      topic,
      course: labForm.course.trim(),
      knowledge_points: parseKnowledgePoints(labForm.knowledgePointsText),
      starter_code: labForm.type === 'code' ? labForm.starterCode : undefined,
      content_model: settingStore.settings.content_model,
      content_api_key: settingStore.getEffectiveContentApiKey(),
      content_base_url: settingStore.getEffectiveContentBaseUrl(),
      content_provider_type: settingStore.getContentProviderType(),
    })
    selectedLabId.value = lab.id
    await fetchLabs()
    selectedLabId.value = lab.id
    await nextTick()
    message.success('实操实验已生成')
  }
  catch (err) {
    console.error(err)
    if (isRequestTimeout(err)) {
      message.warning('生成耗时较长，后端可能仍在完成，稍后自动刷新列表')
      window.setTimeout(() => {
        void fetchLabs()
      }, 8000)
    }
    else {
      message.error(getRequestErrorMessage(err) || '生成失败，请检查模型配置或稍后重试')
    }
  }
  finally {
    labsLoading.value = false
  }
}

async function onDeleteLab(id: string) {
  try {
    await deletePracticeLab(id)
    labs.value = labs.value.filter((lab) => lab.id !== id)
    labsTotal.value = Math.max(0, labsTotal.value - 1)
    if (selectedLabId.value === id) selectedLabId.value = labs.value[0]?.id || ''
    message.success('实验已删除')
  }
  catch (err) {
    console.error(err)
    message.error('删除失败')
  }
}

// ─── 错题下拉菜单 ───
const mistakeMenuId = ref<string | null>(null)
const mistakeMenuStyle = reactive<Record<string, string>>({ top: '0px', left: '0px' })
const cardMenuId = ref<string | null>(null)
const cardMenuStyle = reactive<Record<string, string>>({ top: '0px', left: '0px' })

function toggleMistakeMenu(id: string, ev?: MouseEvent) {
  if (mistakeMenuId.value === id) {
    mistakeMenuId.value = null
    return
  }
  mistakeMenuId.value = id
  nextTick(() => {
    const btn = (ev?.currentTarget as HTMLElement) || document.querySelector(`[data-menu-anchor="${id}"]`) as HTMLElement
    if (btn) {
      const rect = btn.getBoundingClientRect()
      mistakeMenuStyle.top = `${rect.bottom + 4}px`
      mistakeMenuStyle.left = `${rect.right - 160}px`
    }
  })
}

function toggleCardMenu(id: string, ev?: MouseEvent) {
  if (cardMenuId.value === id) {
    cardMenuId.value = null
    return
  }
  cardMenuId.value = id
  nextTick(() => {
    const btn = (ev?.currentTarget as HTMLElement) || document.querySelector(`[data-menu-anchor="card-${id}"]`) as HTMLElement
    if (btn) {
      const rect = btn.getBoundingClientRect()
      cardMenuStyle.top = `${rect.bottom + 4}px`
      cardMenuStyle.left = `${rect.right - 140}px`
    }
  })
}

function closeAllMenus() {
  mistakeMenuId.value = null
  cardMenuId.value = null
}

onMounted(() => document.addEventListener('click', closeAllMenus))
onUnmounted(() => document.removeEventListener('click', closeAllMenus))

// ─── 错题按题型分支工具 ───
function optionValue(label: string, idx: number): string {
  const m = String(label || '').trim().match(/^\(?([A-H])[\.\s\)]/)
  if (m) return m[1]
  return getChoiceLetter(label, idx)
}

function normalizeChoiceAnswer(value?: string | null): string {
  const letters = String(value || '').match(/[A-H]/gi)
  if (letters?.length) return Array.from(new Set(letters.map((x) => x.toUpperCase()))).sort().join('')
  return String(value || '').trim()
}

function choiceLetter(label: string, idx: number): string {
  return optionValue(label, idx)
}

function selectedRedoLetters(m: MistakeItem): string[] {
  if (m.question_type === 'multiple') return redoMultiAnswer[m.id] || []
  const answer = normalizeChoiceAnswer(redoAnswer[m.id])
  return answer ? answer.split('') : []
}

function selectedBatchLetters(): string[] {
  const cur = batchQueue.value[batchIndex.value]
  if (cur?.question_type === 'multiple') return batchMultiAnswer.value
  const answer = normalizeChoiceAnswer(batchAnswer.value)
  return answer ? answer.split('') : []
}

function onSelectRedoChoice(m: MistakeItem, label: string, idx: number) {
  const letter = choiceLetter(label, idx)
  if (m.question_type === 'multiple') {
    const current = new Set(redoMultiAnswer[m.id] || [])
    if (current.has(letter)) current.delete(letter)
    else current.add(letter)
    const next = Array.from(current).sort()
    redoMultiAnswer[m.id] = next
    redoAnswer[m.id] = next.join(' / ')
    return
  }
  redoAnswer[m.id] = letter
}

function onSelectBatchChoice(label: string, idx: number) {
  const cur = batchQueue.value[batchIndex.value]
  if (!cur) return
  const letter = choiceLetter(label, idx)
  if (cur.question_type === 'multiple') {
    const current = new Set(batchMultiAnswer.value)
    if (current.has(letter)) current.delete(letter)
    else current.add(letter)
    const next = Array.from(current).sort()
    batchMultiAnswer.value = next
    batchAnswer.value = next.join(' / ')
    return
  }
  batchAnswer.value = letter
}

function isCorrectChoice(correctAnswer: string | null | undefined, label: string, idx: number): boolean {
  return normalizeChoiceAnswer(correctAnswer).includes(choiceLetter(label, idx))
}

function isRedoChoiceWrong(m: MistakeItem, label: string, idx: number): boolean {
  const letter = choiceLetter(label, idx)
  return selectedRedoLetters(m).includes(letter) && !isCorrectChoice(m.correct_answer, label, idx)
}

function isBatchChoiceWrong(label: string, idx: number): boolean {
  const cur = batchQueue.value[batchIndex.value]
  if (!cur) return false
  const letter = choiceLetter(label, idx)
  return selectedBatchLetters().includes(letter) && !isCorrectChoice(cur.correct_answer, label, idx)
}

function redoChoiceClass(m: MistakeItem, label: string, idx: number, revealed = false): Record<string, boolean> {
  const letter = choiceLetter(label, idx)
  const selected = selectedRedoLetters(m).includes(letter)
  return {
    'is-selected': selected,
    'is-submitted': revealed,
    'is-correct': revealed && isCorrectChoice(m.correct_answer, label, idx),
    'is-wrong': revealed && selected && !isCorrectChoice(m.correct_answer, label, idx),
  }
}

function batchChoiceClass(label: string, idx: number, revealed = false): Record<string, boolean> {
  const cur = batchQueue.value[batchIndex.value]
  const letter = choiceLetter(label, idx)
  const selected = selectedBatchLetters().includes(letter)
  return {
    'is-selected': selected,
    'is-submitted': revealed,
    'is-correct': Boolean(cur && revealed && isCorrectChoice(cur.correct_answer, label, idx)),
    'is-wrong': Boolean(cur && revealed && selected && !isCorrectChoice(cur.correct_answer, label, idx)),
  }
}

function safeMistakeTags(tags?: string[] | null): string[] {
  return (tags || []).map(formatMistakeTagLabel).filter(Boolean)
}

function hasRedoAnswer(m: MistakeItem): boolean {
  if (m.question_type === 'multiple') {
    return (redoMultiAnswer[m.id] || []).length > 0
  }
  return Boolean((redoAnswer[m.id] || '').trim())
}

function hasBatchAnswer(): boolean {
  const cur = batchQueue.value[batchIndex.value]
  if (!cur) return false
  if (cur.question_type === 'multiple') {
    return batchMultiAnswer.value.length > 0
  }
  return Boolean(batchAnswer.value.trim())
}

function formatRedoAnswer(m: MistakeItem): string {
  if (m.question_type === 'multiple') {
    const vs = redoMultiAnswer[m.id] || []
    return vs.length ? vs.join(' / ') : '(未作答)'
  }
  return (redoAnswer[m.id] || '').trim() || '(未作答)'
}

function formatBatchAnswer(): string {
  const cur = batchQueue.value[batchIndex.value]
  if (!cur) return ''
  if (cur.question_type === 'multiple') {
    return batchMultiAnswer.value.length ? batchMultiAnswer.value.join(' / ') : '(未作答)'
  }
  return batchAnswer.value.trim() || '(未作答)'
}

// ─── 附件追加/删除状态 ───
const addingFor = ref<string | null>(null)
const removingAttId = ref<string | null>(null)

// ─── 错题集(用户自定义分类) ───
const activeCollectionId = ref<string | null>(null)
const selectedMistakeIds = ref<Set<string>>(new Set())
const batchAddToCollectionId = ref<string | null>(null)

const collectionEditor = reactive<{
  show: boolean
  id: string | null
  name: string
  error: string
  submitting: boolean
}>({
  show: false,
  id: null,
  name: '',
  error: '',
  submitting: false,
})
const collectionEditorShow = computed({
  get: () => collectionEditor.show,
  set: (v) => { collectionEditor.show = v },
})
const collectionManageShow = ref(false)

const collectionOptionsForBatch = computed(() =>
  store.collections.map((c) => ({ label: c.name, value: c.id })),
)

const unmasteredMistakes = computed(() =>
  store.mistakes.filter((m) => !m.mastered),
)

const stats = computed(() => store.stats)

const mistakeProgressText = computed(() => {
  if (!store.stats) return ''
  const { mastered, total } = store.stats.mistakes
  if (total === 0) return '暂无'
  return `已掌握 ${mastered} / ${total}`
})

function collectionNameById(id: string): string {
  return store.collections.find((c) => c.id === id)?.name || '未知集合'
}

onMounted(async () => {
  await refreshAll()
})

async function refreshAll() {
  try {
    await Promise.all([
      store.fetchStats(),
      store.fetchCollections(),
      store.fetchMistakes({ page_size: 50 }),
      store.fetchFlashcards({ page_size: 50 }),
      store.fetchDueCards(50),
      fetchLabs(),
      settingStore.fetchSettings(),
      settingStore.fetchProviders(),
    ])
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载失败')
  }
}

function selectCollection(id: string | null) {
  activeCollectionId.value = id
  clearSelection()
  void refetchMistakes()
}

async function refetchMistakes() {
  const masteredParam = mistakeFilter.mastered === 'all'
    ? undefined
    : mistakeFilter.mastered === 'mastered'
  await store.fetchMistakes({
    mastered: masteredParam,
    q: mistakeFilter.q || undefined,
    collection_id: activeCollectionId.value || undefined,
    page_size: 50,
  })
}

async function onMistakeFilterChange() {
  try {
    await refetchMistakes()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '筛选失败')
  }
}

async function onCardFilterChange() {
  try {
    await store.fetchFlashcards({ q: cardFilter.q || undefined, page_size: 50 })
  } catch (e) {
    message.error(e instanceof Error ? e.message : '筛选失败')
  }
}

async function onAddMistake(payload: Partial<MistakeItem>, files: File[]) {
  try {
    await store.addMistake(payload, files)
    await store.fetchStats()
    message.success('错题已加入')
  } catch (e) {
    throw e instanceof Error ? e : new Error('添加失败')
  }
}

async function onAddCard(payload: Partial<FlashcardItem>) {
  try {
    await store.addFlashcard(payload)
    await store.fetchStats()
    message.success('闪卡已创建')
  } catch (e) {
    throw e instanceof Error ? e : new Error('创建失败')
  }
}

async function onMarkMastered(m: MistakeItem) {
  try {
    await store.updateMistake(m.id, { mastered: true })
    await store.fetchStats()
    await store.fetchCollections()
    message.success('已标记掌握')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function onUnmarkMastered(m: MistakeItem) {
  try {
    await store.updateMistake(m.id, { mastered: false })
    await store.fetchStats()
    await store.fetchCollections()
    message.success('已取消掌握')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function onConvertToCard(m: MistakeItem) {
  try {
    await store.mistakeToFlashcard(m.id)
    await Promise.all([store.fetchStats(), store.fetchFlashcards({ page_size: 50 })])
    message.success('已转为闪卡,可在闪卡库查看')
    activeTab.value = 'flashcards'
  } catch (e) {
    message.error(e instanceof Error ? e.message : '转换失败')
  }
}

// ─── 错题附件:追加 / 删除 ───
async function onPickAttachments(m: MistakeItem, ev: Event) {
  const target = ev.target as HTMLInputElement
  const fileList = target.files
  if (!fileList || !fileList.length) return
  const files = Array.from(fileList)
  const remaining = 9 - (m.attachments || []).length
  if (remaining <= 0) {
    message.info('附件数量已达上限(9 张)')
    target.value = ''
    return
  }
  const tooBig = files.find((f) => f.size > 5 * 1024 * 1024)
  if (tooBig) {
    message.error(`单张图片不能超过 5MB: ${tooBig.name}`)
    target.value = ''
    return
  }
  const slice = files.slice(0, remaining)
  addingFor.value = m.id
  try {
    const result = await store.addAttachments(m.id, slice)
    if (result.saved.length) {
      message.success(`已追加 ${result.saved.length} 张图片`)
    }
    if (result.rejected && result.rejected.length) {
      message.warning(`已跳过 ${result.rejected.length} 个非图片文件`)
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    addingFor.value = null
    target.value = ''
  }
}

async function onRemoveAttachment(m: MistakeItem, attId: string) {
  removingAttId.value = attId
  try {
    await store.removeAttachment(m.id, attId)
    message.success('已删除附件')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '删除失败')
  } finally {
    removingAttId.value = null
  }
}

function askDelete(m: MistakeItem) {
  dialog.warning({
    title: '删除错题',
    content: `确定要删除「${truncate(m.stem, 20)}」吗?`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.deleteMistake(m.id)
        selectedMistakeIds.value.delete(m.id)
        await Promise.all([store.fetchStats(), store.fetchCollections()])
        message.success('已删除')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

function askDeleteCard(c: FlashcardItem) {
  dialog.warning({
    title: '删除闪卡',
    content: `确定要删除「${truncate(c.front, 20)}」吗?`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.deleteFlashcard(c.id)
        await Promise.all([store.fetchStats(), store.fetchDueCards(50)])
        message.success('已删除')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

// ─── 错题集:选择与批量 ───
function toggleSelect(id: string, checked: boolean) {
  const next = new Set(selectedMistakeIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedMistakeIds.value = next
}

function clearSelection() {
  if (selectedMistakeIds.value.size > 0) {
    selectedMistakeIds.value = new Set()
  }
}

async function onBatchAddToCollection(collectionId: string) {
  if (!collectionId) return
  const ids = Array.from(selectedMistakeIds.value)
  if (ids.length === 0) return
  try {
    const result = await store.addMistakesToCollection(collectionId, ids)
    const cname = collectionNameById(collectionId)
    if (result.added > 0) {
      message.success(`已加入「${cname}」· ${result.added} 道`)
    } else {
      message.info('所选错题已全部在该集合中')
    }
    clearSelection()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加入失败')
  } finally {
    batchAddToCollectionId.value = null
  }
}

function onBatchDeleteSelected() {
  const ids = Array.from(selectedMistakeIds.value)
  if (ids.length === 0) return
  dialog.warning({
    title: '批量删除错题',
    content: `确定要删除选中的 ${ids.length} 道错题吗?`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await Promise.all(ids.map((id) => store.deleteMistake(id)))
        await Promise.all([store.fetchStats(), store.fetchCollections()])
        clearSelection()
        message.success(`已删除 ${ids.length} 道`)
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

// ─── 错题集:单题切换归属 ───
async function onToggleMistakeInCollection(m: MistakeItem, collectionId: string, joined: boolean) {
  try {
    if (joined) {
      const ids = [m.id]
      const result = await store.addMistakesToCollection(collectionId, ids)
      if (result.added > 0) {
        message.success(`已加入「${collectionNameById(collectionId)}」`)
      }
    } else {
      await store.removeMistakeFromCollection(collectionId, m.id)
      message.success(`已从「${collectionNameById(collectionId)}」移除`)
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

// ─── 错题集:编辑器 ───
function openCreateCollection() {
  collectionEditor.id = null
  collectionEditor.name = ''
  collectionEditor.error = ''
  collectionEditor.submitting = false
  collectionEditor.show = true
}

function openRenameCollection(c: MistakeCollection) {
  collectionEditor.id = c.id
  collectionEditor.name = c.name
  collectionEditor.error = ''
  collectionEditor.submitting = false
  collectionEditor.show = true
}

function closeCollectionEditor() {
  collectionEditor.show = false
  collectionEditor.error = ''
}

async function onSubmitCollectionEditor() {
  const name = collectionEditor.name.trim()
  if (!name) {
    collectionEditor.error = '名称不能为空'
    return
  }
  if (name.length > 32) {
    collectionEditor.error = '名称不能超过 32 个字符'
    return
  }
  collectionEditor.error = ''
  collectionEditor.submitting = true
  try {
    if (collectionEditor.id) {
      await store.renameCollection(collectionEditor.id, name)
      message.success('已重命名')
    } else {
      const item = await store.createCollection(name)
      message.success(`已创建「${item.name}」`)
    }
    closeCollectionEditor()
  } catch (e) {
    const msg = e instanceof Error ? e.message : '操作失败'
    if (msg.includes('已存在同名')) {
      collectionEditor.error = msg
    } else {
      message.error(msg)
    }
  } finally {
    collectionEditor.submitting = false
  }
}

function openManageCollections() {
  collectionManageShow.value = true
  store.fetchCollections().catch(() => undefined)
}

function askDeleteCollection(c: MistakeCollection) {
  const tip = c.count > 0
    ? `删除「${c.name}」?该集合下的 ${c.count} 道错题不会被删除,只是从集合中移除。`
    : `确定要删除空集合「${c.name}」?`
  dialog.warning({
    title: '删除错题集',
    content: tip,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.deleteCollection(c.id)
        if (activeCollectionId.value === c.id) {
          activeCollectionId.value = null
          await refetchMistakes()
        }
        message.success('已删除')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

// ─── 复习流程 ───
async function startReview() {
  if (!store.dueCards || store.dueCards.length === 0) {
    message.info('今日已复习完,改为复习全部')
    await startReviewAll()
    return
  }
  reviewQueue.value = [...store.dueCards]
  reviewIndex.value = 0
  reviewFlipped.value = false
  reviewDoneCount.value = 0
  reviewing.value = true
}

async function startReviewAll() {
  try {
    await store.fetchFlashcards({ page_size: 500 })
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载闪卡失败')
    return
  }
  if (!store.flashcards || store.flashcards.length === 0) {
    message.info('还没有闪卡')
    return
  }
  reviewQueue.value = [...store.flashcards]
  reviewIndex.value = 0
  reviewFlipped.value = false
  reviewDoneCount.value = 0
  reviewing.value = true
}

function startReviewOne(c: FlashcardItem) {
  reviewQueue.value = [c]
  reviewIndex.value = 0
  reviewFlipped.value = false
  reviewDoneCount.value = 0
  reviewing.value = true
}

function onFlip() {
  reviewFlipped.value = !reviewFlipped.value
}

async function onGrade(grade: number) {
  const card = reviewQueue.value[reviewIndex.value]
  if (!card) return
  try {
    const updated = await store.reviewFlashcard(card.id, grade)
    const due = updated?.sm2?.due_date || '—'
    message.success(`已记录 · 下次复习: ${due}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '提交失败')
  }
  reviewDoneCount.value += 1
  reviewIndex.value += 1
  reviewFlipped.value = false
}

async function closeReview() {
  reviewing.value = false
  await Promise.all([
    store.fetchStats(),
    store.fetchFlashcards({ page_size: 50 }),
    store.fetchDueCards(50),
  ]).catch(() => undefined)
}

// ─── 错题重做(单题内联) ───
function openRedo(m: MistakeItem) {
  redoingIds.value = new Set([...redoingIds.value, m.id])
  redoAnswer[m.id] = ''
  redoMultiAnswer[m.id] = []
  redoRevealed[m.id] = false
}

function closeRedo(m: MistakeItem) {
  const next = new Set(redoingIds.value)
  next.delete(m.id)
  redoingIds.value = next
  delete redoAnswer[m.id]
  delete redoMultiAnswer[m.id]
  delete redoRevealed[m.id]
}

function onSubmitRedo(m: MistakeItem) {
  redoRevealed[m.id] = true
}

function onRevealRedo(m: MistakeItem) {
  redoRevealed[m.id] = true
}

function onPeek(m: MistakeItem) {
  redoingIds.value = new Set([...redoingIds.value, m.id])
  redoAnswer[m.id] = ''
  redoRevealed[m.id] = true
}

function isRedoCorrect(m: MistakeItem): boolean {
  const got = (redoAnswer[m.id] || '').trim()
  if (!got) return false
  const expected = String(m.correct_answer || '').trim()
  if (!expected) return false
  return normalizeChoiceAnswer(got) === normalizeChoiceAnswer(expected)
}

// ─── 错题重做(集中全屏) ───
function startBatchRedo() {
  const queue = unmasteredMistakes.value
  if (queue.length === 0) {
    message.info('没有未掌握的错题可以重做')
    return
  }
  batchQueue.value = [...queue]
  batchIndex.value = 0
  batchAnswer.value = ''
  batchMultiAnswer.value = []
  batchRevealed.value = false
  batchDoneCount.value = 0
  batchCorrectCount.value = 0
  batchRedoing.value = true
}

function onBatchSubmit() {
  if (!hasBatchAnswer()) return
  batchRevealed.value = true
}

function onBatchReveal() {
  batchRevealed.value = true
}

function isBatchCorrect(): boolean {
  if (!batchRevealed.value) return false
  const got = batchAnswer.value.trim()
  if (!got) return false
  const expected = String(batchQueue.value[batchIndex.value]?.correct_answer || '').trim()
  if (!expected) return false
  return normalizeChoiceAnswer(got) === normalizeChoiceAnswer(expected)
}

function onBatchNext() {
  if (batchRevealed.value) {
    batchDoneCount.value += 1
    if (isBatchCorrect()) batchCorrectCount.value += 1
  }
  if (batchIndex.value + 1 < batchQueue.value.length) {
    batchIndex.value += 1
    batchAnswer.value = ''
    batchMultiAnswer.value = []
    batchRevealed.value = false
  } else {
    batchIndex.value = batchQueue.value.length
  }
}

async function onBatchMarkMastered() {
  const m = batchQueue.value[batchIndex.value]
  if (!m) return
  try {
    await store.updateMistake(m.id, { mastered: true })
    await store.fetchStats()
    await store.fetchCollections()
    message.success('已标记掌握')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function onBatchConvertToCard() {
  const m = batchQueue.value[batchIndex.value]
  if (!m) return
  try {
    await store.mistakeToFlashcard(m.id)
    await Promise.all([store.fetchStats(), store.fetchFlashcards({ page_size: 50 })])
    message.success('已转为闪卡')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '转换失败')
  }
}

function closeBatchRedo() {
  batchRedoing.value = false
  refetchMistakes().catch(() => undefined)
  store.fetchCollections().catch(() => undefined)
}

// ─── 工具 ───
function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

function formatDate(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const pad = (x: number) => String(x).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  } catch {
    return ''
  }
}

function formatSize(bytes?: number | null): string {
  if (bytes == null || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

function sourceLabel(s: string): string {
  switch (s) {
    case 'manual': return '手动添加'
    case 'mistake': return '错题'
    case 'card': return '知识卡'
    case 'ai': return 'AI'
    case 'classroom': return '课堂同步'
    default: return '学习记录'
  }
}

function sourceTagType(s: string): 'default' | 'success' | 'info' | 'warning' {
  if (s === 'mistake') return 'warning'
  if (s === 'ai') return 'success'
  if (s === 'card') return 'info'
  return 'default'
}
</script>

<style scoped>
/* ================================================================
   Study Tools — Warm Amber Palette
   Color source: tokens.css --hue-study-rgb: 201 150 60
   ================================================================ */

/* ── Keyframes ── */
@keyframes study-fade-up {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes study-scale-in {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}

/* ── Page ── */
.study-tools-page {
  --study-accent-rgb: 201 150 60;
  --study-accent-soft-rgb: 251 244 230;
  background:
    radial-gradient(ellipse at 12% 8%, rgb(var(--study-accent-rgb) / 0.04), transparent 40%),
    linear-gradient(180deg, rgb(var(--bg-base-rgb)) 0%, rgb(var(--bg-subtle-rgb) / 0.3) 100%);
}

.study-tools-scroll {
  padding: 0 28px 28px;
}

.study-shell {
  max-width: 960px;
  margin: 0 auto;
}

.study-main {
  min-width: 0;
  padding-top: 12px;
}

/* ============ Stats Grid ============ */
.study-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

/* ============ Tab Bar ============ */
.study-tab-bar {
  display: flex;
  gap: 4px;
  padding: 3px;
  margin-bottom: 12px;
  background: rgb(var(--bg-subtle-rgb) / 0.6);
  border-radius: 10px;
  width: fit-content;
  animation: study-fade-up 300ms var(--ease-out) both;
  animation-delay: 80ms;
}
.study-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 200ms var(--ease-out), color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
  white-space: nowrap;
}
.study-tab-btn:hover {
  color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-surface-rgb) / 0.5);
}
.study-tab-btn-active {
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--study-accent-rgb));
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
}

.study-panel {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb) / 0.7);
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 6px 24px -12px rgba(15, 23, 42, 0.08);
  animation: study-scale-in 320ms var(--ease-out) both;
  animation-delay: 100ms;
}

/* ============ 工具栏 ============ */
.study-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.study-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.study-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.study-toolbar-chips {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolbar-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 999px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 160ms var(--ease-out);
  white-space: nowrap;
}

.toolbar-chip:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.18);
  color: rgb(var(--ink-1-rgb));
}

.toolbar-chip-active {
  background: rgb(var(--study-accent-rgb) / 0.06);
  border-color: rgb(var(--study-accent-rgb) / 0.12);
  color: rgb(var(--study-accent-rgb));
}

.toolbar-chip-badge {
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
  font-variant-numeric: tabular-nums;
}

.toolbar-chip-active .toolbar-chip-badge {
  background: rgb(var(--study-accent-rgb) / 0.10);
  color: rgb(var(--study-accent-rgb));
}

.study-secondary-button {
  border-color: rgb(var(--line-rgb)) !important;
  background: rgb(var(--bg-surface-rgb)) !important;
}

.study-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ============ Stats Tiles ============ */
.stat-tile {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb) / 0.7);
  border-radius: 10px;
  padding: 18px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out), transform 200ms var(--ease-out);
  cursor: pointer;
  animation: study-scale-in 380ms var(--ease-out) both;
}
.stat-tile:nth-child(1) { animation-delay: 0ms; }
.stat-tile:nth-child(2) { animation-delay: 60ms; }
.stat-tile:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.2);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06), 0 8px 24px -8px rgba(15, 23, 42, 0.1);
  transform: translateY(-1px);
}
.stat-tile-active {
  border-color: rgb(var(--study-accent-rgb) / 0.25);
  box-shadow: 0 0 0 2px rgb(var(--study-accent-rgb) / 0.08), 0 2px 8px rgba(15, 23, 42, 0.06);
  background: linear-gradient(135deg, rgb(var(--study-accent-rgb) / 0.02), rgb(var(--bg-surface-rgb)));
}
.stat-tile-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.stat-tile-icon::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 14px;
  opacity: 0;
  transition: opacity 200ms var(--ease-out);
}
.stat-tile:hover .stat-tile-icon::after {
  opacity: 1;
}
.stat-tile-icon-mistakes {
  background: linear-gradient(135deg, rgb(var(--danger-rgb) / 0.10), rgb(var(--danger-rgb) / 0.05));
  color: rgb(var(--danger-rgb));
}
.stat-tile-icon-mistakes::after {
  background: rgb(var(--danger-rgb) / 0.04);
}
.stat-tile-icon-flashcards {
  background: linear-gradient(135deg, rgb(var(--study-accent-rgb) / 0.14), rgb(var(--study-accent-rgb) / 0.06));
  color: rgb(var(--study-accent-rgb));
}
.stat-tile-icon-flashcards::after {
  background: rgb(var(--study-accent-rgb) / 0.04);
}

/* ============ Mistake Card ============ */
.mistake-card {
  position: relative;
  overflow: visible;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb) / 0.7);
  border-radius: 10px;
  padding: 16px 18px 14px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
  animation: study-fade-up 360ms var(--ease-out) both;
}
.study-list > .mistake-card:nth-child(-n+8) {
  animation-delay: calc(var(--i, 0) * 40ms);
}
.study-list > .mistake-card:nth-child(1) { --i: 0; }
.study-list > .mistake-card:nth-child(2) { --i: 1; }
.study-list > .mistake-card:nth-child(3) { --i: 2; }
.study-list > .mistake-card:nth-child(4) { --i: 3; }
.study-list > .mistake-card:nth-child(5) { --i: 4; }
.study-list > .mistake-card:nth-child(6) { --i: 5; }
.study-list > .mistake-card:nth-child(7) { --i: 6; }
.study-list > .mistake-card:nth-child(8) { --i: 7; }
.mistake-card:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.18);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06), 0 8px 24px -8px rgba(15, 23, 42, 0.1);
}
.mistake-card-mastered {
  opacity: 0.82;
}
.mistake-card-redoing {
  border-color: rgb(var(--study-accent-rgb) / 0.18);
  box-shadow: 0 0 0 3px rgb(var(--study-accent-rgb) / 0.03), 0 18px 38px -30px rgba(15, 23, 42, 0.34);
}
.mistake-card-selected {
  border-color: rgb(var(--study-accent-rgb) / 0.22);
  background: rgb(var(--study-accent-rgb) / 0.016);
}

.mistake-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 10px;
}
.mistake-card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}
.mistake-card-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.mistake-date {
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.study-chip,
.study-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 22px;
  max-width: 320px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgb(var(--line-subtle-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 11.5px;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.study-chip-info {
  max-width: none;
  white-space: normal;
  word-break: break-all;
  background: rgb(var(--study-accent-rgb) / 0.06);
  border-color: rgb(var(--study-accent-rgb) / 0.12);
  color: rgb(var(--study-accent-rgb));
}
.study-chip-source {
  background: rgb(var(--bg-subtle-rgb));
  border-color: rgb(var(--line-rgb));
  color: rgb(var(--ink-3-rgb));
}
.study-chip-collection {
  background: rgb(var(--study-accent-rgb) / 0.045);
  border-color: rgb(var(--study-accent-rgb) / 0.10);
  color: rgb(var(--study-accent-rgb));
}
.study-chip-source-mistake {
  background: rgb(var(--study-accent-rgb) / 0.06);
  border-color: rgb(var(--study-accent-rgb) / 0.12);
  color: rgb(var(--study-accent-rgb));
}

.mistake-stem {
  margin: 8px 0 13px;
  color: rgb(var(--ink-1-rgb));
  font-size: 15px;
  font-weight: 650;
  line-height: 1.6;
  white-space: pre-wrap;
}
.mistake-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.study-tag {
  background: rgb(var(--bg-surface-rgb) / 0.76);
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
}

.mistake-source-row {
  margin-top: 8px;
}
.source-tag-inline {
  display: inline-block;
  padding: 2px 8px;
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 999px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
}

/* ============ 选择题样式 ============ */
.choice-hint {
  color: rgb(var(--ink-3-rgb));
  font-size: 11.5px;
  font-weight: 500;
}
.study-choice-list {
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.study-choice {
  appearance: none;
  width: 100%;
  min-height: 54px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 12px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 9px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  cursor: pointer;
  text-align: left;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.03);
  transition: border-color 160ms var(--ease-out), background 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
}
.study-choice:hover:not(:disabled):not(.is-submitted) {
  border-color: rgb(var(--study-accent-rgb) / 0.20);
  background: rgb(var(--study-accent-rgb) / 0.016);
}
.study-choice.is-selected:not(.is-submitted) {
  border-color: rgb(var(--study-accent-rgb) / 0.28);
  background: rgb(var(--study-accent-rgb) / 0.045);
  box-shadow: inset 0 0 0 1px rgb(var(--study-accent-rgb) / 0.12);
  color: rgb(var(--ink-1-rgb));
}
.study-choice.is-submitted {
  cursor: default;
}
.study-choice.is-correct {
  border-color: rgb(var(--study-accent-rgb) / 0.28);
  background: rgb(var(--study-accent-rgb) / 0.045);
  color: rgb(var(--ink-1-rgb));
}
.study-choice.is-wrong {
  border-color: rgb(var(--danger-rgb) / 0.32);
  background: rgb(var(--danger-rgb) / 0.04);
  color: rgb(var(--danger-rgb));
}
.study-choice-letter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 31px;
  height: 31px;
  border-radius: 8px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
  font-size: 11.5px;
  font-weight: 750;
  flex: 0 0 auto;
  transition: background 160ms var(--ease-out), color 160ms var(--ease-out);
}
.study-choice.is-selected:not(.is-submitted) .study-choice-letter,
.study-choice.is-correct .study-choice-letter {
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--study-accent-rgb));
}
.study-choice.is-wrong .study-choice-letter {
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--danger-rgb));
}
.study-choice-text {
  flex: 1;
  min-width: 0;
  color: inherit;
  font-size: 14px;
  font-weight: 520;
  line-height: 1.45;
}
.study-choice-icon {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}
.study-choice-icon.selected,
.study-choice-icon.correct {
  padding: 2px;
  border: 2px solid rgb(var(--study-accent-rgb));
  border-radius: 999px;
  color: rgb(var(--study-accent-rgb));
  opacity: 0.75;
}
.study-choice-icon.wrong {
  padding: 2px;
  border: 2px solid rgb(var(--danger-rgb));
  border-radius: 999px;
  color: rgb(var(--danger-rgb));
  opacity: 0.75;
}

/* ============ 批量操作条 ============ */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: rgb(var(--study-accent-rgb) / 0.035);
  border: 1px solid rgb(var(--study-accent-rgb) / 0.14);
  border-radius: 10px;
  flex-wrap: wrap;
}
.batch-bar-enter-active,
.batch-bar-leave-active {
  transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
}
.batch-bar-enter-from,
.batch-bar-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ============ 错题集 popover 行 ============ */
.collection-popover-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12.5px;
  color: rgb(var(--ink-1-rgb));
  transition: background 120ms var(--ease-out);
}
.collection-popover-row:hover {
  background: rgb(var(--bg-subtle-rgb));
}

/* ============ 错题集管理弹窗行 ============ */
.collection-manage-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  transition: border-color 160ms var(--ease-out);
}
.collection-manage-row:hover {
  border-color: rgb(var(--line-rgb));
}
.collection-manage-row-active {
  border-color: rgb(var(--study-accent-rgb) / 0.22);
  background: rgb(var(--study-accent-rgb) / 0.024);
}

.form-label {
  display: block;
  font-size: 12.5px;
  color: var(--ink-secondary);
  margin-bottom: 6px;
  font-weight: 500;
}

/* ============ 错题图片附件 ============ */
.attachment-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.attachment-thumb {
  border-radius: 6px !important;
  overflow: hidden;
  border: 1px solid rgb(var(--line-subtle-rgb));
  background: rgb(var(--bg-subtle-rgb));
  flex-shrink: 0;
  transition: border-color 160ms var(--ease-out);
  cursor: zoom-in;
}
.attachment-thumb:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.24);
}

/* ============ 附件管理 popover ============ */
.attachment-popover-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  color: rgb(var(--ink-1-rgb));
}
.attachment-popover-thumb {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  object-fit: cover;
  border: 1px solid rgb(var(--line-subtle-rgb));
  flex-shrink: 0;
}
.attachment-add-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 0;
  border-radius: 6px;
  cursor: pointer;
  color: rgb(var(--study-accent-rgb));
  transition: background 120ms var(--ease-out);
}
.attachment-add-row:hover {
  background: rgb(var(--study-accent-rgb) / 0.045);
}
.attachment-add-row input:disabled {
  cursor: not-allowed;
}

/* 默认态:答案已隐藏 */
.reveal-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: linear-gradient(90deg, rgb(var(--study-accent-rgb) / 0.024), rgb(var(--bg-subtle-rgb) / 0.56));
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 8px;
}
.reveal-hint > span:first-child {
  flex: 1;
  min-width: 0;
}

/* 内联重做输入区 */
.redo-panel {
  background: rgb(var(--bg-surface-rgb));
  border: 0;
  border-radius: 0;
  padding: 2px 0 4px;
  margin-bottom: 10px;
}

.redo-result-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 184px;
  gap: 16px;
  align-items: start;
}

.redo-result-main {
  min-width: 0;
}

.redo-explain-card {
  margin-top: 13px;
  padding: 14px 16px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 9px;
  background: linear-gradient(180deg, rgb(var(--bg-surface-rgb)), rgb(var(--study-accent-rgb) / 0.016));
}

.redo-convert-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
  padding: 0;
  border: 0;
  background: transparent;
  color: rgb(var(--study-accent-rgb));
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
  opacity: 0.82;
}

.redo-knowledge-card {
  padding: 18px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-surface-rgb));
  box-shadow: 0 12px 28px -25px rgba(15, 23, 42, 0.34);
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  line-height: 1.65;
}

.redo-knowledge-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 13px;
  color: rgb(var(--study-accent-rgb));
  font-size: 13px;
  font-weight: 750;
  opacity: 0.82;
}

.mistake-action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 13px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--line-subtle-rgb));
  flex-wrap: wrap;
}

/* 已掌握错题:内联展示答案 */
.mistake-meta-list {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.mistake-meta-list .mistake-meta:first-child {
  margin-top: 0;
}

/* 集中重做弹窗的题干 */
.batch-stem {
  background: rgb(var(--bg-subtle-rgb));
  border-left: 3px solid rgb(var(--study-accent-rgb) / 0.72);
  border-radius: 6px;
  padding: 14px 16px;
  font-size: 14.5px;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.7;
  white-space: pre-wrap;
  min-height: 80px;
}

.mistake-meta {
  display: flex;
  gap: 6px;
  font-size: 12px;
  line-height: 1.6;
  margin-top: 4px;
}
.mistake-meta > span:first-child {
  flex-shrink: 0;
  min-width: 36px;
  font-weight: 500;
}

/* ============ 下拉菜单 ============ */
.mistake-menu-wrap {
  position: relative;
}

.mistake-menu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  transition: background 120ms var(--ease-out), color 120ms var(--ease-out);
}
.mistake-menu-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

.mistake-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
}

.mistake-menu-dropdown {
  position: fixed;
  z-index: 1000;
  min-width: 150px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb) / 0.8);
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.14), 0 2px 6px rgba(15, 23, 42, 0.06);
  animation: study-scale-in 160ms var(--ease-out) both;
  transform-origin: top right;
}

.mistake-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgb(var(--ink-2-rgb));
  font-size: 12.5px;
  cursor: pointer;
  text-align: left;
  transition: background 100ms var(--ease-out), color 100ms var(--ease-out);
}
.mistake-menu-item:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}
.mistake-menu-item-danger:hover {
  background: rgb(var(--danger-rgb) / 0.04);
  color: rgb(var(--danger-rgb));
}

.mistake-menu-divider {
  height: 1px;
  margin: 3px 0;
  background: rgb(var(--line-subtle-rgb));
}

/* ============ Flashcard Row ============ */
.card-row {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb) / 0.7);
  border-radius: 10px;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
  animation: study-fade-up 360ms var(--ease-out) both;
}
.study-list > .card-row:nth-child(-n+8) {
  animation-delay: calc(var(--i, 0) * 40ms);
}
.study-list > .card-row:nth-child(1) { --i: 0; }
.study-list > .card-row:nth-child(2) { --i: 1; }
.study-list > .card-row:nth-child(3) { --i: 2; }
.study-list > .card-row:nth-child(4) { --i: 3; }
.study-list > .card-row:nth-child(5) { --i: 4; }
.study-list > .card-row:nth-child(6) { --i: 5; }
.study-list > .card-row:nth-child(7) { --i: 6; }
.study-list > .card-row:nth-child(8) { --i: 7; }
.card-row:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.18);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06), 0 8px 24px -8px rgba(15, 23, 42, 0.1);
}
.card-row-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.card-row-front {
  color: rgb(var(--ink-1-rgb));
  font-size: 15px;
  font-weight: 700;
  line-height: 1.55;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-row-back {
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  line-height: 1.75;
  padding: 12px 14px;
  border-radius: 8px;
  background: linear-gradient(90deg, rgb(var(--study-accent-rgb) / 0.018), rgb(var(--bg-subtle-rgb) / 0.66));
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-row-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--line-subtle-rgb));
}
.card-row-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  color: rgb(var(--ink-3-rgb));
  font-size: 11.5px;
  flex-wrap: wrap;
}
.card-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-menu-wrap {
  position: relative;
}

/* ============ 复习弹窗卡片翻转 ============ */
.flash-stage {
  perspective: 1200px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  cursor: pointer;
}
.flash-card {
  position: relative;
  width: 100%;
  min-height: 200px;
  transition: transform 480ms var(--ease-spring);
  transform-style: preserve-3d;
}
.flash-card-flipped {
  transform: rotateY(180deg);
}
.flash-face {
  position: absolute;
  inset: 0;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  padding: 24px 20px;
  backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}
.flash-face-back {
  transform: rotateY(180deg);
  background: linear-gradient(180deg, rgb(var(--bg-surface-rgb)) 0%, rgb(var(--study-accent-rgb) / 0.026) 100%);
  border-color: rgb(var(--study-accent-rgb) / 0.14);
}

.grade-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 7px 8px;
  min-height: 34px;
  height: auto;
  border-color: rgb(var(--line-rgb)) !important;
  background: rgb(var(--bg-surface-rgb)) !important;
  color: rgb(var(--ink-2-rgb)) !important;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.03);
  transition: border-color 160ms var(--ease-out), background 160ms var(--ease-out), color 160ms var(--ease-out);
}
.grade-btn:hover {
  border-color: rgb(var(--study-accent-rgb) / 0.24) !important;
  background: rgb(var(--study-accent-rgb) / 0.04) !important;
  color: rgb(var(--ink-1-rgb)) !important;
}
.grade-btn :deep(.n-button__content) {
  width: 100%;
  justify-content: center;
  gap: 5px;
}
.grade-btn span {
  margin-left: 0 !important;
}
.grade-btn span:first-child {
  color: rgb(var(--ink-3-rgb));
  font-weight: 700;
  opacity: 1;
}
.grade-btn-0 { border-color: rgb(var(--danger-rgb) / 0.18) !important; }
.grade-btn-1 { border-color: rgb(var(--study-accent-rgb) / 0.20) !important; }
.grade-btn-3 { border-color: rgb(var(--study-accent-rgb) / 0.18) !important; }
.grade-btn-5 { border-color: rgb(var(--study-accent-rgb) / 0.22) !important; }
.grade-btn-0:hover { background: rgb(var(--danger-rgb) / 0.04) !important; }
.grade-btn-1:hover { background: rgb(var(--study-accent-rgb) / 0.05) !important; }
.grade-btn-3:hover,
.grade-btn-5:hover { background: rgb(var(--study-accent-rgb) / 0.045) !important; }

/* ============ 实操实验室 ============ */
.practice-lab-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  gap: 14px;
}
.practice-lab-builder,
.practice-lab-list-panel,
.practice-lab-preview {
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  border-radius: 8px;
  padding: 14px;
}
.practice-lab-builder {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-self: start;
}
.practice-lab-section-head,
.practice-lab-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.practice-lab-title {
  font-size: 14px;
  font-weight: 650;
  color: rgb(var(--ink-1-rgb));
}
.practice-lab-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}
.practice-type-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.practice-type-btn {
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 6px;
  background: rgb(var(--bg-soft-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
}
.practice-type-btn-active {
  border-color: rgb(var(--study-accent-rgb) / 0.32);
  background: rgb(var(--study-accent-rgb) / 0.08);
  color: rgb(var(--ink-1-rgb));
}
.practice-lab-list {
  display: grid;
  gap: 10px;
}
.practice-lab-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-soft-rgb));
  border-radius: 8px;
  padding: 12px;
}
.practice-lab-card:hover,
.practice-lab-card-active {
  border-color: rgb(var(--study-accent-rgb) / 0.28);
  background: rgb(var(--study-accent-rgb) / 0.045);
}
.practice-lab-card-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.practice-lab-card-main strong {
  color: rgb(var(--ink-1-rgb));
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.practice-lab-card-main span:not(.practice-lab-kind) {
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
  line-height: 1.45;
}
.practice-lab-kind {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: rgb(var(--study-accent-rgb));
  font-size: 11px;
  font-weight: 600;
}
.practice-lab-preview {
  margin-top: 14px;
}
.video-prompt-box {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid rgb(var(--study-accent-rgb) / 0.16);
  background: rgb(var(--study-accent-rgb) / 0.035);
  border-radius: 8px;
}
.practice-lab-frame {
  width: 100%;
  height: min(78vh, 760px);
  min-height: 680px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: #fff;
}

/* ============ Tabs 状态容器：切换入口只保留左侧栏 ============ */
.study-tabs :deep(.n-tabs-nav) {
  display: none;
}
.study-tabs :deep(.n-tabs-pane-wrapper) {
  padding-top: 0;
}

/* ============ Mobile ============ */
@media (max-width: 767px) {
  .study-tools-scroll {
    padding: 0 12px 16px;
  }
  .study-main {
    padding-top: 6px;
  }
  .study-stats-grid,
  .redo-result-layout,
  .practice-lab-layout {
    grid-template-columns: 1fr;
  }
  .study-panel {
    padding: 12px;
  }
  .study-toolbar,
  .card-row-footer {
    align-items: stretch;
  }
  .study-toolbar-left,
  .study-toolbar-right,
  .card-row-meta,
  .card-row-actions {
    width: 100%;
  }
  .study-toolbar-left :deep(.n-input),
  .study-toolbar-left :deep(.n-select) {
    width: 100% !important;
  }
  .stat-tile {
    padding: 14px;
  }
  .mistake-card,
  .card-row {
    padding: 14px;
  }
  .mistake-action-bar {
    align-items: stretch;
  }
  .flash-face {
    padding: 20px 16px;
  }
  .practice-lab-frame {
    height: 620px;
    min-height: 520px;
  }
}
</style>
