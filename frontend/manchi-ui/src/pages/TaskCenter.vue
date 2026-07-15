<template>
  <div class="tasks-page">
    <div class="page-header">
      <h2 class="page-title">任务中心</h2>
      <div class="header-actions">
        <button class="btn btn-ghost" @click="showCreateDialog = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
          新建任务
        </button>
      </div>
    </div>

    <!-- Kanban Board -->
    <div class="kanban-board">
      <div v-for="col in columns" :key="col.key" class="kanban-column">
        <div class="column-header">
          <span class="column-title">{{ col.title }}</span>
          <span class="column-count">{{ col.tasks.length }}</span>
        </div>
        <div
          class="column-body"
          @dragover.prevent
          @drop.prevent="onDrop(col.key, null)"
          @contextmenu.prevent="onColumnContextMenu($event, col.key)"
        >
          <!-- Done column: directory groups + ungrouped tasks -->
          <template v-if="col.key === 'done'">
            <div
              v-for="g in doneGroups"
              :key="'g' + g.group.id"
              class="task-group"
              :class="{ 'drag-over': dragOverGroupId === g.group.id }"
              @dragover.prevent="dragOverGroupId = g.group.id"
              @dragleave.prevent="dragOverGroupId = null"
              @drop.prevent.stop="onDrop('done', g.group.id)"
            >
              <div
                class="group-header"
                @click="toggleGroup(g.group.id)"
                @contextmenu.prevent.stop="onGroupContextMenu($event, g.group)"
              >
                <svg
                  class="group-chevron"
                  :class="{ collapsed: collapsedGroups.has(g.group.id) }"
                  width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                ><polyline points="6 9 12 15 18 9"/></svg>
                <span class="group-name">{{ g.group.name }}</span>
                <span class="group-count">{{ g.tasks.length }}</span>
              </div>
              <div v-show="!collapsedGroups.has(g.group.id)" class="group-tasks">
                <div
                  v-for="task in g.tasks"
                  :key="task.id"
                  class="task-card"
                  :class="[`status-${task.status}`]"
                  draggable="true"
                  @dragstart="onDragStart(task)"
                  @dblclick="editTask(task)"
                  @contextmenu.prevent.stop="onContextMenu($event, task)"
                >
                  <div class="task-priority" :class="`priority-${task.priority}`"></div>
                  <div class="task-content">
                    <div class="task-title">{{ task.title }}</div>
                    <div class="task-meta">
                      <span class="task-tag" :class="`tag-${task.status}`">{{ statusLabel(task.status) }}</span>
                      <span class="task-tag" :class="`tag-${task.priority}`">{{ priorityLabel(task.priority) }}</span>
                      <span v-if="task.source_mail_id" class="task-mail-link" title="来自邮件">📧</span>
                      <span class="task-date">{{ task.due_date ? formatDate(task.due_date) : '' }}</span>
                    </div>
                  </div>
                  <button class="task-delete" @click.stop="deleteTask(task)" title="删除">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                </div>
              </div>
            </div>
            <!-- Ungrouped done tasks -->
            <div
              v-for="task in doneUngrouped"
              :key="task.id"
              class="task-card"
              :class="[`status-${task.status}`]"
              draggable="true"
              @dragstart="onDragStart(task)"
              @dblclick="editTask(task)"
              @contextmenu.prevent.stop="onContextMenu($event, task)"
            >
              <div class="task-priority" :class="`priority-${task.priority}`"></div>
              <div class="task-content">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <span class="task-tag" :class="`tag-${task.status}`">{{ statusLabel(task.status) }}</span>
                  <span class="task-tag" :class="`tag-${task.priority}`">{{ priorityLabel(task.priority) }}</span>
                  <span v-if="task.source_mail_id" class="task-mail-link" title="来自邮件">📧</span>
                  <span class="task-date">{{ task.due_date ? formatDate(task.due_date) : '' }}</span>
                </div>
              </div>
              <button class="task-delete" @click.stop="deleteTask(task)" title="删除">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </template>
          <!-- Other columns: flat task list -->
          <template v-else>
            <div
              v-for="task in col.tasks"
              :key="task.id"
              class="task-card"
              :class="[`status-${task.status}`]"
              draggable="true"
              @dragstart="onDragStart(task)"
              @dblclick="editTask(task)"
              @contextmenu.prevent.stop="onContextMenu($event, task)"
            >
              <div class="task-priority" :class="`priority-${task.priority}`"></div>
              <div class="task-content">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <span class="task-tag" :class="`tag-${task.status}`">{{ statusLabel(task.status) }}</span>
                  <span class="task-tag" :class="`tag-${task.priority}`">{{ priorityLabel(task.priority) }}</span>
                  <span v-if="task.source_mail_id" class="task-mail-link" title="来自邮件">📧</span>
                  <span class="task-date">{{ task.due_date ? formatDate(task.due_date) : '' }}</span>
                </div>
              </div>
              <button class="task-delete" @click.stop="deleteTask(task)" title="删除">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Create Dialog -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog">
        <h3 class="dialog-title">新建任务</h3>
        <div class="dialog-body">
          <label class="dialog-label">标题</label>
          <input class="dialog-input" v-model="newTaskForm.title" placeholder="任务标题" />
          <label class="dialog-label">描述</label>
          <textarea class="dialog-textarea" v-model="newTaskForm.description" placeholder="任务描述"></textarea>
          <label class="dialog-label">优先级</label>
          <select class="dialog-select" v-model="newTaskForm.priority">
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="showCreateDialog = false">取消</button>
          <button class="btn btn-primary" @click="createTask" :disabled="!newTaskForm.title.trim()">创建</button>
        </div>
      </div>
    </div>

    <!-- Edit Dialog -->
    <div v-if="showEditDialog" class="dialog-overlay" @click.self="showEditDialog = false">
      <div class="dialog">
        <h3 class="dialog-title">编辑任务</h3>
        <div class="dialog-body">
          <label class="dialog-label">标题</label>
          <input class="dialog-input" v-model="editForm.title" placeholder="任务标题" />
          <label class="dialog-label">描述</label>
          <textarea class="dialog-textarea" v-model="editForm.description" placeholder="任务描述"></textarea>
          <label class="dialog-label">优先级</label>
          <select class="dialog-select" v-model="editForm.priority">
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
          <label class="dialog-label">状态</label>
          <select class="dialog-select" v-model="editForm.status">
            <option value="todo">待办</option>
            <option value="in_progress">进行中</option>
            <option value="done">已完成</option>
          </select>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="showEditDialog = false">取消</button>
          <button class="btn btn-primary" @click="saveEditTask" :disabled="!editForm.title.trim()">保存</button>
        </div>
      </div>
    </div>

    <!-- View Source Text Dialog -->
    <div v-if="showSourceDialog" class="dialog-overlay" @click.self="showSourceDialog = false">
      <div class="dialog dialog-wide">
        <h3 class="dialog-title">原文内容</h3>
        <div class="dialog-body">
          <pre class="source-text">{{ sourceDialogText }}</pre>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="showSourceDialog = false">关闭</button>
        </div>
      </div>
    </div>
  <!-- Context Menu (Task) -->
    <div
      v-if="contextMenu.visible && contextMenu.type === 'task'"
      class="context-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
    >
      <div class="context-item" :class="{ disabled: !hasSource(contextMenu.task) }" @click="viewSource(contextMenu.task)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        查看原文
      </div>
      <div class="context-item" @click="askAi(contextMenu.task)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><circle cx="9" cy="10" r="1"/><circle cx="13" cy="10" r="1"/><circle cx="17" cy="10" r="1"/></svg>
        AI 协助
      </div>
      <div class="context-item" @click="editTask(contextMenu.task)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        编辑
      </div>
      <div class="context-divider"></div>
      <div class="context-item danger" @click="deleteTask(contextMenu.task)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        删除
      </div>
    </div>

    <!-- Context Menu (Column - New Directory) -->
    <div
      v-if="contextMenu.visible && contextMenu.type === 'column'"
      class="context-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
    >
      <div class="context-item" @click="openCreateGroupDialog">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
        新建目录
      </div>
    </div>

    <!-- Context Menu (Group - Rename / Delete) -->
    <div
      v-if="contextMenu.visible && contextMenu.type === 'group'"
      class="context-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
    >
      <div class="context-item" @click="openRenameGroupDialog(contextMenu.group)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        重命名
      </div>
      <div class="context-divider"></div>
      <div class="context-item danger" @click="deleteGroup(contextMenu.group)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        删除目录
      </div>
    </div>

    <!-- Group Create/Rename Dialog -->
    <div v-if="showGroupDialog" class="dialog-overlay" @click.self="showGroupDialog = false">
      <div class="dialog">
        <h3 class="dialog-title">{{ groupForm.id !== null ? '重命名目录' : '新建目录' }}</h3>
        <div class="dialog-body">
          <label class="dialog-label">目录名称</label>
          <input class="dialog-input" v-model="groupForm.name" placeholder="输入目录名称" @keyup.enter="saveGroup" />
        </div>
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="showGroupDialog = false">取消</button>
          <button class="btn btn-primary" @click="saveGroup" :disabled="!groupForm.name.trim()">保存</button>
        </div>
      </div>
    </div>

    <!-- Dismiss context menu on any click outside -->
    <div v-if="contextMenu.visible" class="context-overlay" @click="contextMenu.visible = false"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, reactive, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '@/utils/api'

