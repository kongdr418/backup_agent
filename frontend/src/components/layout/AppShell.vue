<template>
  <div class="shell">
    <TopBar />
    <main class="shell-main">
      <router-view />
    </main>
    <MobileBottomNav />
  </div>
</template>

<script setup lang="ts">
import TopBar from './TopBar.vue'
import MobileBottomNav from './MobileBottomNav.vue'
</script>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent; /* 透明 — 让 mesh 透出来 */
}

.shell-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 767px) {
  .shell-main {
    padding-bottom: 64px; /* 为 MobileBottomNav 留空间 */
    padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  }
}
</style>
