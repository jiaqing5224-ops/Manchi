import { app, BrowserWindow, ipcMain, Menu, dialog, shell } from 'electron'
import { createWindow } from './window'
import { createTray, updateTrayStatus, TrayStatus } from './tray'
import { createFloatingWidget, updateWidgetStatus, toggleFloatingWidget, destroyFloatingWidget } from './floatingWidget'
import { startBackend, stopBackend } from './backend'

let mainWindow: BrowserWindow | null = null
let tray: ReturnType<typeof createTray> | null = null
let widgetInitialized = false

/**
 * Return the main window if it still exists, otherwise recreate it.
 * Tray and floating-widget menus call this on click so they never operate on
 * a destroyed BrowserWindow (which previously raised
 * "TypeError: Object has been destroyed").
 */
function ensureWindow(): BrowserWindow {
  if (mainWindow && !mainWindow.isDestroyed()) {
    return mainWindow
  }
  mainWindow = createWindow()
  return mainWindow
}

app.whenReady().then(async () => {
  // ── 1. Start the Python backend ──
  try {
    await startBackend()
  } catch (err: any) {
    console.error('[main] Backend startup failed:', err.message)
    if (!process.env['ELECTRON_RENDERER_URL']) {
      dialog.showErrorBox('Manchi 后端启动失败', err.message || '无法启动内置后端服务')
      app.quit()
      return
    }
  }

  // ── 2. Create UI ──
  // Remove default menu bar (File, Edit, View, etc.)
  Menu.setApplicationMenu(null)

  mainWindow = createWindow()
  tray = createTray(ensureWindow, () => {
    toggleFloatingWidget(ensureWindow)
  })

  // Listen for status updates from renderer (sync tray + widget)
  ipcMain.on('set-tray-status', (_event, status: TrayStatus) => {
    if (tray) updateTrayStatus(tray, status)
    updateWidgetStatus(status)
  })

  ipcMain.on('show-floating-widget', () => {
    if (!widgetInitialized) {
      createFloatingWidget(ensureWindow)
      widgetInitialized = true
    }
  })

  ipcMain.on('toggle-floating-widget', () => {
    toggleFloatingWidget(ensureWindow)
  })

  // Window controls for frameless mode.
  // Close button hides instead of destroying so the tray keeps the app alive.
  ipcMain.on('win-minimize', () => mainWindow?.minimize())
  ipcMain.on('win-maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize()
    else mainWindow?.maximize()
  })
  ipcMain.on('win-close', () => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.hide()
  })

  ipcMain.handle('get-platform', () => {
    return process.platform
  })

  ipcMain.handle('pick-file', async () => {
    const result = await dialog.showOpenDialog({
      title: '选择文件',
      properties: ['openFile'],
      filters: [
        { name: '支持的文件', extensions: ['txt', 'md', 'json', 'csv', 'log', 'html', 'xml', 'xlsx', 'xlsm'] },
        { name: 'Excel 文件', extensions: ['xlsx', 'xlsm'] },
        { name: '文本文件', extensions: ['txt', 'md', 'json', 'csv', 'log', 'html', 'xml'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  // Reveal a file in the system file explorer. Returns the error string on
  // failure (e.g. file missing) or empty string on success — the renderer
  // decides how to surface it.
  ipcMain.handle('open-file', async (_event, path: string) => {
    if (!path) return '未提供文件路径'
    const err = await shell.showItemInFolder(path)
    return err || ''
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createWindow()
    }
  })
})

// With a tray present, closing all windows should NOT quit the app — otherwise
// hiding the main window or toggling the floating widget would kill Manchi.
// Quit only happens via the tray "退出" item (app.quit()).
app.on('window-all-closed', () => {
  if (process.platform === 'darwin') {
    // macOS convention: keep app alive in the dock
  }
  // Other platforms: do nothing — tray remains alive.
})

app.on('before-quit', () => {
  destroyFloatingWidget()
  stopBackend()
})
