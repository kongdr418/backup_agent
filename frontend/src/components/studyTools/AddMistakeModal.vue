<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: 620px; max-width: 92vw"
    :mask-closable="false"
    :title="title"
    :bordered="false"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div class="space-y-4">
      <div>
        <label class="form-label">题干 <span class="text-danger">*</span></label>
        <n-input
          v-model:value="form.stem"
          type="textarea"
          placeholder="复制粘贴题目或自己描述..."
          :autosize="{ minRows: 3, maxRows: 8 }"
        />
      </div>

      <!-- 图片附件(可空) -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="form-label !mb-0">
            图片附件 <span class="text-ink-4 text-[12px]">(可选,最多 9 张,单张 ≤ 5 MB)</span>
          </label>
          <span v-if="files.length" class="text-[11.5px] text-ink-3">
            已选 {{ files.length }} / 9
          </span>
        </div>
        <div
          v-if="files.length < 9"
          class="mistake-upload-zone"
          :class="{ 'is-dragover': isDragover }"
          @click="triggerPicker"
          @dragover.prevent="isDragover = true"
          @dragleave.prevent="isDragover = false"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileInputRef"
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp,image/bmp"
            multiple
            class="hidden"
            @change="onPick"
          />
          <div class="upload-placeholder">
            <ImagePlus class="upload-icon" :size="22" />
            <span class="upload-text">点击或拖拽图片到此处</span>
            <span class="upload-hint">支持 png / jpg / gif / webp / bmp</span>
          </div>
        </div>
        <div v-if="files.length" class="mt-2.5 grid grid-cols-3 sm:grid-cols-4 gap-2">
          <div
            v-for="(f, i) in files"
            :key="i"
            class="thumb-card"
          >
            <img :src="previewUrls[i]" :alt="f.name" class="thumb-img" />
            <button
              type="button"
              class="thumb-remove"
              title="移除"
              @click.stop="removeAt(i)"
            >
              <X :size="12" />
            </button>
            <div class="thumb-name" :title="f.name">{{ truncate(f.name, 14) }}</div>
          </div>
        </div>
        <div v-if="fileError" class="text-[12px] text-danger mt-1.5">{{ fileError }}</div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="form-label">课程</label>
          <n-input v-model:value="form.course_name" placeholder="如:高三数学" />
        </div>
        <div>
          <label class="form-label">知识点</label>
          <n-input v-model:value="form.knowledge_point_name" placeholder="如:导数定义" />
        </div>
      </div>

      <div>
        <label class="form-label">正确答案 <span class="text-danger">*</span></label>
        <n-input
          v-model:value="form.correct_answer"
          type="textarea"
          placeholder="正确答案,可包含推导过程"
          :autosize="{ minRows: 2, maxRows: 5 }"
        />
      </div>

      <div>
        <label class="form-label">我的错误答案 <span class="text-ink-4 text-[12px]">(可选)</span></label>
        <n-input
          v-model:value="form.user_answer"
          type="textarea"
          placeholder="记录当时错在哪里"
          :autosize="{ minRows: 1, maxRows: 4 }"
        />
      </div>

      <div>
        <label class="form-label">解析 <span class="text-ink-4 text-[12px]">(可选)</span></label>
        <n-input
          v-model:value="form.analysis"
          type="textarea"
          placeholder="正确思路与陷阱说明"
          :autosize="{ minRows: 2, maxRows: 6 }"
        />
      </div>

      <div>
        <label class="form-label">标签 <span class="text-ink-4 text-[12px]">(逗号分隔)</span></label>
        <n-input v-model:value="tagsRaw" placeholder="如:易错,概念混淆,计算错误" />
      </div>

      <div v-if="errorMsg" class="text-[12.5px] text-danger">{{ errorMsg }}</div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <n-button quaternary @click="onCancel">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="onSubmit">添加到错题本</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch, onBeforeUnmount } from 'vue'
import { NModal, NInput, NButton } from 'naive-ui'
import { ImagePlus, X } from 'lucide-vue-next'
import type { MistakeItem } from '@/api/studyTools'

const props = defineProps<{ show: boolean; title?: string }>()
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'submit', payload: Partial<MistakeItem>, files: File[]): Promise<void> | void
}>()

const title = props.title || '添加错题'

const form = reactive({
  stem: '',
  course_name: '',
  knowledge_point_name: '',
  correct_answer: '',
  user_answer: '',
  analysis: '',
})

const tagsRaw = ref('')
const submitting = ref(false)
const errorMsg = ref('')

const MAX_FILES = 9
const MAX_FILE_SIZE = 5 * 1024 * 1024
const ACCEPTED = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp']
const ACCEPTED_EXTS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']

