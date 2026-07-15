<template>
  <div class="mail-page">
    <!-- Top Control Bar -->
    <div class="mail-toolbar">
      <div class="toolbar-left">
        <h2 class="page-title">邮件助手</h2>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-primary" :disabled="isScanning" @click="startScan">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          {{ isScanning ? '扫描中...' : '扫描邮件' }}
        </button>
        <button class="btn btn-ghost" :disabled="!selectedMail" @click="analyzeMail">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          AI 分析
        </button>
      </div>
    </div>

    <!-- Mail Split View -->
    <div class="mail-split">
      <!-- Mail List -->
      <div class="mail-list-panel">
        <div class="mail-list-header">
          <span class="list-title">收件箱</span>
          <span class="list-count">{{ mails.length }}</span>
        </div>
        <div class="mail-list">
          <div
            v-for="mail in mails"
            :key="mail.id"
            class="mail-list-item"
            :class="{ selected: selectedMail?.id === mail.id, unread: !mail.is_read }"
            @click="selectMail(mail)"
          >
            <div class="mail-avatar">{{ mail.sender_name.charAt(0) }}{{ mail.sender_name.charAt(1) }}</div>
            <div class="mail-info">
              <div class="mail-meta">
                <span class="mail-from">{{ mail.sender_name }}</span>
                <span class="mail-time">{{ formatTime(mail.received_at) }}</span>
              </div>
              <div class="mail-subj">{{ mail.subject }}</div>
              <div class="mail-prev">{{ mail.body_preview?.slice(0, 60) }}</div>
            </div>
          </div>
          <div v-if="mails.length === 0" class="mail-empty">
            <p>暂无邮件，点击"扫描邮件"从 Outlook 获取</p>
          </div>
        </div>
      </div>

      <!-- Mail Detail -->
      <div class="mail-detail-panel">
        <div class="detail-placeholder" v-if="!selectedMail">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          <p>选择一封邮件查看详情</p>
        </div>
        <div v-else class="mail-detail">
          <div class="detail-header">
            <h3 class="detail-subject">{{ selectedMail.subject }}</h3>
            <div class="detail-meta">
              <span class="detail-sender">{{ selectedMail.sender_name }} &lt;{{ selectedMail.sender_email }}&gt;</span>
              <span class="detail-time">{{ formatTime(selectedMail.received_at) }}</span>
            </div>
          </div>
          <div class="detail-body">
            <p class="detail-content">{{ fullMailBody || selectedMail.body_preview }}</p>
          </div>
          <div v-if="generatedTasks.length > 0" class="detail-tasks">
            <h4 class="tasks-title">AI 生成任务</h4>
            <div v-for="(task, i) in generatedTasks" :key="i" class="task-chip" :class="`priority-${task.priority}`">
              <span class="task-dot"></span>
              {{ task.title }}
            </div>
          </div>
          <div v-if="isAnalyzing" class="analyzing-badge">
            <span class="analyzing-dot"></span>
            AI 分析中...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/utils/api'
import { useAppStore } from '@/stores/app'

const route = useRoute()

interface MailItem {
  id: string
  subject: string
  sender_name: string
  sender_email: string
  body_preview: string
  received_at: string | null
  is_read: boolean
  is_processed: boolean
}

interface AiTask {
  title: string
  description: string
  priority: string
}

interface AnalyzeResult {
  mail_id: string
  tasks: AiTask[]
}

interface ScanResult {
  scanned: number
  total: number
  tasks_created?: number
  analysis_failed?: number
}

const appStore = useAppStore()
const isScanning = ref(false)
const mails = ref<MailItem[]>([])
const selectedMail = ref<MailItem | null>(null)
const fullMailBody = ref('')
const generatedTasks = ref<AiTask[]>([])
const isAnalyzing = ref(false)

