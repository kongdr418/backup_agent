<template>
  <div class="carousel-wrap">
    <!-- Main viewer -->
    <div class="carousel-viewer">
      <div
        v-if="currentSlide"
        class="svg-stage"
        v-html="currentSlide.svg"
      />
      <div v-else class="text-center text-ink-3 text-[13px] px-6 py-12">
        <ImagePlay class="w-8 h-8 mx-auto mb-2 text-ink-4" />
        SVG 预览将在生成时实时显示
      </div>
    </div>

    <!-- Bottom: thumbnails + nav -->
    <div v-if="slides.length > 0" class="carousel-bottom">
      <!-- Thumbnails -->
      <div v-if="slides.length > 1" class="flex gap-1.5 overflow-x-auto pb-1.5">
        <button
          v-for="(s, i) in slides"
          :key="s.page"
          class="thumb-btn"
          :class="i === activeIdx ? 'is-active' : ''"
          @click="$emit('select', i)"
        >
          <div
            class="w-full h-full [&_svg]:w-full [&_svg]:h-full"
            v-html="s.svg"
          />
          <span class="thumb-no">{{ s.page }}</span>
        </button>
      </div>

      <!-- Nav -->
      <div v-if="slides.length > 1" class="flex items-center justify-between">
        <span class="text-[11px] text-ink-4 tabular-nums">{{ activeIdx + 1 }} / {{ slides.length }}</span>
        <div class="flex gap-1">
          <button
            class="nav-btn"
            :disabled="activeIdx === 0"
            @click="$emit('select', Math.max(0, activeIdx - 1))"
          >
            <ChevronLeft class="w-3.5 h-3.5" />
          </button>
          <button
            class="nav-btn"
            :disabled="activeIdx === slides.length - 1"
            @click="$emit('select', Math.min(slides.length - 1, activeIdx + 1))"
          >
            <ChevronRight class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, ImagePlay } from 'lucide-vue-next'
import type { PptSlide } from '@/types'

const props = defineProps<{
  slides: PptSlide[]
  activeIdx: number
}>()

defineEmits<{ select: [idx: number] }>()

const currentSlide = computed(() => props.slides[props.activeIdx] || null)
</script>

<style scoped>
.carousel-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.carousel-viewer {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.carousel-bottom {
  flex-shrink: 0;
  padding: 6px 4px 4px;
}

/* SVG container */
.svg-stage {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
:deep(.svg-stage svg) {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  border-radius: 6px;
  box-shadow: 0 2px 12px rgb(0 0 0 / 0.08);
}

/* Thumbnail */
.thumb-btn {
  position: relative;
  flex-shrink: 0;
  width: 72px;
  height: 44px;
  border-radius: 6px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  overflow: hidden;
  cursor: pointer;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}
.thumb-btn:hover {
  border-color: rgb(var(--ink-4-rgb));
}
.thumb-btn.is-active {
  border-color: rgb(var(--ink-1-rgb));
  box-shadow: 0 0 0 2px rgb(var(--ink-2-rgb) / 0.12);
}
.thumb-no {
  position: absolute;
  bottom: 1px;
  right: 3px;
  font-size: 9px;
  color: rgb(var(--ink-4-rgb));
  background: rgb(var(--bg-surface-rgb) / 0.8);
  padding: 0 3px;
  border-radius: 3px;
  line-height: 1.4;
}

/* Nav buttons */
.nav-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  cursor: pointer;
  transition: all 150ms ease;
}
.nav-btn:hover:not(:disabled) {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}
.nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
