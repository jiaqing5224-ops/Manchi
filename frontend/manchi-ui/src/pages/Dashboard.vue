<template>
  <div class="dashboard">
    <!-- Welcome Section -->
    <section class="welcome-section" ref="welcomeRef">
      <h1 class="welcome-title">
        <span class="title-line">
          <span class="title-accent">Manchi</span>
          <span class="inline-image" :style="{ backgroundImage: 'url(https://picsum.photos/seed/manchi-ai/1920/1080?grayscale)' }"></span>
          <span>已就绪</span>
        </span>
      </h1>
      <p class="welcome-subtitle">今天有 <strong>{{ todoCount }}</strong> 个待办任务 · <strong>{{ unreadCount }}</strong> 封未读邮件</p>
    </section>

    <!-- Bento Grid -->
    <section class="bento-grid" ref="bentoRef">
      <!-- Card 1: Task Overview -->
      <div class="bento-card card-tasks" @click="$router.push('/tasks')">
        <div class="card-header">
          <span class="card-label">今日概览<span v-if="isPlaceholder" class="sample-tag">示例</span></span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        </div>
        <div class="card-body">
          <div class="stat-row">
            <div class="stat-item">
              <span class="stat-value">{{ todoCount }}</span>
              <span class="stat-label">待办</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ inProgressCount }}</span>
              <span class="stat-label">进行中</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ doneCount }}</span>
              <span class="stat-label">已完成</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ weekNewTaskCount }}</span>
              <span class="stat-label">本周新增</span>
            </div>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: completionRate + '%' }"></div>
          </div>
          <span class="progress-text">完成率 {{ completionRate }}%</span>
        </div>
      </div>

      <!-- Card 2: Mail Insight -->
      <div class="bento-card card-mail" @click="$router.push('/mail')">
        <div class="card-header">
          <span class="card-label">最近邮件</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
        </div>
        <div class="card-body">
          <div class="mail-preview-list">
            <div v-for="mail in recentMails" :key="mail.id" class="mail-item">
              <div class="mail-sender">{{ mail.sender_email }}</div>
              <div class="mail-subject">{{ mail.subject }}</div>
            </div>
            <div v-if="recentMails.length === 0" class="mail-empty-text">暂无邮件，去邮箱扫描</div>
          </div>
        </div>
      </div>

      <!-- Card 3: Quick Actions -->
      <div class="bento-card card-actions">
        <div class="card-header">
          <span class="card-label">快捷操作</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
        </div>
        <div class="card-body">
          <button class="action-btn" @click="quickScan">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            扫描邮件
          </button>
          <button class="action-btn" @click="$router.push('/orch')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
            启动自动化
          </button>
          <button class="action-btn" @click="$router.push('/chat')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            开始对话
          </button>
        </div>
      </div>

      <!-- Card 4: AI Chat Quick Entry -->
      <div class="bento-card card-chat" @click="$router.push('/chat')">
        <div class="card-header">
          <span class="card-label">AI 快捷对话</span>
          <span class="card-badge">DeepSeek</span>
        </div>
        <div class="card-body">
          <div class="chat-preview">
            <div class="chat-bubble bot">你好！我是 Manchi，有什么可以帮助你的？</div>
            <div class="chat-input-line">
              <span class="chat-prompt">&gt; 输入消息开始对话...</span>
              <span class="chat-cursor"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 5: Priority Focus -->
      <div class="bento-card card-priority" @click="$router.push('/tasks')">
        <div class="card-header">
          <span class="card-label">优先级聚焦</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        </div>
        <div class="card-body">
          <div class="priority-list">
            <div v-for="task in topPriorityTasks" :key="task.id" class="priority-item">
              <span class="priority-dot" :class="task.priority"></span>
              <span class="priority-title">{{ task.title }}</span>
              <span class="priority-tag">{{ task.priority }}</span>
            </div>
            <div v-if="topPriorityTasks.length === 0" class="priority-empty">暂无待办任务</div>
          </div>
        </div>
      </div>

      <!-- Card 6: Meeting Report -->
      <div class="bento-card card-meeting">
        <div class="card-header">
          <span class="card-label">本周会议报告</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>
        </div>
        <div class="card-body">
          <div class="meeting-info">
            <p class="meeting-desc">自动扫描本周一至周五的会议邮件，AI 提取会议时间，汇总为 Excel 表格并保存到专属产物目录。</p>
            <div class="meeting-actions">
              <button class="action-btn meeting-btn" :disabled="generatingReport" @click="generateMeetingReport">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                <span>{{ generatingReport ? '生成中...' : '生成本周会议 Excel' }}</span>
              </button>
              <button class="action-btn meeting-folder-btn" @click="openExportsDir">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <span>打开产物目录</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Infinite Marquee -->
    <section class="marquee-section">
      <div class="marquee-track">
        <div class="marquee-content">
          <span v-for="i in 6" :key="i" class="marquee-tag">Outlook 集成</span>
          <span v-for="i in 6" :key="'b'+i" class="marquee-tag">AI 智能分析</span>
          <span v-for="i in 6" :key="'c'+i" class="marquee-tag">自动任务编排</span>
          <span v-for="i in 6" :key="'d'+i" class="marquee-tag">本地安全执行</span>
          <span v-for="i in 6" :key="'e'+i" class="marquee-tag">Outlook 集成</span>
          <span v-for="i in 6" :key="'f'+i" class="marquee-tag">AI 智能分析</span>
          <span v-for="i in 6" :key="'g'+i" class="marquee-tag">自动任务编排</span>
          <span v-for="i in 6" :key="'h'+i" class="marquee-tag">本地安全执行</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '@/utils/api'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const welcomeRef = ref<HTMLElement | null>(null)
