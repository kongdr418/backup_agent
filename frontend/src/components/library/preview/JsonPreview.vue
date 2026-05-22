<template>
  <div class="json-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>加载中...</span>
    </div>
    <div v-else-if="error" class="error-state">{{ error }}</div>
    <div v-else class="json-tree">
      <JsonNode :data="parsed" :depth="0" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, defineComponent, h, type VNode } from 'vue'
import { readFile } from '@/api/files'

const props = defineProps<{ path: string }>()

const parsed = ref<unknown>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.path) return
  loading.value = true
  error.value = ''
  try {
    const { content } = await readFile(props.path)
    parsed.value = JSON.parse(content)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'JSON 解析失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.path, load)

const isObject = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v)
const isArray = (v: unknown): v is unknown[] => Array.isArray(v)
const isPrimitive = (v: unknown): boolean =>
  v === null || typeof v !== 'object'

const JsonNode = defineComponent({
  name: 'JsonNode',
  props: {
    data: { type: null as unknown as () => unknown, required: true },
    depth: { type: Number, default: 0 },
    label: { type: String, default: '' },
  },
  setup(props) {
    const collapsed = ref(props.depth > 2)

    function toggle() {
      collapsed.value = !collapsed.value
    }

    return (): VNode => {
      const { data, depth, label } = props

      if (isPrimitive(data)) {
        const display = data === null ? 'null' : JSON.stringify(data)
        const cls = typeof data === 'string' ? 'json-string'
          : typeof data === 'number' ? 'json-number'
          : typeof data === 'boolean' ? 'json-boolean'
          : 'json-null'
        return h('div', { class: 'json-leaf' }, [
          label ? h('span', { class: 'json-key' }, `"${label}": `) : null,
          h('span', { class: cls }, display),
        ])
      }

      const entries = isObject(data)
        ? Object.entries(data)
        : isArray(data)
        ? data.map((v, i) => [String(i), v] as const)
        : []

      const bracketL = isArray(data) ? '[' : '{'
      const bracketR = isArray(data) ? ']' : '}'
      const count = entries.length

      if (collapsed.value) {
        return h('div', { class: 'json-leaf' }, [
          label ? h('span', { class: 'json-key' }, `"${label}": `) : null,
          h('span', { class: 'json-bracket clickable', onClick: toggle }, `${bracketL}...${bracketR}`),
          h('span', { class: 'json-count' }, ` ${count} items`),
        ])
      }

      return h('div', { class: 'json-node' }, [
        h('div', { class: 'json-leaf' }, [
          label ? h('span', { class: 'json-key' }, `"${label}": `) : null,
          h('span', { class: 'json-bracket clickable', onClick: toggle }, bracketL),
        ]),
        ...entries.map(([k, v]) =>
          h('div', { style: { paddingLeft: '16px' } }, [
            h(JsonNode, { data: v, depth: depth + 1, label: isObject(data) ? k : '' }),
          ])
        ),
        h('div', { class: 'json-leaf' }, [
          h('span', { class: 'json-bracket' }, bracketR),
        ]),
      ])
    }
  },
})
</script>

<style scoped>
.json-preview {
  width: 100%;
  min-height: 100px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.loading-dots { display: flex; gap: 4px; }
.loading-dots span {
  width: 5px; height: 5px; border-radius: 50%;
  background: rgb(var(--ink-4-rgb));
  animation: dot-bounce 1.4s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.16s; }
.loading-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
  40% { transform: translateY(-3px); opacity: 1; }
}

.error-state {
  padding: 20px;
  text-align: center;
  color: rgb(var(--danger-rgb));
  font-size: 13px;
}

.json-tree {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgb(var(--bg-inset-rgb));
  border: 1px solid rgb(var(--line-rgb));
  overflow-x: auto;
  max-height: 500px;
  overflow-y: auto;
}

.json-leaf {
  white-space: nowrap;
}

.json-key {
  color: rgb(var(--accent-rgb));
}

.json-string {
  color: #059669;
}

.json-number {
  color: #d97706;
}

.json-boolean {
  color: #7c3aed;
}

.json-null {
  color: rgb(var(--ink-4-rgb));
  font-style: italic;
}

.json-bracket {
  color: rgb(var(--ink-3-rgb));
  font-weight: 600;
}

.json-bracket.clickable {
  cursor: pointer;
  user-select: none;
}
.json-bracket.clickable:hover {
  color: rgb(var(--accent-rgb));
}

.json-count {
  color: rgb(var(--ink-4-rgb));
  font-size: 11px;
  font-style: italic;
}
</style>