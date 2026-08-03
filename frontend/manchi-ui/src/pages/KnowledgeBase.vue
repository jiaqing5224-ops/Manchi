<template>
  <div class="kb-page">
    <!-- Top Control Bar -->
    <div class="kb-toolbar">
      <div class="toolbar-left">
        <h2 class="page-title">知识库</h2>
        <span class="kb-summary">沉淀自任务的知识卡片，点击可跳转到对应任务</span>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-ghost" @click="goTasks">去任务中心生成知识</button>
        <button class="btn btn-primary" :disabled="isLoading" @click="loadKnowledge">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.5 0 4.8 1 6.4 2.6"/><path d="M21 3v6h-6"/></svg>
          {{ isLoading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Knowledge list -->
    <div class="kb-body">
      <div v-if="knowledge.length === 0 && !isLoading" class="kb-empty">
        <p>暂无沉淀，去任务中心为任务生成知识</p>
        <button class="btn btn-primary sm" @click="goTasks">去任务中心</button>
      </div>
      <div v-else class="kb-list">
        <div
          v-for="k in knowledge"
          :id="'kb-' + k.id"
          :key="k.id"
          class="kb-card"
          :class="{ highlight: highlightId === k.id }"
          @click="openTask(k)"
        >
          <div class="kb-card-head">
            <span class="kb-task-title">{{ k.task_title || '(任务已删除)' }}</span>
            <div class="kb-tags">
              <span v-if="k.status" class="kb-tag" :class="'tag-' + k.status">{{ statusLabel(k.status) }}</span>
              <span v-if="k.priority" class="kb-tag" :class="'tag-' + k.priority">{{ priorityLabel(k.priority) }}</span>
              <span v-if="k.source_type" class="kb-tag kb-source">{{ sourceLabel(k.source_type) }}</span>
            </div>
          </div>
          <div class="kb-summary">{{ preview(k.summary) }}</div>
          <div class="kb-foot">
            <span class="kb-date">{{ formatDate(k.created_at) }}</span>
            <span class="kb-go">查看任务 ›</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/utils/api'

const route = useRoute()
const router = useRouter()

interface KnowledgeItem {
  id: number
  task_id: number
  summary: string
  created_at: string
  updated_at: string
  task_title: string
  priority: string | null
  status: string | null
  source_type: string | null
  source_mail_id: string | null
}

const knowledge = ref<KnowledgeItem[]>([])
const isLoading = ref(false)
const highlightId = ref<number | null>(null)

const statusMap: Record<string, string> = {
  todo: '待办',
  in_progress: '进行中',
  done: '已完成'
}
const priorityMap: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低'
}
const sourceMap: Record<string, string> = {
  mail: '📧 邮件',
  text: '📝 文本',
  file: '📁 文件'
}

function statusLabel(s: string): string {
  return statusMap[s] || s
}
function priorityLabel(p: string): string {
  return priorityMap[p] || p
}
function sourceLabel(s: string): string {
  return sourceMap[s] || s
}

onMounted(async () => {
  await loadKnowledge()
  const kid = route.query.knowledgeId
  if (kid) {
    highlightId.value = Number(kid)
    setTimeout(() => {
      const el = document.getElementById('kb-' + kid)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 200)
  }
})

async function loadKnowledge() {
  isLoading.value = true
  try {
    knowledge.value = await api.get<KnowledgeItem[]>('/api/knowledge')
  } catch {
    knowledge.value = []
  } finally {
    isLoading.value = false
  }
}

function preview(text: string): string {
  const plain = text.replace(/[#*>\-]/g, '').replace(/\n+/g, ' ').trim()
  return plain.length > 160 ? plain.slice(0, 160) + '…' : plain
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function openTask(k: KnowledgeItem) {
  router.push({ path: '/tasks', query: { taskId: String(k.task_id) } })
}

function goTasks() {
  router.push('/tasks')
}
</script>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.kb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 32px 16px;
  border-bottom: 1px solid var(--border);
}

.toolbar-left {
  display: flex;
  align-items: baseline;
  gap: 14px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-summary {
  font-size: 12px;
  color: var(--text-muted);
}

.toolbar-right {
  display: flex;
  gap: 8px;
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
  cursor: pointer;
}

.btn.sm {
  padding: 5px 14px;
  font-size: 12px;
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

.btn-ghost:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.kb-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 32px 32px;
}

.kb-empty {
  padding: 80px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kb-card {
  padding: 16px 18px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
}

.kb-card:hover {
  border-color: var(--accent);
}

.kb-card.highlight {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(79, 195, 247, 0.25);
}

.kb-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.kb-task-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-tags {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.kb-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tag-todo { background: rgba(234, 179, 8, 0.12); color: #EAB308; }
.tag-in_progress { background: rgba(59, 130, 246, 0.12); color: #3B82F6; }
.tag-done { background: rgba(34, 197, 94, 0.12); color: #22C55E; }
.tag-high { background: rgba(239, 68, 68, 0.12); color: #EF4444; }
.tag-medium { background: rgba(234, 179, 8, 0.12); color: #EAB308; }
.tag-low { background: rgba(34, 197, 94, 0.12); color: #22C55E; }

.kb-source {
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.kb-summary {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.kb-date {
  font-size: 11px;
  color: var(--text-muted);
}

.kb-go {
  font-size: 12px;
  color: var(--accent);
}
</style>
