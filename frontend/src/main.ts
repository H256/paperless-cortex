import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import App from './App.vue'
import DocumentsView from './views/DocumentsView.vue'
import DocumentDetailView from './views/DocumentDetailView.vue'
import DashboardView from './views/DashboardView.vue'
import QueueView from './views/QueueView.vue'
import LogInspectorView from './views/LogInspectorView.vue'
import SearchView from './views/SearchView.vue'
import ChatView from './views/ChatView.vue'
import MaintenanceView from './views/MaintenanceView.vue'
import WritebackDryRunView from './views/WritebackDryRunView.vue'
import './index.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/documents' },
    { path: '/documents', component: DocumentsView },
    { path: '/documents/:id', component: DocumentDetailView, props: true },
    { path: '/dashboard', component: DashboardView },
    { path: '/search', component: SearchView },
    { path: '/queue', component: QueueView },
    { path: '/logs', component: LogInspectorView },
    { path: '/chat', component: ChatView },
    { path: '/operations', component: MaintenanceView },
    { path: '/writeback', component: WritebackDryRunView },
    { path: '/writeback-dry-run', redirect: '/writeback' },
  ],
})

const app = createApp(App)
const queryClient = new QueryClient()
app.use(createPinia())
app.use(VueQueryPlugin, { queryClient })
app.use(router)
app.mount('#app')
