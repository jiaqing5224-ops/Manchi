import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('manchi', {
  setTrayStatus: (status: 'idle' | 'processing' | 'newMail') => {
    ipcRenderer.send('set-tray-status', status)
  },
  minimizeToTray: () => {
    ipcRenderer.send('minimize-to-tray')
  },
  getPlatform: () => {
    return ipcRenderer.invoke('get-platform')
  },
  toggleFloatingWidget: () => {
    ipcRenderer.send('toggle-floating-widget')
  },
  showFloatingWidget: () => {
    ipcRenderer.send('show-floating-widget')
  },
  pickFile: () => {
    return ipcRenderer.invoke('pick-file')
  },
  // Window controls for frameless mode
  winMinimize: () => ipcRenderer.send('win-minimize'),
  winMaximize: () => ipcRenderer.send('win-maximize'),
  winClose: () => ipcRenderer.send('win-close'),
  // Reveal a file in the system file explorer (Finder/Explorer).
  openFile: (path: string) => ipcRenderer.invoke('open-file', path)
})
