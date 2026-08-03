import { BrowserWindow, Menu, app } from 'electron'

export type WidgetStatus = 'idle' | 'processing' | 'newMail'

// Callback used to obtain (or recreate) the main window on demand.
// Stored at createFloatingWidget time so the widget menu never holds a stale
// BrowserWindow reference that may have been destroyed.
let ensureWindowRef: (() => BrowserWindow) | null = null

const C: Record<WidgetStatus, string> = {
  idle: '#22C55E',
  processing: '#EAB308',
  newMail: '#3B82F6'
}

function html(status: WidgetStatus): string {
  const color = C[status]
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:transparent;user-select:none}
body{-webkit-app-region:no-drag}
.wrap{width:52px;height:52px;position:relative;display:flex;align-items:center;justify-content:center;cursor:pointer}

/* Outer gradient ring */
.ring{position:absolute;width:52px;height:52px;border-radius:50%;
  background:conic-gradient(from 0deg,${color}00,${color}66,${color}00,${color}44,${color}00);
  animation:spin 3s linear infinite}
.ring2{position:absolute;width:48px;height:48px;border-radius:50%;
  background:conic-gradient(from 120deg,${color}00,${color}44,${color}00,${color}22,${color}00);
  animation:spin2 4s linear infinite}
@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
@keyframes spin2{0%{transform:rotate(0deg)}100%{transform:rotate(-360deg)}}

/* Glass core */
.core{width:40px;height:40px;border-radius:50%;position:relative;z-index:2;
  background:radial-gradient(circle at 35% 35%,rgba(26,26,44,0.95),rgba(12,12,22,0.98));
  border:1px solid rgba(255,255,255,0.08);
  display:flex;align-items:center;justify-content:center;
  transition:transform 0.3s cubic-bezier(0.22,1,0.36,1)}
.wrap:hover .core{transform:scale(1.12)}
.wrap:active .core{transform:scale(0.92)}

/* M logo */
svg{width:22px;height:22px;display:block;animation:m-pulse 3s ease-in-out infinite}
@keyframes m-pulse{0%,100%{filter:drop-shadow(0 0 2px rgba(79,195,247,0.15))}50%{filter:drop-shadow(0 0 6px rgba(79,195,247,0.4))}}

/* Status dot */
.dot{position:absolute;bottom:0;right:0;width:10px;height:10px;border-radius:50%;z-index:3;
  background:${color};border:2px solid rgba(12,12,22,0.95)}
.dot::after{content:'';position:absolute;inset:-3px;border-radius:50%;
  background:${color}33;animation:br 2s ease-in-out infinite}
@keyframes br{0%,100%{transform:scale(1);opacity:0.6}50%{transform:scale(2);opacity:0}}
</style>
</head>
<body>
<div class="wrap" id="w">
  <div class="ring"></div>
  <div class="ring2"></div>
  <div class="core">
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#4FC3F7"/><stop offset="100%" stop-color="#7C3AED"/></linearGradient></defs>
      <path d="M8 32 L14 8 L20 22 L26 8 L32 32" stroke="url(#g)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div class="dot"></div>
  </div>
</div>
<script>
(function(){
  var w=document.getElementById('w');
  var dr=false,dx=0,dy=0,wx=0,wy=0;
  w.addEventListener('mousedown',function(e){
    if(e.button!==0)return;dr=true;dx=e.screenX;dy=e.screenY;
    wx=window.screenX;wy=window.screenY;e.preventDefault()
  });
  document.addEventListener('mousemove',function(e){if(dr)window.moveTo(wx+e.screenX-dx,wy+e.screenY-dy)});
  document.addEventListener('mouseup',function(){dr=false});
  document.addEventListener('contextmenu',function(e){e.preventDefault();console.log('MANCHI_MENU')});
  w.addEventListener('dblclick',function(e){e.preventDefault();console.log('MANCHI_OPEN')});
})();
</script>
</body>
</html>`
}

let ww: BrowserWindow | null = null

function menu(): Menu {
  return Menu.buildFromTemplate([
    {
      label: '打开 Manchi',
      click: () => {
        if (!ensureWindowRef) return
        const w = ensureWindowRef()
        w.show()
        w.focus()
      }
    },
    {
      label: '扫描邮件',
      click: () => {
        if (!ensureWindowRef) return
        const w = ensureWindowRef()
        w.show()
        w.webContents.send('action', 'scan-mail')
      }
    },
    { type: 'separator' },
    { label: '隐藏悬浮窗', click: () => { destroyFloatingWidget() } },
    { type: 'separator' },
    { label: '退出', click: () => { destroyFloatingWidget(); app.quit() } }
  ])
}

export function createFloatingWidget(ensureWindow: () => BrowserWindow): BrowserWindow {
  if (ww && !ww.isDestroyed()) { ww.show(); ww.focus(); return ww }
  ensureWindowRef = ensureWindow
  ww = new BrowserWindow({
    width: 52, height: 52, x: 100, y: 100,
    frame: false, transparent: true, resizable: false,
    skipTaskbar: true, alwaysOnTop: true, hasShadow: false, type: 'toolbar',
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false }
  })
  ww.setAlwaysOnTop(true, 'floating')
  ww.setVisibleOnAllWorkspaces(true)
  ww.webContents.on('context-menu', e => e.preventDefault())
  ww.webContents.on('console-message', (_e, _l, msg) => {
    if (msg === 'MANCHI_MENU' && ww) menu().popup({ window: ww })
    else if (msg === 'MANCHI_OPEN' && ensureWindowRef) {
      const win = ensureWindowRef()
      win.show()
      win.focus()
    }
  })
  ww.loadURL(`data:text/html;base64,${Buffer.from(html('idle')).toString('base64')}`)
  ww.on('closed', () => { ww = null })
  return ww
}

export function updateWidgetStatus(s: WidgetStatus): void {
  if (ww && !ww.isDestroyed()) ww.loadURL(`data:text/html;base64,${Buffer.from(html(s)).toString('base64')}`)
}

export function toggleFloatingWidget(ensureWindow: () => BrowserWindow): void {
  if (ww && !ww.isDestroyed()) { ww.close(); ww = null }
  else createFloatingWidget(ensureWindow)
}

export function destroyFloatingWidget(): void {
  if (ww && !ww.isDestroyed()) { ww.close(); ww = null }
}
