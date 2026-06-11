<template>
  <div class="h-full flex flex-col">
    <PageHeader title="学习工具" description="错题本 + 闪卡复习 · 越用越懂你">
      <template #actions>
        <n-button quaternary size="small" @click="refreshAll">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          刷新
        </n-button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-5xl mx-auto space-y-5">
        <!-- 顶部两个统计入口卡 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <button
            class="stat-tile text-left"
            :class="activeTab === 'mistakes' ? 'stat-tile-active' : ''"
            @click="activeTab = 'mistakes'"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="stat-tile-icon bg-hue-study/12 text-hue-study">
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
            :class="activeTab === 'flashcards' ? 'stat-tile-active' : ''"
            @click="activeTab = 'flashcards'"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="stat-tile-icon bg-hue-study/12 text-hue-study">
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

        <!-- 主体 Tab -->
        <div class="surface-card p-5">
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
                <!-- 错题集筛选条 -->
                <div class="collection-bar mb-3">
                  <div class="collection-bar-tags">
                    <button
                      class="collection-chip"
                      :class="activeCollectionId === null ? 'collection-chip-active' : ''"
                      @click="selectCollection(null)"
                    >
                      <FolderOpen class="w-3 h-3" />
                      <span>全部</span>
                      <span class="collection-chip-count">{{ store.mistakesTotal || store.mistakes.length }}</span>
                    </button>
                    <button
                      v-for="c in store.collections"
                      :key="c.id"
                      class="collection-chip"
                      :class="activeCollectionId === c.id ? 'collection-chip-active' : ''"
                      @click="selectCollection(c.id)"
                    >
                      <Tag class="w-3 h-3" />
                      <span>{{ c.name }}</span>
                      <span class="collection-chip-count">{{ c.unmastered_count }}/{{ c.count }}</span>
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5 shrink-0">
                    <n-button size="tiny" quaternary @click="openCreateCollection">
                      <Plus class="w-3 h-3 mr-0.5" />
                      新建
                    </n-button>
                    <n-button size="tiny" quaternary @click="openManageCollections">
                      <Settings class="w-3 h-3 mr-0.5" />
                      管理
                    </n-button>
                  </div>
                </div>

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

                <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
                  <div class="flex items-center gap-2 flex-wrap">
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
                    <n-select
                      v-model:value="mistakeFilter.mastered"
                      :options="masteredOptions"
                      size="small"
                      style="width: 110px"
                      @update:value="onMistakeFilterChange"
                    />
                    <n-input
                      v-model:value="mistakeFilter.q"
                      size="small"
                      placeholder="搜索题干/知识点..."
                      clearable
                      style="width: 220px"
                      @keyup.enter="onMistakeFilterChange"
                    >
                      <template #prefix>
                        <Search class="w-3.5 h-3.5 text-ink-3" />
                      </template>
                    </n-input>
                  </div>
                  <n-button type="primary" size="small" @click="mistakeAddShow = true">
                    <Plus class="w-3.5 h-3.5 mr-1" />
                    添加错题
                  </n-button>
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
                <div v-else class="space-y-3">
                  <div
                    v-for="m in store.mistakes"
                    :key="m.id"
                    class="mistake-card"
                    :class="[m.mastered ? 'mistake-card-mastered' : '', redoingIds.has(m.id) ? 'mistake-card-redoing' : '', selectedMistakeIds.has(m.id) ? 'mistake-card-selected' : '']"
                  >
                    <!-- 顶部:选择框 + 知识点/来源/时间 -->
                    <div class="flex items-center gap-1.5 flex-wrap mb-2">
                      <n-checkbox
                        :checked="selectedMistakeIds.has(m.id)"
                        size="small"
                        @update:checked="(v: boolean) => toggleSelect(m.id, v)"
                      />
                      <n-tag size="small" :bordered="false" type="info" v-if="m.knowledge_point_name">
                        {{ m.knowledge_point_name }}
                      </n-tag>
                      <n-tag size="small" :bordered="false" v-if="m.course_name">{{ m.course_name }}</n-tag>
                      <n-tag size="small" :bordered="false" :type="m.source === 'classroom' ? 'success' : 'default'">
                        {{ m.source === 'classroom' ? '课堂同步' : '手动' }}
                      </n-tag>
                      <!-- 所属错题集标签(在头部展示) -->
                      <n-tag
                        v-for="cid in (m.collection_ids || []).slice(0, 2)"
                        :key="cid"
                        size="small"
                        :bordered="false"
                        type="warning"
                      >
                        <Tag class="w-2.5 h-2.5 mr-0.5" />
                        {{ collectionNameById(cid) }}
                      </n-tag>
                      <n-tag
                        v-if="(m.collection_ids || []).length > 2"
                        size="small"
                        :bordered="false"
                      >
                        +{{ (m.collection_ids || []).length - 2 }}
                      </n-tag>
                      <span class="text-[11px] text-ink-3 ml-auto">
                        {{ formatDate(m.first_added_at) }}
                      </span>
                    </div>
                    <!-- 头部:知识点 + 来源 + 时间 -->
                    <div class="flex items-center gap-1.5 flex-wrap mb-2">
                      <n-tag size="small" :bordered="false" type="info" v-if="m.knowledge_point_name">
                        {{ m.knowledge_point_name }}
                      </n-tag>
                      <n-tag size="small" :bordered="false" v-if="m.course_name">{{ m.course_name }}</n-tag>
                      <n-tag size="small" :bordered="false" :type="m.source === 'classroom' ? 'success' : 'default'">
                        {{ m.source === 'classroom' ? '课堂同步' : '手动' }}
                      </n-tag>
                      <span class="text-[11px] text-ink-3 ml-auto">
                        {{ formatDate(m.first_added_at) }}
                      </span>
                    </div>

                    <!-- 题干 -->
                    <div class="text-[13px] text-ink-1 font-medium leading-relaxed mb-2 whitespace-pre-wrap">
                      {{ m.stem }}
                    </div>

                    <!-- 图片附件(始终可见) -->
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

                    <!-- 已掌握:默认直接展示答案(无需操作) -->
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
                        <!-- 单选：radio group -->
                        <template v-if="m.question_type === 'single' && m.options?.length">
                          <div class="text-[11.5px] text-ink-3">选择一个选项</div>
                          <NRadioGroup
                            v-model:value="redoAnswer[m.id]"
                            size="small"
                          >
                            <NSpace size="small" vertical>
                              <NRadio
                                v-for="(label, idx) in m.options"
                                :key="idx"
                                :value="optionValue(label, idx)"
                              >
                                {{ label }}
                              </NRadio>
                            </NSpace>
                          </NRadioGroup>
                        </template>
                        <!-- 多选：checkbox group -->
                        <template v-else-if="m.question_type === 'multiple' && m.options?.length">
                          <div class="text-[11.5px] text-ink-3">可多选</div>
                          <NCheckboxGroup
                            :value="redoMultiAnswer[m.id] || []"
                            @update:value="(vs) => onRedoMultiChange(m, vs)"
                          >
                            <NSpace size="small" vertical>
                              <NCheckbox
                                v-for="(label, idx) in m.options"
                                :key="idx"
                                :value="optionValue(label, idx)"
                              >
                                {{ label }}
                              </NCheckbox>
                            </NSpace>
                          </NCheckboxGroup>
                        </template>
                        <!-- 简答：textarea 兜底 -->
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
                      <div v-else class="space-y-1.5">
                        <div v-if="hasRedoAnswer(m)" class="mistake-meta">
                          <span class="text-ink-3">你刚写的</span>
                          <span :class="isRedoCorrect(m) ? 'text-success' : 'text-danger'">
                            {{ formatRedoAnswer(m) }}
                          </span>
                          <span v-if="isRedoCorrect(m)" class="text-success text-[11px]">✓ 答对</span>
                          <span v-else class="text-warning text-[11px]">✗ 还需巩固</span>
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
                          <n-button
                            v-else-if="!m.mastered"
                            size="small"
                            quaternary
                            type="primary"
                            @click="onConvertToCard(m)"
                          >
                            <Layers class="w-3 h-3 mr-1" />
                            转闪卡反复练
                          </n-button>
                          <n-button size="small" quaternary class="ml-auto" @click="closeRedo(m)">
                            关闭
                          </n-button>
                        </div>
                      </div>
                    </div>

                    <!-- 默认:隐藏答案,只显示"重新作答" + "偷看" 入口 -->
                    <div v-else class="reveal-hint">
                      <span class="text-[11.5px] text-ink-3">
                        {{ m.mastered ? '已掌握 — 仍可查看' : '答案已隐藏 — 先试着回忆,再看解析' }}
                      </span>
                      <n-button
                        v-if="!m.mastered"
                        size="tiny"
                        type="primary"
                        ghost
                        @click="openRedo(m)"
                      >
                        <PenLine class="w-3 h-3 mr-1" />
                        重新作答
                      </n-button>
                      <n-button size="tiny" quaternary @click="onPeek(m)">
                        <Eye class="w-3 h-3 mr-1" />
                        查看答案
                      </n-button>
                    </div>

                    <div v-if="m.tags && m.tags.length" class="flex gap-1 flex-wrap mt-2">
                      <n-tag
                        v-for="t in m.tags"
                        :key="t"
                        size="tiny"
                        :bordered="false"
                        type="default"
                      >
                        #{{ t }}
                      </n-tag>
                    </div>

                    <!-- 操作 -->
                    <div class="flex items-center gap-1.5 mt-3 pt-3 border-t border-line-subtle">
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
                <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
                  <div class="flex items-center gap-2 flex-wrap">
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
                      placeholder="搜索卡片..."
                      clearable
                      style="width: 220px"
                      @keyup.enter="onCardFilterChange"
                    >
                      <template #prefix>
                        <Search class="w-3.5 h-3.5 text-ink-3" />
                      </template>
                    </n-input>
                  </div>
                  <n-button size="small" @click="cardAddShow = true">
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
                <div v-else class="space-y-2.5">
                  <div
                    v-for="c in store.flashcards"
                    :key="c.id"
                    class="card-row"
                  >
                    <div class="flex items-center gap-1.5 flex-wrap mb-1.5">
                      <n-tag size="small" :bordered="false" type="info" v-if="c.knowledge_point_name">
                        {{ c.knowledge_point_name }}
                      </n-tag>
                      <n-tag size="small" :bordered="false" v-if="c.course_name">{{ c.course_name }}</n-tag>
                      <n-tag size="small" :bordered="false" :type="sourceTagType(c.source)">
                        {{ sourceLabel(c.source) }}
                      </n-tag>
                      <span class="text-[11px] text-ink-3 ml-auto">
                        {{ formatDate(c.created_at) }}
                      </span>
                    </div>
                    <div class="text-[13px] text-ink-1 font-medium leading-snug mb-1 line-clamp-2">
                      {{ c.front }}
                    </div>
                    <div class="text-[12px] text-ink-3 leading-snug line-clamp-2">
                      {{ c.back }}
                    </div>
                    <div class="flex items-center justify-between mt-2.5 pt-2.5 border-t border-line-subtle">
                      <div class="flex items-center gap-3 text-[11px] text-ink-3">
                        <span>
                          <Calendar class="w-3 h-3 inline -mt-0.5 mr-0.5" />
                          {{ c.sm2?.due_date || '—' }}
                        </span>
                        <span>EF {{ (c.sm2?.ease_factor ?? 2.5).toFixed(2) }}</span>
                        <span>重复 {{ c.sm2?.repetitions ?? 0 }} 次</span>
                      </div>
                      <div class="flex items-center gap-1">
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
          </n-tabs>
        </div>
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
          <n-button size="medium" type="primary" @click="onGrade(3)" class="grade-btn grade-btn-3">
            <span class="text-[11px] opacity-70">3</span>
            <span class="ml-1">良好</span>
          </n-button>
          <n-button size="medium" type="primary" @click="onGrade(5)" class="grade-btn grade-btn-5">
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
        <!-- 进度 + 上下文 -->
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

        <!-- 题干 -->
        <div class="batch-stem">
          {{ batchQueue[batchIndex].stem }}
        </div>

        <!-- 输入区 -->
        <div v-if="!batchRevealed" class="space-y-2">
          <template v-if="batchQueue[batchIndex].question_type === 'single' && batchQueue[batchIndex].options?.length">
            <div class="text-[11.5px] text-ink-3">选择一个选项</div>
            <NRadioGroup v-model:value="batchAnswer" size="medium">
              <NSpace vertical>
                <NRadio
                  v-for="(label, idx) in batchQueue[batchIndex].options"
                  :key="idx"
                  :value="optionValue(label, idx)"
                >
                  {{ label }}
                </NRadio>
              </NSpace>
            </NRadioGroup>
          </template>
          <template v-else-if="batchQueue[batchIndex].question_type === 'multiple' && batchQueue[batchIndex].options?.length">
            <div class="text-[11.5px] text-ink-3">可多选</div>
            <NCheckboxGroup
              :value="batchMultiAnswer"
              @update:value="(vs) => onBatchMultiChange(vs)"
            >
              <NSpace vertical>
                <NCheckbox
                  v-for="(label, idx) in batchQueue[batchIndex].options"
                  :key="idx"
                  :value="optionValue(label, idx)"
                >
                  {{ label }}
                </NCheckbox>
              </NSpace>
            </NCheckboxGroup>
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

        <!-- 答案揭晓 -->
        <div v-else class="space-y-2">
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
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton, NCheckbox, NCheckboxGroup, NImage, NImageGroup, NInput, NModal, NPopover, NPopselect, NRadio, NRadioGroup, NSelect, NSpace, NTabPane, NTabs, NTag,
  useDialog, useMessage,
} from 'naive-ui'
import {
  BookMarked, Calendar, Check, CheckCheck, CheckSquare, ChevronRight, Eye, FolderOpen,
  FolderPlus, Layers, Paperclip, PenLine, Pencil, Play, Plus, RefreshCw, RotateCw, Search, Send,
  Settings, Tag, Trash2,
} from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AddMistakeModal from '@/components/studyTools/AddMistakeModal.vue'
import AddFlashcardModal from '@/components/studyTools/AddFlashcardModal.vue'
import { useStudyToolsStore } from '@/stores/studyToolsStore'
import type { FlashcardItem, MistakeCollection, MistakeItem } from '@/api/studyTools'

