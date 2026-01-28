<template>
  <div class="app">
    <header class="app__header">
      <h1>Paperless Intelligence</h1>
      <nav class="app__nav">
        <RouterLink to="/documents">Documents</RouterLink>
        <RouterLink to="/connections">Connections</RouterLink>
      </nav>
    </header>
    <main class="app__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.app {
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  color: #1f2937;
  background: #f8fafc;
  min-height: 100vh;
}
.app__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e2e8f0;
}
.app__nav a {
  margin-left: 12px;
  color: #2563eb;
  text-decoration: none;
}
.app__main {
  padding: 24px;
}
</style>
