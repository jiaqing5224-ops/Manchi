/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, never>
  export default component
}

interface Window {
  manchi: {
    setTrayStatus: (status: 'idle' | 'processing' | 'newMail') => void
    minimizeToTray: () => void
    getPlatform: () => Promise<string>
    toggleFloatingWidget: () => void
    showFloatingWidget: () => void
    pickFile: () => Promise<string | null>
    winMinimize: () => void
    winMaximize: () => void
    winClose: () => void
    openFile: (path: string) => Promise<string>
  }
}
