<template>
  <div class="mindmap-scene">
    <div v-if="!markdown" class="mindmap-empty">本节知识结构暂未生成</div>
    <div v-else ref="containerEl" class="mindmap-container">
      <svg
        ref="svgEl"
        class="mindmap-svg"
        role="img"
        aria-label="知识结构图"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const props = defineProps<{
  /** markmap 格式的 Markdown 大纲 */
  markdown: string
  title?: string
}>()

const containerEl = ref<HTMLDivElement | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)
let mm: Markmap | null = null
let transformer: Transformer | null = null
let resizeObserver: ResizeObserver | null = null
let pendingFitRaf: number | null = null

function getTransformer(): Transformer {
  if (!transformer) transformer = new Transformer()
  return transformer
}

function fitToContainer() {
  if (!mm) return
  void mm.fit()
}

function scheduleFit() {
  if (pendingFitRaf !== null) cancelAnimationFrame(pendingFitRaf)
  pendingFitRaf = requestAnimationFrame(() => {
    pendingFitRaf = null
    fitToContainer()
  })
}

async function render() {
  if (!svgEl.value) return
  const md = (props.markdown || '').trim()
  if (!md) {
    destroy()
    return
  }
  try {
    await nextTick()

    const { root } = getTransformer().transform(md)
    if (mm) {
      await mm.setData(root)
      scheduleFit()
    } else {
      // 关键：autoFit 关掉，由我们手动 fit() 控尺寸。
      // 原因：markmap 内部 autoFit 在 create 时读 SVG 尺寸，
      // 但这时 CSS 还没生效（容器高度依赖 flex 父级），
      // 读到的尺寸是默认值（300x150），导致 scale ~0.38 看起来很小。
      // 我们的策略：先 fit()（markmap 读真实尺寸），
      // 然后 ResizeObserver 持续兜底 fit。
      mm = Markmap.create(
        svgEl.value,
        {
          autoFit: false,
          duration: 0,
          paddingX: 16,
          zoom: true,
          pan: true,
        },
        root,
      )
      scheduleFit()
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn('[MindmapScene] 渲染失败：', err)
    destroy()
  }
}

function destroy() {
  if (pendingFitRaf !== null) {
    cancelAnimationFrame(pendingFitRaf)
    pendingFitRaf = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (mm) {
    try {
      mm.destroy()
    } catch {
      /* ignore */
    }
    mm = null
  }
  if (svgEl.value) {
    svgEl.value.innerHTML = ''
  }
}

function setupResizeObserver() {
  if (!containerEl.value) return
  resizeObserver = new ResizeObserver(() => {
    scheduleFit()
  })
  resizeObserver.observe(containerEl.value)
}

onMounted(() => {
  setupResizeObserver()
  void render()
})

watch(() => props.markdown, () => {
  void render()
})

onBeforeUnmount(destroy)
</script>

<style scoped>
.mindmap-scene {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.mindmap-container {
  /* 16:9 与 slide 一致；高度由宽度 + aspect-ratio 决定 */
  width: 100%;
  max-width: 880px;
  max-height: 460px;
  margin: 0 auto;
  aspect-ratio: 16 / 9;
  background: var(--bg-subtle, #fafaf9);
  border-radius: 12px;
  border: 1px solid var(--line, #e7e5e4);
  overflow: hidden;
  display: block;
  flex: 0 0 auto;  /* 不让 flex 父级把它撑高 */
}
.mindmap-svg {
  display: block;
  width: 100%;
  height: 100%;
}
.mindmap-empty {
  flex: 1;
  display: grid;
  place-items: center;
  color: var(--ink-3, #78716c);
  font-size: 14px;
  background: var(--bg-subtle, #fafaf9);
  border-radius: 12px;
  border: 1px dashed var(--line, #e7e5e4);
  min-height: 240px;
}
</style>
