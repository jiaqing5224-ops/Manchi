<template>
  <div class="chat-page">
    <!-- Messages Area -->
    <div class="chat-messages" ref="messagesRef">
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
        <div class="message-avatar">
          <span v-if="msg.role === 'assistant'">M</span>
          <span v-else>U</span>
        </div>
        <div class="message-content">
          <div v-if="msg.toolCalls && msg.toolCalls.length" class="tool-summary" @click="toggleToolDetail(i)">
            <span class="tool-summary-icon">🔧</span>
            <span class="tool-summary-text">已使用 {{ msg.toolCalls.length }} 个工具调用</span>
            <span class="tool-summary-toggle">{{ expandedTools.has(i) ? '收起' : '展开' }}</span>
          </div>
          <div v-if="expandedTools.has(i) && msg.toolCalls && msg.toolCalls.length" class="tool-calls">
            <div v-for="(tc, j) in msg.toolCalls" :key="'tc'+j" class="tool-bubble tool-call-bubble">
              <span class="tool-tag">调用</span>
              <span class="tool-name">{{ tc.name }}</span>
              <span class="tool-args">{{ tc.args }}</span>
            </div>
          </div>
          <div v-if="msg.content" class="message-text markdown-body" v-html="renderMarkdown(msg.content)"></div>
          <div v-else-if="msg.role === 'assistant' && (!msg.toolCalls || msg.toolCalls.length === 0) && isThinking" class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
          <div v-if="expandedTools.has(i) && msg.toolResults && msg.toolResults.length" class="tool-results">
            <div v-for="(tr, j) in msg.toolResults" :key="'tr'+j" class="tool-bubble tool-result-bubble">
              <span class="tool-tag">结果</span>
              <span class="tool-name">{{ tr.name }}</span>
              <pre class="tool-result-content">{{ tr.result }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          ref="chatInputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="输入消息，与 Manchi 对话..."
          rows="1"
          @input="resizeChatInput"
          @keydown.enter.exact.prevent="sendMessage()"
        ></textarea>
        <button class="clear-btn" title="清空对话" @click="clearChat" :disabled="isThinking">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
        <button class="send-btn" :disabled="!inputText.trim() || isThinking" @click="sendMessage()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onActivated, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, streamChat, type ChatEvent } from '@/utils/api'

const SESSION_ID = 'default'
const route = useRoute()

interface TaskContextMeta {
  mail_id?: string
  subject?: string
  sender_name?: string
  sender_email?: string
  received_at?: string
  not_found?: boolean
  char_count?: number
  file_path?: string
  file_name?: string
  file_size?: number
  read_error?: string
}

interface TaskContext {
  task_id: number
  title: string
  description: string
  source_type: string | null
  source_meta: TaskContextMeta
  source_content: string
}

interface ToolCall {
  name: string
  args: string
}

interface ToolResult {
  name: string
  result: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
  toolResults?: ToolResult[]
}

const WELCOME = '你好！我是 Manchi，你的个人 AI 助手。我可以帮你处理邮件、管理任务、执行自动化操作。有什么需要的吗？'

const messages = ref<Message[]>([
  { role: 'assistant', content: WELCOME }
])

const inputText = ref('')
const isThinking = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const chatInputRef = ref<HTMLTextAreaElement | null>(null)
const expandedTools = reactive(new Set<number>())

marked.setOptions({
  breaks: true,
  gfm: true
})

function renderMarkdown(content: string): string {
  const raw = marked.parse(content, { async: false }) as string
  return DOMPurify.sanitize(raw)
}

function toggleToolDetail(idx: number) {
  if (expandedTools.has(idx)) {
    expandedTools.delete(idx)
  } else {
    expandedTools.add(idx)
  }
}

onMounted(async () => {
  try {
    const history = await api.get<{ role: string; content: string }[]>(`/api/chat/history/${SESSION_ID}`)
    if (history.length > 0) {
      messages.value = history.map(h => ({
        role: h.role as 'user' | 'assistant',
        content: h.content
      }))
      scrollToBottom()
    }
  } catch {
    // No history yet — keep welcome message
  }

  // AI 协助入口：任务中心右键「AI 协助」跳转过来时，自动拉取任务上下文并发送。
  // 注意：不能 router.replace 清 query —— App.vue 用 :key="$route.fullPath"，
  // 清 query 会改变 fullPath 触发组件重建，导致正在进行的流式请求更新到已
  // 销毁的旧实例上，新实例又因为 query 已空不会重新触发，消息就丢了。
  // keep-alive 下同 fullPath 不会重新 mount，所以保留 query 不会重复发送。
  const taskId = route.query.taskId as string | undefined
  const action = route.query.action as string | undefined
  if (taskId && action === 'ai_assist') {
    await sendAiAssist(taskId)
  }
})

// keep-alive 缓存组件切回时滚动到最新消息
onActivated(() => {
  scrollToBottom()
})

async function sendAiAssist(taskId: string) {
  // 立即显示 typing indicator，让用户看到 AI 正在工作，而不是干等网络请求
  const placeholder: Message = {
    role: 'assistant',
    content: '',
    toolCalls: [],
    toolResults: []
  }
  messages.value.push(placeholder)
  isThinking.value = true
  scrollToBottom()

  let msg: string
  try {
    const ctx = await api.get<TaskContext>(`/api/tasks/${taskId}/context`)
    msg = buildAiAssistMessage(ctx)
  } catch (e: any) {
    placeholder.content = `加载任务上下文失败：${e.message || e}`
    isThinking.value = false
    scrollToBottom()
    return
  }

  // 移除占位，交给 sendMessage 处理真正的用户消息 + 流式回复
  messages.value = messages.value.filter(m => m !== placeholder)
  isThinking.value = false
  await sendMessage(msg)
}

function buildAiAssistMessage(ctx: TaskContext): string {
  const lines: string[] = ['[AI 协助请求]']
  lines.push('请帮我分析以下任务该如何处理，并给出具体建议。')
  lines.push('')
  lines.push(`任务标题：${ctx.title}`)
  if (ctx.description) lines.push(`任务描述：${ctx.description}`)
  lines.push('')

  const typeLabel = sourceTypeLabel(ctx.source_type)
  lines.push(`来源类型：${typeLabel}`)

  if (ctx.source_type === 'mail') {
    const m = ctx.source_meta
    lines.push('来源信息：')
    if (m.subject) lines.push(`- 主题：${m.subject}`)
    if (m.sender_name || m.sender_email) {
      lines.push(`- 发件人：${m.sender_name || ''} <${m.sender_email || ''}>`)
    }
    if (m.received_at) lines.push(`- 接收时间：${m.received_at}`)
    if (m.not_found) lines.push('- （原邮件已不在缓存中）')
  } else if (ctx.source_type === 'file') {
    const m = ctx.source_meta
    lines.push('来源信息：')
    if (m.file_name) lines.push(`- 文件名：${m.file_name}`)
    if (typeof m.file_size === 'number') lines.push(`- 文件大小：${m.file_size} 字节`)
    if (m.not_found) lines.push('- （文件不存在或无法访问）')
    if (m.read_error) lines.push(`- 读取错误：${m.read_error}`)
  } else if (ctx.source_type === 'text') {
    const m = ctx.source_meta
    if (typeof m.char_count === 'number') lines.push(`- 字符数：${m.char_count}`)
  }
  lines.push('')
  lines.push('原文内容：')
  const content = ctx.source_content || '(无原文内容)'
  // 截断超长内容，避免撑爆 LLM 上下文
  const MAX = 2000
  const truncated = content.length > MAX
    ? content.slice(0, MAX) + '\n...(内容过长已截断)'
    : content
  lines.push(truncated)
  lines.push('')
  lines.push('请分析这个任务该怎么做，给出具体建议。如果 Manchi 有合适的工具可以直接完成此任务，请告知我可以帮你完成，并等待我的确认后再执行。')
  return lines.join('\n')
}

function sourceTypeLabel(t: string | null | undefined): string {
  if (t === 'mail') return '邮件'
  if (t === 'text') return '文本消息'
  if (t === 'file') return '文件'
  return '未知'
}

function resizeChatInput() {
  const el = chatInputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 140)}px`
}

async function sendMessage(text?: string) {
  // 允许调用方直接传入文本（如 AI 协助预设消息）；不传则取输入框
  const content = (text !== undefined ? text : inputText.value).trim()
  if (!content || isThinking.value) return

  messages.value.push({ role: 'user', content })
  if (text === undefined) {
    inputText.value = ''
    nextTick(resizeChatInput)
  }
  scrollToBottom()

  isThinking.value = true

  const assistantMsg: Message = {
    role: 'assistant',
    content: '',
    toolCalls: [],
    toolResults: []
  }
  messages.value.push(assistantMsg)

  const history = messages.value
    .slice(0, -2)  // exclude current user msg + placeholder assistant
    .map(m => ({ role: m.role, content: m.content }))

  try {
    await streamChat(SESSION_ID, content, history, (evt: ChatEvent) => {
      if (evt.text) {
        assistantMsg.content += evt.text
      } else if (evt.tool_call) {
        assistantMsg.toolCalls!.push({
          name: evt.tool_call.name,
          args: evt.tool_call.args
        })
      } else if (evt.tool_result) {
        assistantMsg.toolResults!.push({
          name: evt.tool_result.name,
          result: evt.tool_result.result
        })
      }
      scrollToBottom()
    })
    if (!assistantMsg.content && (!assistantMsg.toolCalls || assistantMsg.toolCalls.length === 0)) {
      assistantMsg.content = '(无回复)'
    }
  } catch (e: any) {
    assistantMsg.content = `错误: ${e.message}`
  } finally {
    isThinking.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function clearChat() {
  if (isThinking.value) return
  try {
    await api.delete(`/api/chat/history/${SESSION_ID}`)
  } catch {
    // 即使后端删除失败，也清空前端
  }
  messages.value = [
    { role: 'assistant', content: WELCOME }
  ]
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bg-primary);
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-row {
  display: flex;
  gap: 12px;
  max-width: 720px;
}

.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.message-row.assistant .message-avatar {
  background: var(--accent-gradient);
  color: white;
}

.message-row.user .message-avatar {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  padding: 12px 16px;
  border-radius: 12px;
}

.message-row.assistant .message-text {
  background: var(--bg-surface);
  border-bottom-left-radius: 4px;
}

.message-row.user .message-text {
  background: var(--accent-glow);
  color: var(--accent);
  border-bottom-right-radius: 4px;
}

/* Markdown rendering inside message-text */
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4) {
  margin: 12px 0 8px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary);
}

.message-text :deep(h1) { font-size: 18px; }
.message-text :deep(h2) { font-size: 16px; }
.message-text :deep(h3) { font-size: 15px; }
.message-text :deep(h4) { font-size: 14px; }

.message-text :deep(p) {
  margin: 8px 0;
  line-height: 1.6;
}

.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.message-text :deep(li) {
  margin: 4px 0;
  line-height: 1.5;
}

.message-text :deep(ul) { list-style: disc; }
.message-text :deep(ol) { list-style: decimal; }

.message-text :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-elevated);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent);
}

.message-text :deep(pre) {
  margin: 8px 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  overflow-x: auto;
}

.message-text :deep(pre code) {
  padding: 0;
  background: none;
  color: var(--text-primary);
  font-size: 12px;
}

.message-text :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid var(--accent);
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.message-text :deep(table) {
  margin: 8px 0;
  border-collapse: collapse;
  width: 100%;
}

.message-text :deep(th),
.message-text :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--border);
  text-align: left;
  font-size: 12px;
}

.message-text :deep(th) {
  background: var(--bg-elevated);
  font-weight: 600;
}

.message-text :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

.message-text :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid var(--border);
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 16px;
  align-items: center;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typing 1.4s infinite both;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-4px); }
}

/* Tool call / result bubbles */
.tool-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  margin-bottom: 8px;
  border-radius: 999px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
  transition: all var(--transition-base);
}

.tool-summary:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.tool-summary-icon {
  font-size: 12px;
}

.tool-summary-toggle {
  margin-left: 4px;
  font-size: 10px;
  opacity: 0.7;
}

.tool-calls,
.tool-results {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.tool-bubble {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  border: 1px solid var(--border);
  max-width: 100%;
}

.tool-call-bubble {
  background: rgba(79, 195, 247, 0.08);
  border-color: rgba(79, 195, 247, 0.25);
}

.tool-result-bubble {
  background: var(--bg-elevated);
  flex-direction: column;
}

.tool-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.tool-call-bubble .tool-tag {
  background: rgba(79, 195, 247, 0.2);
  color: var(--accent);
}

.tool-result-bubble .tool-tag {
  background: rgba(34, 197, 94, 0.15);
  color: #22C55E;
}

.tool-name {
  color: var(--text-primary);
  font-weight: 600;
  flex-shrink: 0;
}

.tool-args {
  color: var(--text-muted);
  word-break: break-all;
  flex: 1;
  min-width: 0;
}

.tool-result-content {
  margin: 4px 0 0;
  padding: 0;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

/* Input */
.chat-input-area {
  padding: 20px 40px 28px;
  border-top: 1px solid var(--border);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 4px;
  max-width: 720px;
  margin: 0 auto;
  transition: border-color var(--transition-base);
}

.input-wrapper:focus-within {
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}

.chat-input {
  flex: 1;
  padding: 10px 16px;
  min-height: 40px;
  max-height: 140px;
  background: none;
  border: none;
  outline: none;
  font-size: 14px;
  line-height: 20px;
  color: var(--text-primary);
  font-family: var(--font-sans);
  resize: none;
  overflow-y: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  transition: all var(--transition-base);
}

.send-btn:hover:not(:disabled) {
  background: var(--accent);
  color: var(--bg-primary);
}

.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.clear-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-base);
}

.clear-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.15);
  color: #EF4444;
}

.clear-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>