const router = useRouter()
const route = useRoute()

interface TaskItem {
  id: number
  title: string
  description: string
  priority: string
  status: string
  source_type: string | null  // mail / text / file
  source_mail_id: string | null
  source_text: string | null
  source_file_path: string | null
  group_id: number | null  // NULL = ungrouped (done column only)
  due_date: string | null
  created_at: string
  updated_at: string
}

interface TaskGroup {
  id: number
  name: string
  created_at: string
  updated_at: string
}

interface ColumnDef {
  key: string
  title: string
  tasks: TaskItem[]
}

const statusMap: Record<string, string> = {
  todo: '待办',
  in_progress: '进行中',
  done: '已完成'
}

const priorityMap: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low'
}

const allTasks = ref<TaskItem[]>([])
const allGroups = ref<TaskGroup[]>([])
const collapsedGroups = ref<Set<number>>(new Set())
const dragOverGroupId = ref<number | null>(null)
const columns = ref<ColumnDef[]>([])
const draggedTask = ref<TaskItem | null>(null)
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showSourceDialog = ref(false)
const showGroupDialog = ref(false)
const sourceDialogText = ref('')
const editingTaskId = ref<number | null>(null)
const contextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  type: 'task' as 'task' | 'column' | 'group',
  task: null as TaskItem | null,
  group: null as TaskGroup | null,
  columnKey: ''
})
const newTaskForm = reactive({
  title: '',
  description: '',
  priority: 'medium'
})
const editForm = reactive({
  title: '',
  description: '',
  priority: 'medium',
  status: 'todo'
})
const groupForm = reactive({
  id: null as number | null,
  name: ''
})