const bentoRef = ref<HTMLElement | null>(null)

interface TaskItem {
  id: number
  title: string
  priority: string
  status: string
  created_at?: string
  due_date?: string | null
  description?: string
}

interface MailItem {
  id: string
  subject: string
  sender_name: string
  sender_email: string
  is_read: boolean
}

interface MeetingReportResult {
  path: string
  count: number
}

const CACHE_TASKS = 'manchi_dash_tasks'
const CACHE_MAILS = 'manchi_dash_mails'

const PLACEHOLDER_TASKS: TaskItem[] = [
  { id: -1, title: '示例：整理本周会议纪要', priority: 'high', status: 'todo', created_at: '' },
  { id: -2, title: '示例：回复客户邮件', priority: 'medium', status: 'in_progress', created_at: '' },
  { id: -3, title: '示例：完成需求文档', priority: 'medium', status: 'todo', created_at: '' },
  { id: -4, title: '示例：周报提交', priority: 'low', status: 'done', created_at: '' }
]

const PLACEHOLDER_MAILS: MailItem[] = [
  { id: 's1', subject: '示例：项目周会邀请', sender_name: '张三', sender_email: 'zhangsan@example.com', is_read: false },
  { id: 's2', subject: '示例：需求评审通知', sender_name: '李四', sender_email: 'lisi@example.com', is_read: false },
  { id: 's3', subject: '示例：版本发布确认', sender_name: '王五', sender_email: 'wangwu@example.com', is_read: true }
]

const PRIORITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

const tasks = ref<TaskItem[]>([])
const mails = ref<MailItem[]>([])
const isPlaceholder = ref(false)
const generatingReport = ref(false)

const todoCount = computed(() => tasks.value.filter(t => t.status === 'todo').length)
const inProgressCount = computed(() => tasks.value.filter(t => t.status === 'in_progress').length)
const doneCount = computed(() => tasks.value.filter(t => t.status === 'done').length)
const totalCount = computed(() => tasks.value.length)
const completionRate = computed(() => totalCount.value ? Math.round(doneCount.value / totalCount.value * 100) : 0)
const unreadCount = computed(() => mails.value.filter(m => !m.is_read).length)
const recentMails = computed(() => mails.value.slice(0, 3))

