<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: 540px; max-width: 92vw"
    :mask-closable="false"
    title="新建闪卡"
    :bordered="false"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div class="space-y-4">
      <div>
        <label class="form-label">正面 <span class="text-danger">*</span></label>
        <n-input
          v-model:value="form.front"
          type="textarea"
          placeholder="问题/术语/概念"
          :autosize="{ minRows: 2, maxRows: 5 }"
        />
      </div>
      <div>
        <label class="form-label">背面 <span class="text-danger">*</span></label>
        <n-input
          v-model:value="form.back"
          type="textarea"
          placeholder="答案/解释/记忆点"
          :autosize="{ minRows: 3, maxRows: 8 }"
        />
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
      <div v-if="errorMsg" class="text-[12.5px] text-danger">{{ errorMsg }}</div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <n-button quaternary @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="onSubmit">创建</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { NModal, NInput, NButton } from 'naive-ui'
import type { FlashcardItem } from '@/api/studyTools'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'submit', payload: Partial<FlashcardItem>): Promise<void> | void
}>()

const form = reactive({
  front: '',
  back: '',
  course_name: '',
  knowledge_point_name: '',
})
const submitting = ref(false)
const errorMsg = ref('')

watch(
  () => props.show,
  (v) => {
    if (v) {
      Object.assign(form, { front: '', back: '', course_name: '', knowledge_point_name: '' })
      errorMsg.value = ''
    }
  },
)

async function onSubmit() {
  errorMsg.value = ''
  if (!form.front.trim() || !form.back.trim()) {
    errorMsg.value = '正面和背面都不能为空'
    return
  }
  submitting.value = true
  try {
    const kp = form.knowledge_point_name.trim()
    const course = form.course_name.trim() || (kp ? '自学' : '')
    await emit('submit', {
      front: form.front.trim(),
      back: form.back.trim(),
      course_name: course,
      course_id: course ? `c_${slugify(course)}` : '',
      knowledge_point_name: kp,
      knowledge_point_id: kp ? `kp_${slugify(kp)}` : null,
      source: 'manual',
    })
    emit('update:show', false)
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '创建失败'
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
</style>
