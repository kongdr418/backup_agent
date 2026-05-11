import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/themeStore'

import './assets/styles/tailwind.css'

const app = createApp(App)

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)

// 主题初始化必须在 mount 之前同步执行,避免首屏 FOUC
useThemeStore().init()

app.use(router)
app.mount('#app')
