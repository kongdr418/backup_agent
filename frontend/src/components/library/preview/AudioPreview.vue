<template>
  <div class="audio-preview">
    <div class="audio-card">
      <div class="audio-icon">
        <Music class="w-6 h-6" />
      </div>
      <div class="audio-info">
        <div class="audio-name">{{ name }}</div>
        <div class="audio-meta">{{ meta }}</div>
      </div>
    </div>

    <div ref="waveformEl" class="waveform-container" />

    <audio
      ref="audioEl"
      controls
      class="audio-controls"
      :src="src"
      preload="metadata"
    />

    <div v-if="waveError" class="wave-fallback">
      <span class="text-[11px] text-ink-4">波形加载失败,使用标准播放器</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Music } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  name?: string
  meta?: string
}>()

const waveformEl = ref<HTMLElement | null>(null)
const audioEl = ref<HTMLAudioElement | null>(null)
const waveError = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let wavesurferInstance: any = null

async function initWaveform() {
  if (!waveformEl.value || !audioEl.value || !props.src) return

  try {
    const WaveSurfer = (await import('wavesurfer.js')).default
    wavesurferInstance = WaveSurfer.create({
      container: waveformEl.value,
      waveColor: 'rgb(var(--ink-4-rgb) / 0.3)',
      progressColor: 'rgb(var(--accent-rgb))',
      cursorColor: 'rgb(var(--accent-rgb))',
      barWidth: 2,
      barRadius: 3,
      barGap: 1,
      height: 48,
      normalize: true,
    })

    wavesurferInstance.load(props.src)
  } catch {
    waveError.value = true
  }
}

onMounted(() => {
  setTimeout(initWaveform, 100)
})

onUnmounted(() => {
  if (wavesurferInstance) {
    wavesurferInstance.destroy()
    wavesurferInstance = null
  }
})

watch(() => props.src, () => {
  if (wavesurferInstance) {
    wavesurferInstance.destroy()
    wavesurferInstance = null
  }
  waveError.value = false
  setTimeout(initWaveform, 100)
})
</script>

<style scoped>
.audio-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
}

.audio-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.audio-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgb(var(--accent-orange-rgb) / 0.12);
  color: rgb(var(--accent-orange-rgb));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.audio-info {
  min-width: 0;
}

.audio-name {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.audio-meta {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  margin-top: 2px;
}

.waveform-container {
  width: 100%;
  min-height: 48px;
  border-radius: 8px;
  overflow: hidden;
}

.audio-controls {
  width: 100%;
  height: 36px;
  border-radius: 8px;
  outline: none;
}

.wave-fallback {
  text-align: center;
  padding: 4px 0;
}
</style>