onMounted(async () => {
  await loadTasks()
})

// 切换路由到任务中心时自动刷新
watch(
  () => route.path,
  (path) => {
    if (path === '/tasks') {
      loadTasks()
    }
  }
)

async function loadTasks() {
  try {
    const [tasks, groups] = await Promise.all([
      api.get<TaskItem[]>('/api/tasks'),
      api.get<TaskGroup[]>('/api/task-groups')
    ])
    allTasks.value = tasks
    allGroups.value = groups
  } catch {
    allTasks.value = []
    allGroups.value = []
  }
  rebuildColumns()
}

// Done-column directories with their tasks.
const doneGroups = computed(() =>
  allGroups.value.map(g => ({
    group: g,
    tasks: allTasks.value.filter(t => t.status === 'done' && t.group_id === g.id)
  }))
)

// Done-column tasks not in any directory.
const doneUngrouped = computed(() =>
  allTasks.value.filter(t => t.status === 'done' && t.group_id === null)
)

function rebuildColumns() {
  columns.value = [
    { key: 'todo', title: '待办', tasks: allTasks.value.filter(t => t.status === 'todo') },
    { key: 'in_progress', title: '进行中', tasks: allTasks.value.filter(t => t.status === 'in_progress') },
    { key: 'done', title: '已完成', tasks: allTasks.value.filter(t => t.status === 'done') }
  ]
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return '今天'
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function statusLabel(status: string): string {
  return statusMap[status] || status
}

function priorityLabel(priority: string): string {
  return priorityMap[priority] || priority
}

function onContextMenu(event: MouseEvent, task: TaskItem) {
  contextMenu.visible = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.type = 'task'
  contextMenu.task = task
  contextMenu.group = null
  contextMenu.columnKey = ''
}

function onColumnContextMenu(event: MouseEvent, colKey: string) {
  if (colKey !== 'done') return
  contextMenu.visible = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.type = 'column'
  contextMenu.task = null
  contextMenu.group = null
  contextMenu.columnKey = colKey
}

function onGroupContextMenu(event: MouseEvent, group: TaskGroup) {
  contextMenu.visible = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.type = 'group'
  contextMenu.task = null
  contextMenu.group = group
  contextMenu.columnKey = ''
}

function toggleGroup(groupId: number) {
  if (collapsedGroups.value.has(groupId)) {
    collapsedGroups.value.delete(groupId)
  } else {
    collapsedGroups.value.add(groupId)
  }
  // Trigger reactivity for Set
  collapsedGroups.value = new Set(collapsedGroups.value)
}

function openCreateGroupDialog() {
  contextMenu.visible = false
  groupForm.id = null
  groupForm.name = ''
  showGroupDialog.value = true
}

function openRenameGroupDialog(group: TaskGroup | null) {
  if (!group) return
  contextMenu.visible = false
  groupForm.id = group.id
  groupForm.name = group.name
  showGroupDialog.value = true
}

async function saveGroup() {
  if (!groupForm.name.trim()) return
  try {
    if (groupForm.id !== null) {
      await api.put(`/api/task-groups/${groupForm.id}`, { name: groupForm.name.trim() })
    } else {
      await api.post('/api/task-groups', { name: groupForm.name.trim() })
    }
    showGroupDialog.value = false
    groupForm.id = null
    groupForm.name = ''
    await loadTasks()
  } catch (e: any) {
    alert('保存目录失败: ' + (e?.message || String(e)))
  }
}

async function deleteGroup(group: TaskGroup | null) {
  if (!group) return
  contextMenu.visible = false
  if (!confirm(`确定删除目录"${group.name}"吗？目录内的任务将变为未分组。`)) return
  try {
    await api.delete(`/api/task-groups/${group.id}`)
    await loadTasks()
  } catch (e: any) {
    alert('删除目录失败: ' + (e?.message || String(e)))
  }
}

function sourceTypeOf(task: TaskItem | null): string | null {
  if (!task) return null
  if (task.source_type === 'mail' || task.source_type === 'text' || task.source_type === 'file') {
    return task.source_type
  }
  // Legacy rows have source_type = null — infer from source_mail_id.
  if (task.source_mail_id) return 'mail'
  if (task.source_text) return 'text'
  if (task.source_file_path) return 'file'
  return null
}

function hasSource(task: TaskItem | null): boolean {
  return sourceTypeOf(task) !== null
}

function viewSource(task: TaskItem | null) {
  if (!task) return
  const type = sourceTypeOf(task)
  contextMenu.visible = false
  if (type === 'mail' && task.source_mail_id) {
    router.push({ path: '/mail', query: { mailId: task.source_mail_id } })
  } else if (type === 'text' && task.source_text) {
    sourceDialogText.value = task.source_text
    showSourceDialog.value = true
  } else if (type === 'file' && task.source_file_path) {
    window.manchi.openFile(task.source_file_path)
  } else {
    alert('该任务未关联原文来源')
  }
}

function askAi(task: TaskItem | null) {
  if (!task) return
  contextMenu.visible = false
  router.push({ path: '/chat', query: { taskId: String(task.id), action: 'ai_assist' } })
}

function onDragStart(task: TaskItem) {
  draggedTask.value = task
}

async function onDrop(targetCol: string, groupId: number | null) {
  if (!draggedTask.value) return
  const task = draggedTask.value
  draggedTask.value = null
  dragOverGroupId.value = null

  if (task.status === targetCol && task.group_id === groupId) return
  try {
    const payload: Record<string, any> = { status: targetCol }
    if (targetCol === 'done') {
      payload.group_id = groupId  // null = ungrouped
    } else {
      payload.group_id = null  // leaving done column clears group
    }
    await api.put<TaskItem>(`/api/tasks/${task.id}`, payload)
    await loadTasks()
  } catch {
    // revert
  }
}

async function createTask() {
  if (!newTaskForm.title.trim()) return
  try {
    await api.post<TaskItem>('/api/tasks', {
      title: newTaskForm.title,
      description: newTaskForm.description,
      priority: newTaskForm.priority
    })
    showCreateDialog.value = false
    newTaskForm.title = ''
    newTaskForm.description = ''
    newTaskForm.priority = 'medium'
    await loadTasks()
  } catch (e: any) {
    alert('创建失败: ' + e.message)
  }
}

async function deleteTask(task: TaskItem | null) {
  if (!task) return
  contextMenu.visible = false
  if (!confirm('确定删除这个任务吗?')) return
  try {
    await api.delete(`/api/tasks/${task.id}`)
    await loadTasks()
  } catch (e: any) {
    alert('删除失败: ' + e.message)
  }
}

function editTask(task: TaskItem | null) {
  if (!task) return
  contextMenu.visible = false
  editingTaskId.value = task.id
  editForm.title = task.title
  editForm.description = task.description || ''
  editForm.priority = task.priority
  editForm.status = task.status
  showEditDialog.value = true
}

async function saveEditTask() {
  if (editingTaskId.value === null || !editForm.title.trim()) return
  try {
    await api.put(`/api/tasks/${editingTaskId.value}`, {
      title: editForm.title.trim(),
      description: editForm.description,
      priority: editForm.priority,
      status: editForm.status
    })
    showEditDialog.value = false
    editingTaskId.value = null
    await loadTasks()
  } catch (e: any) {
    alert('保存失败: ' + e.message)
  }
}
</script>

<style scoped>
.tasks-page {
  padding: 32px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 4px;
  background: var(--bg-surface);
  padding: 3px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 12px;
  border-radius: 4px;
  transition: all var(--transition-base);
}

.btn-ghost {
  color: var(--text-muted);
}

.btn-ghost:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-primary);
}