const store = useStudyToolsStore()
const message = useMessage()
const dialog = useDialog()

type TabName = 'mistakes' | 'flashcards'
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
// 单题内联重做:redoingIds 记录正在作答的卡片 id,redoAnswer 记录每张卡的输入,redoRevealed 记录是否已揭晓
// 多选题用 redoMultiAnswer 记字母数组;显示/判等时拼成与 correct_answer 一致的 'A / C' 字符串
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

// ─── 错题按题型分支工具 ───
const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

function optionValue(label: string, idx: number): string {
  // 优先提取 label 文本开头的字母标号（"A. xxx" / "A、xxx" / "A xxx" / "(A) xxx"）
  const m = String(label || '').trim().match(/^\(?([A-H])[\.、\s)]/)
  if (m) return m[1]
  return OPTION_LETTERS[idx] || String(idx)
}

function onRedoMultiChange(m: MistakeItem, vs: Array<string | number>) {
  const arr = vs.map(String).sort()
  redoMultiAnswer[m.id] = arr
  redoAnswer[m.id] = arr.join(' / ')
}

function onBatchMultiChange(vs: Array<string | number>) {
  const arr = vs.map(String).sort()
  batchMultiAnswer.value = arr
  batchAnswer.value = arr.join(' / ')
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
    // 没有 due 时,自动转入"复习全部"模式(支持一天多次复习)
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
  // 全部完成时停留在弹窗
}

