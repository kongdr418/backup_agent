<template>
  <div class="shell">
    <TopBar @open-settings="showSettings = true" />
    <main class="shell-main">
      <Transition mode="out-in" name="page-slide">
        <router-view />
      </Transition>
    </main>
    <MobileBottomNav />
    <SettingsDialog :visible="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TopBar from './TopBar.vue'
import MobileBottomNav from './MobileBottomNav.vue'
import SettingsDialog from '@/views/SettingsDialog.vue'

const showSettings = ref(false)
</script>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
}

.shell-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 767px) {
  .shell-main {
    padding-bottom: 64px;
    padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  }
}
</style>
