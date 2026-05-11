<template>
  <div class="shell">
    <TopBar />
    <main class="shell-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import TopBar from './TopBar.vue'
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
  /* 顶栏 56px 已 sticky,这里不再扣 */
}
</style>