.btn-primary:hover {
  box-shadow: var(--shadow-glow);
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Kanban */
.kanban-board {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  flex: 1;
  overflow: hidden;
}

.kanban-column {
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.column-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 1px 8px;
  border-radius: 999px;
}

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100px;
}

.task-card {
  position: relative;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  gap: 12px;
  cursor: grab;
  transition: all var(--transition-base);
}

/* Status-specific card styles */
.task-card.status-todo {
  border-left: 3px solid #EAB308;
}

.task-card.status-in_progress {
  border-left: 3px solid #3B82F6;
  background: linear-gradient(135deg, var(--bg-elevated) 0%, rgba(59, 130, 246, 0.04) 100%);
}

.task-card.status-done {
  border-left: 3px solid #22C55E;
  opacity: 0.75;
}

.task-card.status-done .task-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.task-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-1px);
}

.task-card:active {
  cursor: grabbing;
}

.task-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  color: var(--text-muted);
  padding: 4px;
  border-radius: 4px;
  transition: all var(--transition-base);
}

.task-card:hover .task-delete {
  opacity: 1;
}

.task-delete:hover {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.1);
}

.task-priority {
  width: 3px;
  flex-shrink: 0;
  border-radius: 2px;
}

.priority-high { background: #EF4444; }
.priority-medium { background: #EAB308; }
.priority-low { background: #22C55E; }

.task-content {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tag-todo {
  background: rgba(234, 179, 8, 0.12);
  color: #EAB308;
}

.tag-in_progress {
  background: rgba(59, 130, 246, 0.12);
  color: #3B82F6;
}

.tag-done {
  background: rgba(34, 197, 94, 0.12);
  color: #22C55E;
}

.tag-high {
  background: rgba(239, 68, 68, 0.12);
  color: #EF4444;
}

.tag-medium {
  background: rgba(234, 179, 8, 0.12);
  color: #EAB308;
}

.tag-low {
  background: rgba(34, 197, 94, 0.12);
  color: #22C55E;
}

.task-mail-link {
  font-size: 12px;
  cursor: default;
}

.task-date {
  font-size: 11px;
  color: var(--text-muted);
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 420px;
  max-width: 90vw;
}

.dialog-wide {
  width: 640px;
}

.source-text {
  margin: 0;
  padding: 12px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 50vh;
  overflow-y: auto;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  padding: 20px 24px 0;
  color: var(--text-primary);
}

.dialog-body {
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dialog-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 4px;
}

.dialog-input,
.dialog-textarea,
.dialog-select {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
}

.dialog-input:focus,
.dialog-textarea:focus,
.dialog-select:focus {
  border-color: var(--accent);
}

.dialog-textarea {
  min-height: 80px;
  resize: vertical;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
}

/* Context Menu */
.context-overlay {
  position: fixed;
  inset: 0;
  z-index: 199;
}

.context-menu {
  position: fixed;
  z-index: 200;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  min-width: 160px;
  padding: 4px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.context-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.context-item:hover {
  background: var(--bg-hover);
}

.context-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.context-item.danger {
  color: #EF4444;
}

.context-item.danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

.context-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 8px;
}

/* Task Group (Done column directories) */
.task-group {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.15s;
}

.task-group.drag-over {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(79, 195, 247, 0.15);
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-surface);
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid transparent;
  transition: background 0.15s;
}

.group-header:hover {
  background: var(--bg-hover);
}

.task-group.drag-over .group-header {
  border-bottom-color: var(--accent);
}

.group-chevron {
  flex-shrink: 0;
  transition: transform 0.2s ease;
  color: var(--text-muted);
}

.group-chevron.collapsed {
  transform: rotate(-90deg);
}

.group-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.group-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 1px 8px;
  border-radius: 999px;
}

.group-tasks {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>