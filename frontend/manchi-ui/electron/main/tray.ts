import { Tray, Menu, nativeImage, BrowserWindow, app } from 'electron'
import zlib from 'zlib'

export type TrayStatus = 'idle' | 'processing' | 'newMail'

const STATUS_COLORS: Record<TrayStatus, [number, number, number]> = {
  idle: [34, 197, 94],
  processing: [234, 179, 8],
  newMail: [59, 130, 246]
}

/**
 * Minimal CRC32 lookup table.
 */
function crc32(data: Buffer): number {
  let crc = 0xffffffff
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i]
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0)
    }
  }
  return (crc ^ 0xffffffff) >>> 0
}

/**
 * Create a chunk for PNG format.
 */
function pngChunk(type: string, data: Buffer): Buffer {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length, 0)
  const typeB = Buffer.from(type, 'ascii')
  const combined = Buffer.concat([typeB, data])
  const crcB = Buffer.alloc(4)
  crcB.writeUInt32BE(crc32(combined), 0)
  return Buffer.concat([len, typeB, data, crcB])
}

/**
 * Generate a valid PNG from raw RGBA pixel data.
 * Uses Node.js built-in zlib for deflate compression.
 */
function encodePNG(width: number, height: number, rgba: Buffer): Buffer {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])

  // IHDR
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8   // bit depth
  ihdr[9] = 6   // color type: RGBA
  ihdr[10] = 0  // compression
  ihdr[11] = 0  // filter
  ihdr[12] = 0  // interlace

  // IDAT: PNG rows have a filter byte prefix (0 = none)
  const rowSize = 1 + width * 4
  const raw = Buffer.alloc(height * rowSize)
  for (let y = 0; y < height; y++) {
    raw[y * rowSize] = 0
    rgba.copy(raw, y * rowSize + 1, y * width * 4, (y + 1) * width * 4)
  }

  const compressed = zlib.deflateSync(raw)

  return Buffer.concat([
    sig,
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', compressed),
    pngChunk('IEND', Buffer.alloc(0))
  ])
}

/**
 * Draw a hex node symbol + status dot onto RGBA pixel buffer.
 */
function drawIcon(size: number, color: [number, number, number]): Buffer {
  const rgba = Buffer.alloc(size * size * 4, 0)
  const [cr, cg, cb] = color
  const c1: [number, number, number] = [79, 195, 247]
  const c2: [number, number, number] = [124, 58, 237]

  function sp(x: number, y: number, r: number, g: number, b: number, a = 255): void {
    if (x < 0 || x >= size || y < 0 || y >= size) return
    const i = (y * size + x) * 4; rgba[i] = r; rgba[i + 1] = g; rgba[i + 2] = b; rgba[i + 3] = a
  }

  function ln(x0: number, y0: number, x1: number, y1: number, r: number, g: number, b: number, t = 1): void {
    const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1
    let err = dx - dy, x = x0, y = y0
    while (true) {
      for (let i = -t; i <= t; i++) for (let j = -t; j <= t; j++) if (i * i + j * j <= t * t) sp(x + i, y + j, r, g, b)
      if (x === x1 && y === y1) break
      const e2 = 2 * err; if (e2 > -dy) { err -= dy; x += sx }; if (e2 < dx) { err += dx; y += sy }
    }
  }

  const cx = size / 2, cy = size / 2, s = size / 2.6

  // M shape: 5 points matching the SVG logo
  const pts: [number, number][] = [
    [cx - s * 0.55, cy + s * 0.55],
    [cx - s * 0.3,  cy - s * 0.55],
    [cx,           cy + s * 0.05],
    [cx + s * 0.3,  cy - s * 0.55],
    [cx + s * 0.55, cy + s * 0.55]
  ]

  for (let i = 0; i < pts.length - 1; i++) {
    const m = i / 3
    const r = Math.round(c1[0] * (1 - m) + c2[0] * m)
    const g = Math.round(c1[1] * (1 - m) + c2[1] * m)
    const b = Math.round(c1[2] * (1 - m) + c2[2] * m)
    ln(Math.round(pts[i][0]), Math.round(pts[i][1]),
       Math.round(pts[i + 1][0]), Math.round(pts[i + 1][1]), r, g, b, 2)
  }

  // Status dot at bottom right
  const dotX = Math.round(cx + s * 0.55), dotY = Math.round(cy + s * 0.55)
  const dr = Math.max(2.5, size / 12)
  for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
    const d = Math.sqrt(dx * dx + dy * dy)
    if (d <= dr) sp(dotX + dx, dotY + dy, cr, cg, cb, Math.round(Math.max(0, 255 * (1 - d / (dr + 1)))))
    else if (d <= dr + 3) sp(dotX + dx, dotY + dy, cr, cg, cb, Math.round(Math.max(0, 60 * (1 - (d - dr) / 3))))
  }

  return rgba
}

function generateTrayIcon(status: TrayStatus): nativeImage {
  const size = 32
  const color = STATUS_COLORS[status]
  const rgba = drawIcon(size, color)
  const png = encodePNG(size, size, rgba)
  return nativeImage.createFromBuffer(png, { width: size, height: size })
    .resize({ width: 16, height: 16 })
}

/** Generate a 64x64 icon for the window title bar / taskbar */
export function generateWindowIcon(): nativeImage {
  const size = 64
  const color: [number, number, number] = [79, 195, 247]
  const rgba = drawIcon(size, color)
  const png = encodePNG(size, size, rgba)
  return nativeImage.createFromBuffer(png, { width: size, height: size })
}

export function createTray(
  ensureWindow: () => BrowserWindow,
  onToggleWidget?: () => void
): Tray {
  const icon = generateTrayIcon('idle')
  const tray = new Tray(icon)

  tray.setToolTip('Manchi - 智能 Agent 平台')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '打开 Manchi',
      click: () => {
        const win = ensureWindow()
        win.show()
        win.focus()
      }
    },
    { type: 'separator' },
    {
      label: '扫描邮件',
      click: () => {
        const win = ensureWindow()
        win.show()
        win.webContents.send('action', 'scan-mail')
      }
    },
    { type: 'separator' },
    {
      label: '显示悬浮窗',
      click: () => {
        if (onToggleWidget) onToggleWidget()
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.quit()
      }
    }
  ])

  tray.setContextMenu(contextMenu)

  tray.on('click', () => {
    const win = ensureWindow()
    if (win.isVisible()) {
      win.hide()
    } else {
      win.show()
      win.focus()
    }
  })

  return tray
}

export function updateTrayStatus(tray: Tray, status: TrayStatus): void {
  tray.setImage(generateTrayIcon(status))
  const labels: Record<TrayStatus, string> = {
    idle: 'Manchi - 待命中',
    processing: 'Manchi - 处理中...',
    newMail: 'Manchi - 新邮件'
  }
  tray.setToolTip(labels[status])
}