const weekNewTaskCount = computed(() => {
  const now = new Date()
  const dayOfWeek = now.getDay() || 7
  const monday = new Date(now)
  monday.setHours(0, 0, 0, 0)
  monday.setDate(now.getDate() - dayOfWeek + 1)
  return tasks.value.filter(t => {
    if (!t.created_at) return false
    const created = new Date(t.created_at)
    return !isNaN(created.getTime()) && created >= monday
  }).length
})

const topPriorityTasks = computed(() => {
  return [...tasks.value]
    .filter(t => t.status !== 'done')
    .sort((a, b) => {
      const pa = PRIORITY_ORDER[a.priority] ?? 3
      const pb = PRIORITY_ORDER[b.priority] ?? 3
      return pa - pb
    })
    .slice(0, 3)
})

async function withRetry<T>(fn: () => Promise<T>, times = 2): Promise<T> {
  let lastErr: unknown
  for (let i = 0; i < times; i++) {
    try {
      return await fn()
    } catch (e) {
      lastErr = e
    }
  }
  throw lastErr
}

function readCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : null
  } catch {
    return null
  }
}

function writeCache<T>(key: string, val: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(val))
  } catch {
    // ignore quota errors
  }
}

async function loadTasks() {
  try {
    const data = await withRetry(() => api.get<TaskItem[]>('/api/tasks'))
    tasks.value = data
    isPlaceholder.value = false
    writeCache(CACHE_TASKS, data)
  } catch {
    const cached = readCache<TaskItem[]>(CACHE_TASKS)
    if (cached && cached.length > 0) {
      tasks.value = cached
      isPlaceholder.value = false
    } else {
      tasks.value = PLACEHOLDER_TASKS
      isPlaceholder.value = true
    }
  }
}

async function loadMails() {
  try {
    const data = await withRetry(() => api.get<MailItem[]>('/api/mail?limit=10'))
    mails.value = data
    writeCache(CACHE_MAILS, data)
  } catch {
    const cached = readCache<MailItem[]>(CACHE_MAILS)
    if (cached && cached.length > 0) {
      mails.value = cached
    } else {
      mails.value = PLACEHOLDER_MAILS
      isPlaceholder.value = true
    }
  }
}

async function generateMeetingReport() {
  if (generatingReport.value) return
  generatingReport.value = true
  appStore.setTrayStatus('processing')
  try {
    const result = await api.post<MeetingReportResult>('/api/meeting/report', {})
    alert(`会议报告已生成：\n${result.path}\n共 ${result.count} 场会议`)
    appStore.setTrayStatus('newMail')
    setTimeout(() => appStore.setTrayStatus('idle'), 5000)
  } catch (e) {
    alert('生成会议报告失败：' + (e as Error).message)
    appStore.setTrayStatus('idle')
  } finally {
    generatingReport.value = false
  }
}

async function openExportsDir() {
  try {
    await api.post('/api/meeting/open-exports', {})
  } catch (e) {
    alert('打开目录失败：' + (e as Error).message)
  }
}

onMounted(async () => {
  await Promise.allSettled([loadTasks(), loadMails()])
})

// 切换路由到首页时自动刷新
watch(
  () => route.path,
  (path) => {
    if (path === '/') {
      Promise.allSettled([loadTasks(), loadMails()])
    }
  }
)

async function quickScan() {
  appStore.setTrayStatus('processing')
  try {
    await api.post('/api/mail/scan', {})
    await loadMails()
    appStore.setTrayStatus('newMail')
    setTimeout(() => appStore.setTrayStatus('idle'), 5000)
  } catch {
    appStore.setTrayStatus('idle')
  }
}
</script>

<style scoped>
.dashboard {
  padding: 40px 48px 48px;
  height: 100%;
  overflow-y: auto;
}

.welcome-section {
  margin-bottom: 48px;
  animation: fadeInUp 0.6s ease-out both;
}

