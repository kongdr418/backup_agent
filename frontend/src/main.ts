import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/themeStore'
import { ensureDeviceSession } from './api/deviceSession'

import './assets/styles/tailwind.css'

const app = createApp(App)

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)

// 主题初始化必须在 mount 之前同步执行,避免首屏 FOUC
useThemeStore().init()

app.use(router)
ensureDeviceSession()
  .catch((error) => console.warn('[device-session] 初始化失败，将在后续 API 请求时重试', error))
  .finally(() => app.mount('#app'))
