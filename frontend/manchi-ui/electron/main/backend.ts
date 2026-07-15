/**
 * Manchi Backend Manager
 * Spawns and manages the Python backend process.
 *
 * In dev mode: spawns `python -m uvicorn app.main:app` from the backend directory.
 * In production: spawns the PyInstaller-bundled `manchi-backend.exe`.
 */

import { app } from 'electron'
import { spawn, type ChildProcess } from 'child_process'
import { randomUUID } from 'crypto'
import { join } from 'path'
import { httpGet } from './httpUtil'

const BACKEND_PORT = 8000
const HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`
const MAX_RETRIES = 120
const RETRY_INTERVAL_MS = 1000

let backendProcess: ChildProcess | null = null
let backendInstanceToken = ''

/**
 * Determine the backend path and executable based on the environment.
 */
function getBackendCommand(): { cmd: string; args: string[]; cwd: string } {
  const isDev = !!process.env['ELECTRON_RENDERER_URL']

  if (isDev) {
    // ── Dev mode: run uvicorn via Python ──
    // Prefer MANCHI_PYTHON env var (e.g. conda env) so dev machines without
    // uvicorn in the system PATH still work. Falls back to `python`.
    const backendDir = join(__dirname, '..', '..', '..', '..', 'backend')
    return {
      cmd: process.env['MANCHI_PYTHON'] || 'python',
      args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
      cwd: backendDir
    }
  }

  // ── Production: run bundled PyInstaller exe ──
  // In production, the backend exe is placed in extraResources/backend/
  const resourcesPath = process.resourcesPath
  const exePath = join(resourcesPath, 'backend', 'manchi-backend.exe')
  return {
    cmd: exePath,
    args: [],
    cwd: join(resourcesPath, 'backend')
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
