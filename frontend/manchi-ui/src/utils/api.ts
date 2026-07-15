const API_BASE = 'http://localhost:8000'

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options

  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers
    }
  }

  if (body) {
    config.body = JSON.stringify(body)
  }

  const response = await fetch(`${API_BASE}${endpoint}`, config)

  if (!response.ok) {
    const raw = await response.text().catch(() => '')
    let detail = raw
    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed.detail === 'string') detail = parsed.detail
    } catch {
      // keep raw text if not JSON
    }
    throw new Error(detail || `API Error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

export const api = {
  get<T>(endpoint: string) {
    return request<T>(endpoint)
  },

  post<T>(endpoint: string, body: unknown) {
    return request<T>(endpoint, { method: 'POST', body })
  },

  put<T>(endpoint: string, body: unknown) {
    return request<T>(endpoint, { method: 'PUT', body })
  },

  delete<T>(endpoint: string) {
    return request<T>(endpoint, { method: 'DELETE' })
  }
}

export interface ChatEvent {
  text?: string
  tool_call?: { id: string; name: string; args: string }
  tool_result?: { id: string; name: string; result: string }
  done?: boolean
}

/**
 * SSE streaming helper for chat (function-call aware).
 * Calls the API, parses SSE data events, invokes onEvent for each event
 * (text / tool_call / tool_result), and resolves when the stream ends.
 */
export function streamChat(
  sessionId: string,
  message: string,
  history: { role: string; content: string }[],
  onEvent: (evt: ChatEvent) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, history })
    }).then(async response => {
      if (!response.ok) {
        reject(new Error(`Chat stream error: ${response.status}`))
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        reject(new Error('No response body reader'))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: ChatEvent = JSON.parse(line.slice(6))
              if (data.done) {
                resolve()
                return
              }
              onEvent(data)
            } catch {
              // skip malformed JSON
            }
          }
        }
      }
      resolve()
    }).catch(reject)
  })
}