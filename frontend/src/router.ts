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
        path: 'interactive-classroom',
        name: 'interactive-classroom-home',
        component: () => import('./views/InteractiveClassroomHomeView.vue'),
        meta: { title: '交互式课堂' },
      },
      {
        path: 'interactive-classroom/:classroomId',
        name: 'interactive-classroom-player',
        component: () => import('./views/InteractiveClassroomPlayerView.vue'),
        meta: { title: '课堂播放' },
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
      {
        path: 'student-profile',
        name: 'student-profile',
        component: () => import('./views/StudentProfileView.vue'),
        meta: { title: '学习者中心' },
      },
    ],
  },
  {
    path: '/pptist-preview/:jobId',
    name: 'pptist-preview',
    component: () => import('./views/PptistPreviewView.vue'),
    meta: { title: 'PPT 场景编辑' },
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
  const brand = '智创空间 · 多智能体智慧课堂'
  document.title = title ? `${title} · ${brand}` : brand
})

export default router
