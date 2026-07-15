import { defineStore } from 'pinia'
import { ref, onMounted } from 'vue'

export type AppStatus = 'idle' | 'processing' | 'newMail'

export const useAppStore = defineStore('app', () => {
  const trayStatus = ref<AppStatus>('idle')
  const sidebarCollapsed = ref(false)
  const floatingWidgetVisible = ref(false)

  function setTrayStatus(status: AppStatus) {
    trayStatus.value = status
    if (window.manchi) {
      window.manchi.setTrayStatus(status)
    }
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleFloatingWidget() {
    floatingWidgetVisible.value = !floatingWidgetVisible.value
    if (window.manchi) {
      window.manchi.toggleFloatingWidget()
    }
  }

  function showFloatingWidget() {
    floatingWidgetVisible.value = true
    if (window.manchi) {
      window.manchi.showFloatingWidget()
    }
  }

  return {
    trayStatus,
    sidebarCollapsed,
    floatingWidgetVisible,
    setTrayStatus,
    toggleSidebar,
    toggleFloatingWidget,
    showFloatingWidget
  }
})