async function closeReview() {
  reviewing.value = false
  // 显式 await:确保 store 状态在用户切回主页面之前已与后端同步,
  // 避免"还有未复习的却不能点今日复习"的 UI 假死
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

// 偷看:不开作答面板,直接在默认区揭晓答案(轻量"看一眼"路径)
function onPeek(m: MistakeItem) {
  redoingIds.value = new Set([...redoingIds.value, m.id])
  redoAnswer[m.id] = ''
  redoRevealed[m.id] = true
}

// 简单判等:学生答案 vs 正确答案(容错:忽略首尾空白)
function isRedoCorrect(m: MistakeItem): boolean {
  const got = (redoAnswer[m.id] || '').trim()
  if (!got) return false
  const expected = String(m.correct_answer || '').trim()
  if (!expected) return false
  return got === expected
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
  return got === expected
}

function onBatchNext() {
  // 计入本轮数据
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
    // 全部完成:把 batchIndex 推到 queue 末尾,触发"完成"视图
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
  // 标记后这题不必再答,直接下一题
  // (为简化流程:不立即推进,而是让用户点"下一题"以保留控制感)
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
  // 同步刷新列表(可能有些题被标记掌握/转了卡)
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
    case 'manual': return '手动'
    case 'mistake': return '错题'
    case 'card': return '知识卡'
    case 'ai': return 'AI'
    case 'classroom': return '课堂'
    default: return s
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
/* ============ 顶部入口卡 ============ */
.stat-tile {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
  cursor: pointer;
}
.stat-tile:hover {
  border-color: rgb(var(--line-strong-rgb));
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}
.stat-tile-active {
  border-color: rgb(var(--hue-study-rgb) / 0.5);
  box-shadow: 0 0 0 3px rgb(var(--hue-study-rgb) / 0.1);
}
.stat-tile-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ============ 错题卡 ============ */
.mistake-card {
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 10px;
  padding: 12px 14px;
  transition: border-color 200ms var(--ease-out), background 200ms var(--ease-out);
}
.mistake-card:hover {
  border-color: rgb(var(--line-rgb));
}
.mistake-card-mastered {
  opacity: 0.7;
}
.mistake-card-mastered .text-ink-1 {
  text-decoration: line-through;
  text-decoration-color: rgb(var(--ink-4-rgb));
}
.mistake-card-redoing {
  border-color: rgb(var(--hue-study-rgb) / 0.45);
  box-shadow: 0 0 0 3px rgb(var(--hue-study-rgb) / 0.08);
  background: rgb(var(--bg-surface-rgb));
}
.mistake-card-selected {
  border-color: rgb(var(--hue-study-rgb) / 0.55);
  background: rgb(var(--hue-study-rgb) / 0.04);
}

/* ============ 错题集筛选条 ============ */
.collection-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 10px;
  flex-wrap: wrap;
}
.collection-bar-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: thin;
}
.collection-bar-tags::-webkit-scrollbar {
  height: 4px;
}
.collection-bar-tags::-webkit-scrollbar-thumb {
  background: rgb(var(--line-rgb));
  border-radius: 2px;
}
.collection-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 999px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12.5px;
  cursor: pointer;
  transition: all 160ms var(--ease-out);
  white-space: nowrap;
  flex-shrink: 0;
}
.collection-chip:hover {
  border-color: rgb(var(--hue-study-rgb) / 0.5);
  color: rgb(var(--ink-1-rgb));
}
.collection-chip-active {
  background: rgb(var(--hue-study-rgb) / 0.1);
  border-color: rgb(var(--hue-study-rgb) / 0.55);
  color: rgb(var(--hue-study-rgb));
  font-weight: 500;
}
.collection-chip-count {
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
  font-variant-numeric: tabular-nums;
}
.collection-chip-active .collection-chip-count {
  background: rgb(var(--hue-study-rgb) / 0.18);
  color: rgb(var(--hue-study-rgb));
}

