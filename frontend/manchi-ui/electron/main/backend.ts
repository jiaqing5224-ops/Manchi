/**
 * Manchi Backend Manager
 * Spawns and manages the Python backend process.
 *
 * Dev mode:       spawns `python -m uvicorn app.main:app` (prefers the
 *                dedicated Manchi venv at ~/Documents/Manchi/venv).
 * Production:    on first launch, bootstraps a user-writable venv at
 *                ~/Documents/Manchi/venv from a bundled/system Python, then
 *                runs the backend through that venv. This is what lets the
 *                shipped product `pip install` component dependencies at
 *                runtime — a frozen PyInstaller exe cannot receive installs.
 */

import { app } from 'electron'
import { spawn, execSync, type ChildProcess } from 'child_process'
import { randomUUID } from 'crypto'
import { existsSync } from 'fs'
import { join } from 'path'
import os from 'os'
import { httpGet } from './httpUtil'

const BACKEND_PORT = 8000
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`
const MAX_RETRIES = 120
const RETRY_INTERVAL_MS = 1000

// User-writable app data root. The venv and component dirs live here so they
// survive app updates and are writable without admin rights.
const MANCHI_DIR = join(os.homedir(), 'Documents', 'Manchi')

let backendProcess: ChildProcess | null = null
let backendInstanceToken = ''

/**
 * Probe PATH for a usable system Python (Windows `py` launcher first).
 */
function findSystemPython(): string | null {
  for (const cand of ['py.exe', 'python.exe', 'python3', 'python']) {
    try {
      const out = execSync(`where ${cand}`, { stdio: ['ignore', 'pipe', 'ignore'] })
        .toString()
        .trim()
        .split(/\r?\n/)[0]
      if (out) return out
    } catch {
      // not found
    }
  }
  return null
}

/**
 * Production only: ensure the dedicated venv exists. If missing, create it
 * from a bundled Python (extraResources/python) or, failing that, a system
 * Python, then install backend + component requirements. Idempotent.
 */
async function ensureRuntime(): Promise<void> {
  const venvPython = join(MANCHI_DIR, 'venv', 'Scripts', 'python.exe')
  if (existsSync(venvPython)) return // already bootstrapped

  const resourcesPath = process.resourcesPath
  const bundled = join(resourcesPath, 'python', 'python.exe')
  const basePython = existsSync(bundled) ? bundled : findSystemPython()
  if (!basePython) {
    throw new Error(
      '未找到可用于初始化运行时的 Python（安装包应自带 Python，或系统需已安装 python）'
    )
  }

  const backendDir = join(resourcesPath, 'backend')
  const componentsDir = join(MANCHI_DIR, 'components')
  console.log('[backend] 首次启动：正在初始化 Python 运行环境（可能需要几分钟）…')

  await new Promise<void>((resolve, reject) => {
    const proc = spawn(
      basePython,
      [
        join(backendDir, 'scripts', 'bootstrap_runtime.py'),
        '--components-dir', componentsDir,
        '--backend-dir', backendDir,
      ],
      { stdio: ['ignore', 'pipe', 'pipe'], shell: false }
    )
    proc.stdout?.on('data', (d: Buffer) => console.log(`[bootstrap:out] ${d.toString().trim()}`))
    proc.stderr?.on('data', (d: Buffer) => console.log(`[bootstrap:err] ${d.toString().trim()}`))
    proc.on('exit', (code) =>
      code === 0 ? resolve() : reject(new Error(`运行时初始化失败 (exit=${code})`))
    )
    proc.on('error', (e) => reject(e))
  })

  console.log('[backend] 运行环境初始化完成')
}

/**
 * Determine the backend command based on the environment.
 */
function getBackendCommand(): { cmd: string; args: string[]; cwd: string } {
  const isDev = !!process.env['ELECTRON_RENDERER_URL']

  if (isDev) {
    // ── Dev mode: run uvicorn via Python ──
    // Prefer MANCHI_PYTHON env var, then the dedicated Manchi runtime venv
    // (C:\Users\<user>\Documents\Manchi\venv), then a system `python`.
    const backendDir = join(__dirname, '..', '..', '..', '..', 'backend')
    const venvPython = join(MANCHI_DIR, 'venv', 'Scripts', 'python.exe')
    const cmd =
      process.env['MANCHI_PYTHON'] ||
      (existsSync(venvPython) ? venvPython : 'python')
    return {
      cmd,
      args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
      cwd: backendDir
    }
  }

  // ── Production: run the backend through the bootstrapped venv ──
  // ensureRuntime() (called in startBackend) guarantees this venv exists.
  const backendDir = join(process.resourcesPath, 'backend')
  const venvPython = join(MANCHI_DIR, 'venv', 'Scripts', 'python.exe')
  return {
    cmd: venvPython,
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    cwd: backendDir
  }
}

/**
 * Wait for the backend health endpoint to respond.
 */
async function waitForBackend(): Promise<void> {
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const res = await httpGet(HEALTH_URL)
      const body = JSON.parse(res.body || '{}') as { instance_token?: string }
      const tokenMatches = !backendInstanceToken || body.instance_token === backendInstanceToken
      if (res.status === 200 && tokenMatches) {
        console.log('[backend] Health check passed')
        return
      }
    } catch {
      // not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL_MS))
  }
  throw new Error(`Backend failed to start within ${MAX_RETRIES * RETRY_INTERVAL_MS / 1000}s`)
}

/**
 * Start the backend process and wait for it to be ready.
 */
export async function startBackend(): Promise<void> {
  const isDev = !!process.env['ELECTRON_RENDERER_URL']
  if (!isDev) {
    // Production: make sure the dedicated venv exists before launching.
    await ensureRuntime()
  }

  const { cmd, args, cwd } = getBackendCommand()
  backendInstanceToken = randomUUID()

  console.log(`[backend] Starting: ${cmd} ${args.join(' ')} (cwd: ${cwd})`)

  backendProcess = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    shell: false,
    env: {
      ...process.env,
      MANCHI_BACKEND_INSTANCE_TOKEN: backendInstanceToken,
      // Keep component data under the user-writable Manchi dir.
      MANCHI_COMPONENTS: join(MANCHI_DIR, 'components'),
    },
  })

  backendProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[backend:out] ${data.toString().trim()}`)
  })

  backendProcess.stderr?.on('data', (data: Buffer) => {
    console.log(`[backend:err] ${data.toString().trim()}`)
  })

  backendProcess.on('exit', (code, signal) => {
    console.log(`[backend] Exited with code=${code} signal=${signal}`)
    backendProcess = null
  })

  backendProcess.on('error', (err) => {
    console.error(`[backend] Failed to start: ${err.message}`)
    backendProcess = null
  })

  try {
    await waitForBackend()
  } catch (err) {
    stopBackend()
    throw err
  }
  console.log('[backend] Ready')
}

/**
 * Gracefully stop the backend process.
 */
export function stopBackend(): void {
  if (!backendProcess) return
  console.log('[backend] Stopping...')
  if (process.platform === 'win32') {
    // On Windows, kill the process tree to ensure uvicorn child processes die
    spawn('taskkill', ['/F', '/T', '/PID', String(backendProcess.pid!)])
  } else {
    backendProcess.kill('SIGTERM')
  }
  backendProcess = null
}