const files = ref<File[]>([])
const previewUrls = ref<string[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const isDragover = ref(false)
const fileError = ref('')

function clearPreviews() {
  for (const u of previewUrls.value) URL.revokeObjectURL(u)
  previewUrls.value = []
  files.value = []
}

function triggerPicker() {
  fileInputRef.value?.click()
}

function makePreview(file: File): string | null {
  try {
    return URL.createObjectURL(file)
  } catch {
    return null
  }
}

function filterAndAppend(rawList: FileList | File[]) {
  fileError.value = ''
  const arr = Array.from(rawList)
  for (const f of arr) {
    if (files.value.length >= MAX_FILES) {
      fileError.value = `最多上传 ${MAX_FILES} 张图片`
      break
    }
    if (!f || !f.name) continue
    const ext = f.name.includes('.') ? f.name.split('.').pop()!.toLowerCase() : ''
    const okExt = ACCEPTED_EXTS.includes(ext)
    const okMime = !f.type || ACCEPTED.includes(f.type)
    if (!okExt || !okMime) {
      fileError.value = `不支持的文件类型: ${f.name}`
      continue
    }
    if (f.size > MAX_FILE_SIZE) {
      fileError.value = `单张图片不能超过 5MB: ${f.name}`
      continue
    }
    files.value.push(f)
    const url = makePreview(f)
    if (url) previewUrls.value.push(url)
  }
}

function onPick(ev: Event) {
  const target = ev.target as HTMLInputElement
  if (target.files && target.files.length) {
    filterAndAppend(target.files)
    target.value = '' // 允许重复选同一文件
  }
}

function onDrop(ev: DragEvent) {
  isDragover.value = false
  const dt = ev.dataTransfer
  if (!dt || !dt.files || !dt.files.length) return
  filterAndAppend(dt.files)
}

function removeAt(idx: number) {
  const url = previewUrls.value[idx]
  if (url) URL.revokeObjectURL(url)
  files.value.splice(idx, 1)
  previewUrls.value.splice(idx, 1)
}

function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      Object.assign(form, {
        stem: '',
        course_name: '',
        knowledge_point_name: '',
        correct_answer: '',
        user_answer: '',
        analysis: '',
      })
      tagsRaw.value = ''
      errorMsg.value = ''
      fileError.value = ''
    } else {
      clearPreviews()
    }
  },
)

onBeforeUnmount(() => {
  clearPreviews()
})

function onCancel() {
  emit('update:show', false)
}

async function onSubmit() {
  errorMsg.value = ''
  if (!form.stem.trim()) {
    errorMsg.value = '题干不能为空'
    return
  }
  if (!form.correct_answer.trim()) {
    errorMsg.value = '正确答案不能为空'
    return
  }
  submitting.value = true
  try {
    const tags = tagsRaw.value
      .split(/[,,、]/)
      .map((t) => t.trim())
      .filter(Boolean)
    const kp = form.knowledge_point_name.trim()
    const course = form.course_name.trim() || (kp ? '自学' : '')
    const course_id = course ? `c_${slugify(course)}` : ''
    const kp_id = kp ? `kp_${slugify(kp)}` : null
    await emit(
      'submit',
      {
        stem: form.stem.trim(),
        correct_answer: form.correct_answer.trim(),
        user_answer: form.user_answer.trim() || null,
        analysis: form.analysis.trim(),
        course_name: course,
        course_id,
        knowledge_point_name: kp,
        knowledge_point_id: kp_id,
        tags,
        source: 'manual',
      },
      files.value,
    )
    emit('update:show', false)
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    submitting.value = false
  }
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[\s　]+/g, '_')
    .replace(/[^a-z0-9_一-龥-]/g, '')
    .slice(0, 64) || `x${Date.now().toString(36)}`
}
</script>

<style scoped>
.form-label {
  display: block;
  font-size: 12.5px;
  color: var(--ink-secondary);
  margin-bottom: 6px;
  font-weight: 500;
}
.mistake-upload-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 4px;
  padding: 18px 12px;
  border: 1px dashed rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-subtle-rgb));
  cursor: pointer;
  transition: border-color 160ms var(--ease-out), background 160ms var(--ease-out);
}
.mistake-upload-zone:hover,
.mistake-upload-zone.is-dragover {
  border-color: rgb(var(--hue-study-rgb) / 0.6);
  background: rgb(var(--hue-study-rgb) / 0.05);
}
.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
  pointer-events: none;
}
.upload-icon {
  color: rgb(var(--ink-3-rgb));
  margin-bottom: 2px;
}
.upload-text {
  font-size: 12.5px;
  color: rgb(var(--ink-2-rgb));
}
.upload-hint {
  font-size: 11px;
  color: rgb(var(--ink-3-rgb));
}
.thumb-card {
  position: relative;
  border: 1px solid rgb(var(--line-subtle-rgb));
  border-radius: 6px;
  overflow: hidden;
  background: rgb(var(--bg-subtle-rgb));
  aspect-ratio: 1 / 1;
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb-remove {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.thumb-remove:hover {
  background: rgba(220, 38, 38, 0.85);
}
.thumb-name {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 2px 6px;
  font-size: 10.5px;
  color: #fff;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0));
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
