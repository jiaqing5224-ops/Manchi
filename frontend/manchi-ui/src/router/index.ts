import { createRouter, createMemoryHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/pages/Dashboard.vue')
  },
  {
    path: '/mail',
    name: 'MailAssistant',
    component: () => import('@/pages/MailAssistant.vue')
  },
  {
    path: '/tasks',
    name: 'TaskCenter',
    component: () => import('@/pages/TaskCenter.vue')
  },
  {
    path: '/orch',
    name: 'SmartOrch',
    component: () => import('@/pages/SmartOrch.vue')
  },
  {
    path: '/chat',
    name: 'ChatCenter',
    component: () => import('@/pages/ChatCenter.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/Settings.vue')
  }
]

const router = createRouter({
  history: createMemoryHistory(),
  routes
})

export default router
