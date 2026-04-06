import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import App from './App.vue'
import './index.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/documents' },
    { path: '/documents', component: () => import('./views/DocumentsView.vue') },
    { path: '/documents/:id', component: () => import('./views/DocumentDetailView.vue'), props: true },
    { path: '/dashboard', component: () => import('./views/DashboardView.vue') },
    { path: '/search', component: () => import('./views/SearchView.vue') },
    { path: '/queue', component: () => import('./views/QueueView.vue') },
    { path: '/logs', component: () => import('./views/LogInspectorView.vue') },
    { path: '/processing/continue', component: () => import('./views/ContinueProcessingView.vue') },
    { path: '/chat', component: () => import('./views/ChatView.vue') },
    { path: '/settings', component: () => import('./views/SettingsView.vue') },
    { path: '/operations', component: () => import('./views/MaintenanceView.vue') },
    { path: '/writeback', component: () => import('./views/WritebackDryRunView.vue') },
    { path: '/writeback-dry-run', redirect: '/writeback' },
  ],
})

const app = createApp(App)
const queryClient = new QueryClient()
app.use(createPinia())
app.use(VueQueryPlugin, { queryClient })
app.use(router)
app.mount('#app')
