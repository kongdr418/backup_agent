<template>
  <div 
    class="editable-element-text" 
    :class="{ 'lock': elementInfo.lock }"
    :style="{
      top: elementInfo.top + 'px',
      left: elementInfo.left + 'px',
      width: elementInfo.width + 'px',
      height: elementInfo.height + 'px',
    }"
  >
    <div
      class="rotate-wrapper"
      :style="{ transform: `rotate(${elementInfo.rotate}deg)` }"
    >
      <div 
        class="element-content"
        ref="elementRef"
        :style="{
          width: elementInfo.vertical ? 'auto' : elementInfo.width + 'px',
          height: elementInfo.vertical ? elementInfo.height + 'px' : 'auto',
          backgroundColor: elementInfo.fill,
          opacity: elementInfo.opacity,
          textShadow: shadowStyle,
          lineHeight: elementInfo.lineHeight,
          letterSpacing: (elementInfo.wordSpace || 0) + 'px',
          color: elementInfo.defaultColor,
          fontFamily: elementInfo.defaultFontName,
          writingMode: elementInfo.vertical ? 'vertical-rl' : 'horizontal-tb',
          padding: `${inset[0]}px ${inset[1]}px ${inset[2]}px ${inset[3]}px`,
          '--paragraphSpace': `${elementInfo.paragraphSpace === undefined ? 5 : elementInfo.paragraphSpace}px`,
        }"
        v-contextmenu="contextmenus"
        @mousedown="$event => handleSelectElement($event)"
        @touchstart="$event => handleSelectElement($event)"
        @dblclick.stop="focusEditor"
      >
        <ElementOutline
          :width="elementInfo.width"
          :height="elementInfo.height"
          :outline="elementInfo.outline"
        />
        <ProsemirrorEditor
          ref="prosemirrorEditorRef"
          class="text"
          :elementId="elementInfo.id"
          :defaultColor="elementInfo.defaultColor"
          :defaultFontName="elementInfo.defaultFontName"
          :editable="!elementInfo.lock"
          :value="elementInfo.content"
          @update="({ value, ignore }) => updateContent(value, ignore)"
          @mousedown="$event => handleSelectElement($event)"
          @dblclick.stop="focusEditor"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch, useTemplateRef } from 'vue'
import { storeToRefs } from 'pinia'
import { debounce } from 'lodash'
import { useMainStore, useSlidesStore } from '@pptist/store'
import type { PPTTextElement } from '@pptist/types/slides'
import type { ContextmenuItem } from '@pptist/components/Contextmenu/types'
import useElementShadow from '@pptist/views/components/element/hooks/useElementShadow'
import useHistorySnapshot from '@pptist/hooks/useHistorySnapshot'

import ElementOutline from '@pptist/views/components/element/ElementOutline.vue'
import ProsemirrorEditor from '@pptist/views/components/element/ProsemirrorEditor.vue'

const props = defineProps<{
  elementInfo: PPTTextElement
  selectElement: (e: MouseEvent | TouchEvent, element: PPTTextElement, canMove?: boolean) => void
  contextmenus: () => ContextmenuItem[] | null
}>()

const mainStore = useMainStore()
const slidesStore = useSlidesStore()
const { handleElementId, isScaling } = storeToRefs(mainStore)

const { addHistorySnapshot } = useHistorySnapshot()

const elementRef = useTemplateRef<HTMLElement>('elementRef')
const prosemirrorEditorRef = useTemplateRef<InstanceType<typeof ProsemirrorEditor>>('prosemirrorEditorRef')

const shadow = computed(() => props.elementInfo.shadow)
const { shadowStyle } = useElementShadow(shadow)
const inset = computed(() => props.elementInfo.inset || [10, 10, 10, 10])

const handleSelectElement = (e: MouseEvent | TouchEvent, canMove = true) => {
  if (props.elementInfo.lock) return
  e.stopPropagation()

  props.selectElement(e, props.elementInfo, canMove)
}

const focusEditor = () => {
  if (props.elementInfo.lock) return
  prosemirrorEditorRef.value?.focus()
}

// 监听文本元素的尺寸变化，当高度变化时，更新高度到vuex
// 如果高度变化时正处在缩放操作中，则等待缩放操作结束后再更新
const realHeightCache = ref(-1)
const realWidthCache = ref(-1)

watch(isScaling, () => {
  if (handleElementId.value !== props.elementInfo.id) return

  if (!isScaling.value) {
    if (!props.elementInfo.vertical && realHeightCache.value !== -1) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { height: realHeightCache.value },
      })
      realHeightCache.value = -1
    }
    if (props.elementInfo.vertical && realWidthCache.value !== -1) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { width: realWidthCache.value },
      })
      realWidthCache.value = -1
    }
  }
})

watch(() => props.elementInfo.inset, () => {
  nextTick(() => {
    if (!elementRef.value) return

    if (!props.elementInfo.vertical && props.elementInfo.height !== elementRef.value.offsetHeight) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { height: elementRef.value.offsetHeight },
      })
    }
    if (props.elementInfo.vertical && props.elementInfo.width !== elementRef.value.offsetWidth) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { width: elementRef.value.offsetWidth },
      })
    }
  })
})

const updateTextElementHeight = (entries: ResizeObserverEntry[]) => {
  const contentRect = entries[0].contentRect
  if (!elementRef.value) return

  const realHeight = contentRect.height + inset.value[0] + inset.value[2]
  const realWidth = contentRect.width + inset.value[1] + inset.value[3]

  if (!props.elementInfo.vertical && props.elementInfo.height !== realHeight) {
    if (!isScaling.value) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { height: realHeight },
      })
    }
    else realHeightCache.value = realHeight
  }
  if (props.elementInfo.vertical && props.elementInfo.width !== realWidth) {
    if (!isScaling.value) {
      slidesStore.updateElement({
        id: props.elementInfo.id,
        props: { width: realWidth },
      })
    }
    else realWidthCache.value = realWidth
  }
}
const resizeObserver = new ResizeObserver(updateTextElementHeight)

onMounted(() => {
  if (elementRef.value) resizeObserver.observe(elementRef.value)
})
onUnmounted(() => {
  if (elementRef.value) resizeObserver.unobserve(elementRef.value)
})

const updateContent = (content: string, ignore = false) => {
  slidesStore.updateElement({
    id: props.elementInfo.id,
    props: { content },
  })
  
  if (!ignore) addHistorySnapshot()
}

const checkEmptyText = debounce(function() {
  const pureText = props.elementInfo.content.replace(/<[^>]+>/g, '')
  if (!pureText) slidesStore.deleteElement(props.elementInfo.id)
}, 300, { trailing: true })

const isHandleElement = computed(() => handleElementId.value === props.elementInfo.id)
watch(isHandleElement, () => {
  if (!isHandleElement.value) checkEmptyText()
})
</script>

<style lang="scss" scoped>
.editable-element-text {
  position: absolute;

  &.lock .element-content {
    cursor: default;
  }
}
.rotate-wrapper {
  width: 100%;
  height: 100%;
}
.element-content {
  position: relative;
  line-height: 1.5;
  word-break: break-word;
  font-family: $textElementFont;
  cursor: move;

  .text {
    position: relative;
  }

  ::v-deep(a) {
    cursor: text;
  }
}
</style>
