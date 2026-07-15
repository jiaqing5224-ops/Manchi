/**
 * Simple HTTP utility for the Electron main process.
 * Uses Node.js built-in http module (no external dependency).
 */
import * as http from 'http'

export interface HttpResponse {
  status: number
  body: string
}

export function httpGet(url: string): Promise<HttpResponse> {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = ''
      res.on('data', (chunk: string) => { body += chunk })
      res.on('end', () => {
        resolve({ status: res.statusCode ?? 0, body })
      })
    })
    req.on('error', (err) => reject(err))
    req.setTimeout(3000, () => {
      req.destroy()
      reject(new Error('Request timed out'))
    })
  })
}
