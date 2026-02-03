import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import DocumentsView from './views/DocumentsView.vue';
import DocumentDetailView from './views/DocumentDetailView.vue';
import DashboardView from './views/DashboardView.vue';
import QueueView from './views/QueueView.vue';
import SearchView from './views/SearchView.vue';
import ChatView from './views/ChatView.vue';
import MaintenanceView from './views/MaintenanceView.vue';
import './index.css';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/documents' },
    { path: '/documents', component: DocumentsView },
    { path: '/documents/:id', component: DocumentDetailView, props: true },
    { path: '/dashboard', component: DashboardView },
    { path: '/search', component: SearchView },
    { path: '/queue', component: QueueView },
    { path: '/chat', component: ChatView },
    { path: '/operations', component: MaintenanceView },
  ],
});

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
