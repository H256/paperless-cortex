import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import DocumentsView from './views/DocumentsView.vue';
import DocumentDetailView from './views/DocumentDetailView.vue';
import ConnectionsView from './views/ConnectionsView.vue';
import QueueView from './views/QueueView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/documents' },
    { path: '/documents', component: DocumentsView },
    { path: '/documents/:id', component: DocumentDetailView, props: true },
    { path: '/connections', component: ConnectionsView },
    { path: '/queue', component: QueueView },
  ],
});

createApp(App).use(router).mount('#app');