/* ============ 批量操作条 ============ */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: rgb(var(--hue-study-rgb) / 0.06);
  border: 1px solid rgb(var(--hue-study-rgb) / 0.3);
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
  border-color: rgb(var(--hue-study-rgb) / 0.45);
  background: rgb(var(--hue-study-rgb) / 0.04);
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
  border-color: rgb(var(--hue-study-rgb) / 0.5);
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
  color: rgb(var(--hue-study-rgb));
  transition: background 120ms var(--ease-out);
}
.attachment-add-row:hover {
  background: rgb(var(--hue-study-rgb) / 0.08);
}
.attachment-add-row input:disabled {
  cursor: not-allowed;
}

/* 默认态:答案已隐藏的提示行 */
.reveal-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  margin-bottom: 8px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px dashed rgb(var(--line-rgb));
  border-radius: 8px;
}
.reveal-hint > span:first-child {
  flex: 1;
  min-width: 0;
}

/* 内联重做输入区 */
.redo-panel {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
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
  border-left: 3px solid rgb(var(--hue-study-rgb));
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

/* ============ 闪卡行 ============ */
.card-row {
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 10px;
  padding: 11px 14px;
  transition: border-color 200ms var(--ease-out);
}
.card-row:hover {
  border-color: rgb(var(--line-rgb));
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
  background: rgb(var(--accent-soft-rgb) / 0.4);
  border-color: rgb(var(--accent-rgb) / 0.25);
}

.grade-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 4px;
  height: auto;
}
.grade-btn-0 { color: rgb(var(--danger-rgb)); }
.grade-btn-1 { color: rgb(var(--warning-rgb)); }
.grade-btn-3 { color: rgb(var(--accent-rgb)); }
.grade-btn-5 { color: rgb(var(--success-rgb)); }

/* ============ Tabs 微调 ============ */
.study-tabs :deep(.n-tabs-tab) {
  font-size: 13px;
}
.study-tabs :deep(.n-tabs-tab--active) {
  color: rgb(var(--hue-study-rgb));
}
.study-tabs :deep(.n-tabs-bar) {
  background-color: rgb(var(--hue-study-rgb)) !important;
}

/* ============ Mobile ============ */
@media (max-width: 767px) {
  .p-6 {
    padding: 14px;
  }
  .stat-tile {
    padding: 14px;
  }
  .flash-face {
    padding: 20px 16px;
  }
}
</style>