onMounted(async () => {
  await loadMails()
  // 如果 URL 携带 mailId 参数，自动选中对应邮件
  const mailId = route.query.mailId as string | undefined
  if (mailId) {
    const found = mails.value.find(m => m.id === mailId)
    if (found) {
      await selectMail(found)
    } else {
      // 邮件可能不在前 50 条中，直接尝试获取详情
      try {
        const detail = await api.get<MailItem>(`/api/mail/${encodeURIComponent(mailId)}`)
        selectedMail.value = detail
        fullMailBody.value = detail.body_preview
      } catch {
        // not found
      }
    }
  }
})

async function loadMails() {
  try {
    mails.value = await api.get<MailItem[]>('/api/mail?limit=50')
  } catch {
    // silently fail
  }
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

async function startScan() {
  isScanning.value = true
  appStore.setTrayStatus('processing')
  try {
    const result = await api.post<ScanResult>('/api/mail/scan', {})
    await loadMails()
    appStore.setTrayStatus('newMail')
    setTimeout(() => appStore.setTrayStatus('idle'), 5000)
    const taskText = result.tasks_created === undefined ? '' : `，生成 ${result.tasks_created} 个 Task`
    const failedText = result.analysis_failed ? `，${result.analysis_failed} 封邮件分析失败` : ''
    alert(`扫描完成: 新增 ${result.scanned} 封，共 ${result.total} 封${taskText}${failedText}`)
  } catch (e: any) {
    alert('扫描失败: ' + e.message)
    appStore.setTrayStatus('idle')
  } finally {
    isScanning.value = false
  }
}

async function selectMail(mail: MailItem) {
  selectedMail.value = mail
  fullMailBody.value = ''
  generatedTasks.value = []

  try {
    const detail = await api.get<MailItem>(`/api/mail/${encodeURIComponent(mail.id)}`)
    fullMailBody.value = detail.body_preview
  } catch {
    // keep preview
  }
}

async function analyzeMail() {
  if (!selectedMail.value) return
  isAnalyzing.value = true
  generatedTasks.value = []
  try {
    const result = await api.post<AnalyzeResult>(`/api/mail/${encodeURIComponent(selectedMail.value.id)}/analyze`, {})
    generatedTasks.value = result.tasks
  } catch (e: any) {
    alert('AI 分析失败: ' + e.message)
  } finally {
    isAnalyzing.value = false
  }
}
</script>

<style scoped>
.mail-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.mail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 32px 16px;
  border-bottom: 1px solid var(--border);
}

.page-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}

.btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-base);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-primary);
}

.btn-primary:hover {
  box-shadow: var(--shadow-glow);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-ghost:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Split View */
.mail-split {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.mail-list-panel {
  width: 340px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.mail-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 8px;
}

.list-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
}

.list-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 2px 8px;
  border-radius: 999px;
}

.mail-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px;
}

.mail-empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.mail-list-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
}

.mail-list-item:hover {
  background: var(--bg-hover);
}

.mail-list-item.selected {
  background: var(--accent-glow);
}

.mail-list-item.unread {
  border-left: 2px solid var(--accent);
}

.mail-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.mail-info {
  flex: 1;
  min-width: 0;
}

.mail-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
}

.mail-from {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.mail-time {
  font-size: 11px;
  color: var(--text-muted);
}

.mail-subj {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mail-prev {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Detail */
.mail-detail-panel {
  flex: 1;
  display: flex;
  overflow-y: auto;
}

.detail-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  gap: 12px;
  color: var(--text-muted);
  font-size: 14px;
}

.mail-detail {
  padding: 32px;
  width: 100%;
}

.detail-header {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.detail-subject {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.detail-meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.detail-sender {
  color: var(--text-secondary);
}

.detail-time {
  color: var(--text-muted);
}

.detail-body {
  margin-bottom: 24px;
}

.detail-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.detail-tasks {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
}

.tasks-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.task-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-primary);
  padding: 6px 0;
}

.task-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.priority-high .task-dot { background: #EF4444; }
.priority-medium .task-dot { background: #EAB308; }
.priority-low .task-dot { background: #22C55E; }

.analyzing-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--accent-glow);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--accent);
  margin-top: 16px;
}

.analyzing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.4s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
</style>