import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('./components/layout/AppShell.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('./views/DashboardView.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'chat',
        name: 'chat',
        component: () => import('./views/ChatView.vue'),
        meta: { title: '对话' },
      },
      {
        path: 'ppt-studio',
        name: 'ppt-studio',
        component: () => import('./views/PptStudioView.vue'),
        meta: { title: 'PPT 工作台' },
      },
      {
        path: 'video-studio',
        name: 'video-studio',
        component: () => import('./views/VideoStudioView.vue'),
        meta: { title: '微课' },
      },
      {
        path: 'library',
        name: 'library',
        component: () => import('./views/LibraryView.vue'),
        meta: { title: '文件库' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('./views/SettingsView.vue'),
        meta: { title: '设置' },
      },
      {
        path: 'memory',
        name: 'memory',
        component: () => import('./views/MemoryView.vue'),
        meta: { title: '记忆' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · 智创空间` : '智创空间'
})

export default router
