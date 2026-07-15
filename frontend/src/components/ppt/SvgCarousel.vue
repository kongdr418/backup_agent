<template>
  <div class="carousel-wrap">
    <!-- Main viewer -->
    <div class="carousel-viewer">
      <div
        v-if="currentSlide"
        class="svg-stage"
        v-html="sanitizeSvg(currentSlide.svg)"
      />
      <div v-else class="placeholder-wrap">
        <ImagePlay class="placeholder-icon" />
        <span class="placeholder-text">SVG 预览将在生成时实时显示</span>
      </div>
    </div>

    <!-- Bottom: thumbnails + nav -->
    <div v-if="slides.length > 0" class="carousel-bottom">
      <!-- Thumbnails -->
      <div v-if="slides.length > 1" class="thumb-list">
        <button
          v-for="(s, i) in slides"
          :key="s.page"
          class="thumb-btn"
          :class="{ 'is-active': i === activeIdx }"
          @click="$emit('select', i)"
        >
          <div
            class="thumb-svg"
            v-html="sanitizeSvg(s.svg)"
          />
          <span class="thumb-no">{{ s.page }}</span>
        </button>
      </div>

      <!-- Nav -->
      <div v-if="slides.length > 1" class="nav-row">
        <span class="nav-count">{{ activeIdx + 1 }} / {{ slides.length }}</span>
        <div class="nav-btns">
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
import { sanitizeSvg } from '@/utils/sanitizeSvg'

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
  padding: 8px 4px 4px;
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
  box-shadow: 0 2px 12px rgb(0 0 0 / 0.06);
}

/* Placeholder */
.placeholder-wrap {
  text-align: center;
  padding: 48px 24px;
}
.placeholder-icon {
  width: 32px;
  height: 32px;
  margin: 0 auto 10px;
  color: rgb(var(--ink-4-rgb));
}
.placeholder-text {
  font-size: 13px;
  color: rgb(var(--ink-3-rgb));
}

/* Thumbnails */
.thumb-list {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 6px;
  margin-bottom: 4px;
}

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
  transition: border-color 180ms ease;
}

.thumb-btn:hover {
  border-color: rgb(var(--line-strong-rgb));
}

.thumb-btn.is-active {
  border-color: rgb(var(--ink-1-rgb));
}

.thumb-svg {
  width: 100%;
  height: 100%;
}
.thumb-svg :deep(svg) {
  width: 100%;
  height: 100%;
}

.thumb-no {
  position: absolute;
  bottom: 1px;
  right: 3px;
  font-size: 9px;
  color: rgb(var(--ink-3-rgb));
  background: rgb(var(--bg-surface-rgb) / 0.85);
  padding: 0 3px;
  border-radius: 3px;
  line-height: 1.4;
}

/* Nav */
.nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
}

.nav-count {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  font-variant-numeric: tabular-nums;
}

.nav-btns {
  display: flex;
  gap: 4px;
}

.nav-btn {
  width: 26px;
  height: 26px;
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
  border-color: rgb(var(--line-strong-rgb));
}

.nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
