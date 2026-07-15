<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="app-content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" :key="$route.fullPath" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import AppSidebar from './components/layout/AppSidebar.vue'

const appStore = useAppStore()

onMounted(() => {
  // Auto-show desktop floating widget on startup
  appStore.showFloatingWidget()
})
</script>

<style scoped>
.app-shell {
  display: flex;
  width: 100%;
  height: 100%;
}

.app-content {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  margin-left: var(--sidebar-w);
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.25s ease, transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