.bento-card {
  animation: fadeInUp 0.6s ease-out both;
}

.bento-card:nth-child(1) { animation-delay: 0.05s; }
.bento-card:nth-child(2) { animation-delay: 0.1s; }
.bento-card:nth-child(3) { animation-delay: 0.15s; }
.bento-card:nth-child(4) { animation-delay: 0.2s; }
.bento-card:nth-child(5) { animation-delay: 0.25s; }
.bento-card:nth-child(6) { animation-delay: 0.3s; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.welcome-title {
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 3.5vw, 3.2rem);
  font-weight: 700;
  line-height: 1.15;
  color: var(--text-primary);
}

.title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title-accent {
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.inline-image {
  display: inline-block;
  width: 40px;
  height: 28px;
  border-radius: 999px;
  background-size: cover;
  background-position: center;
  vertical-align: middle;
  filter: grayscale(0.6) contrast(1.2);
  mix-blend-mode: luminosity;
  opacity: 0.8;
}

.welcome-subtitle {
  margin-top: 12px;
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
}

.welcome-subtitle strong {
  color: var(--text-primary);
  font-weight: 600;
}

.bento-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  grid-auto-flow: dense;
  margin-bottom: 48px;
}

.bento-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.bento-card:hover {
  border-color: var(--border-hover);
  background: var(--bg-elevated);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.card-tasks {
  grid-column: span 2;
}

.card-mail {
  grid-column: span 1;
}

.card-actions {
  grid-column: span 1;
}

.card-chat {
  grid-column: span 2;
}

.card-priority {
  grid-column: span 1;
}

.card-meeting {
  grid-column: span 2;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-muted);
}

.card-header svg {
  color: var(--text-muted);
  opacity: 0.5;
}

.card-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-glow);
  color: var(--accent);
  letter-spacing: 0.5px;
}

.stat-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--accent-gradient);
  transition: width 1s ease;
}

.progress-text {
  font-size: 11px;
  color: var(--text-muted);
}

.mail-preview-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mail-item {
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.mail-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.mail-empty-text {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.mail-sender {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.mail-subject {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
  transition: all var(--transition-base);
}

.action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.action-btn svg {
  flex-shrink: 0;
}

.chat-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 80%;
}

.chat-bubble.bot {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border-bottom-left-radius: 4px;
}

.chat-input-line {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0;
}

.chat-prompt {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.chat-cursor {
  width: 6px;
  height: 14px;
  background: var(--accent);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.sample-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  letter-spacing: 0.5px;
  vertical-align: middle;
}

.priority-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.priority-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.priority-item:last-child {
  border-bottom: none;
}

.priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--text-muted);
}

.priority-dot.high {
  background: #ff6b6b;
  box-shadow: 0 0 6px rgba(255, 107, 107, 0.4);
}

.priority-dot.medium {
  background: #ffb84d;
}

.priority-dot.low {
  background: #4dd599;
}

.priority-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.priority-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.priority-empty {
  font-size: 13px;
  color: var(--text-muted);
  padding: 12px 0;
  text-align: center;
}

.meeting-info {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.meeting-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.meeting-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.meeting-btn {
  align-self: flex-start;
  background: var(--accent-glow);
  color: var(--accent);
  font-weight: 600;
  border: 1px solid var(--accent);
}

.meeting-btn:hover:not(:disabled) {
  background: var(--accent);
  color: var(--bg-surface);
}

.meeting-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.meeting-folder-btn {
  align-self: flex-start;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.meeting-folder-btn:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
}

.marquee-section {
  overflow: hidden;
}

.marquee-track {
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, black 5%, black 95%, transparent);
}

.marquee-content {
  display: flex;
  gap: 12px;
  animation: marquee 30s linear infinite;
  width: max-content;
}

.marquee-tag {
  flex-shrink: 0;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  border: 1px solid var(--border);
  white-space: nowrap;
}

@keyframes marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
</style>