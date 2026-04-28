import { createRouter, createWebHashHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { titleKey: 'navDashboard' },
      },
      {
        path: 'miss-logs',
        name: 'MissLogs',
        component: () => import('../views/MissLogsView.vue'),
        meta: { titleKey: 'navMissLogs' },
      },
      {
        path: 'subset',
        name: 'Subset',
        component: () => import('../views/SubsetView.vue'),
        meta: { titleKey: 'navSubset' },
      },
      {
        path: 'hdr',
        name: 'HDR',
        component: () => import('../views/HdrView.vue'),
        meta: { titleKey: 'navHdr' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { titleKey: 'navSettings' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory('/subset/'),
  routes,
})

export default router
