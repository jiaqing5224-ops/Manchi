<template>
  <div class="orch-page">
    <div class="page-header">
      <h2 class="page-title">智能编排</h2>
      <div class="header-actions">
        <button class="btn btn-ghost" @click="openComponentManager">管理组件</button>
        <button class="btn btn-primary" @click="openCreateBlank">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
          新建规则
        </button>
      </div>
    </div>

    <div class="section-title custom-title">我的规则</div>
    <div v-if="rules.length === 0" class="empty-state">
      <p>还没有规则，点击右上角"新建规则"开始创建</p>
    </div>

    <div class="rules-list">
      <div v-for="rule in rules" :key="rule.id" class="rule-row">
        <div class="rule-row-icon" :class="rule.last_run_status === 'failed' ? 'failed' : (rule.last_run_status === 'success' ? 'ok' : '')">
          <svg width="18" height="18" stroke="currentColor" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
        </div>
        <div class="rule-row-main" @click="openEdit(rule)">
          <div class="rule-row-name">{{ rule.name }}</div>
          <div class="rule-row-pipeline">
            <span class="chip chip-source">{{ sourceLabel(rule.source_config) }}</span>
            <span class="chip-arrow">→</span>
            <span class="chip chip-trigger">{{ triggerLabel(rule.trigger_config) }}</span>
            <span class="chip-arrow">→</span>
            <span v-for="(a, idx) in rule.actions_config" :key="idx" class="chip chip-action">
              {{ actionLabel(a.type) }}<span v-if="idx < rule.actions_config.length - 1" class="chain-plus"> +</span>
            </span>
            <span v-if="rule.actions_config.length === 0" class="chip chip-empty">无动作</span>
          </div>
          <div class="rule-row-meta">
            <span v-if="rule.last_run_at" class="meta-text" :class="rule.last_run_status">
              上次：{{ rule.last_run_status === 'success' ? '成功' : (rule.last_run_status === 'failed' ? '失败' : rule.last_run_status) }}
              · {{ formatTime(rule.last_run_at) }}
            </span>
            <span v-else class="meta-text muted">未运行</span>
          </div>
        </div>
        <div class="rule-row-actions">
          <span class="status-pill" :class="rule.is_active ? 'active' : 'inactive'" @click="toggleRule(rule)">
            {{ rule.is_active ? '运行中' : '已暂停' }}
          </span>
          <button class="icon-btn" :disabled="!rule.is_active || runningId === rule.id" @click="runRule(rule)" title="运行">
            <svg v-if="runningId === rule.id" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </button>
          <button class="icon-btn" @click="openArtifacts(rule)" title="产物目录">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          </button>
          <button class="icon-btn" @click="openEdit(rule)" title="编辑">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="icon-btn danger" @click="deleteRule(rule.id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Wizard Dialog -->
    <div v-if="showWizard" class="dialog-overlay" @click.self="closeWizard">
      <div class="wizard">
        <div class="wizard-header">
          <h3 class="wizard-title">{{ editingId ? '编辑规则' : '新建规则' }}</h3>
          <button class="wizard-close" @click="closeWizard">×</button>
        </div>

        <div class="wizard-steps">
          <div class="step-tabs">
            <div v-for="(s, i) in stepDefs" :key="i" class="step-tab" :class="{ active: step === i, done: step > i }" @click="step = i">
              <span class="step-num">{{ i + 1 }}</span>
              <span class="step-label">{{ s }}</span>
            </div>
          </div>

          <div class="step-body">
            <!-- Step 0: Basic -->
            <div v-if="step === 0" class="step-pane">
              <label class="fld-label">规则名称</label>
              <input class="fld-input" v-model="form.name" placeholder="例如：周报邮件摘要" />
              <label class="fld-label">描述</label>
              <textarea class="fld-textarea" v-model="form.description" placeholder="这条规则做什么？"></textarea>
            </div>

            <!-- Step 1: Source -->
            <div v-if="step === 1" class="step-pane">
              <label class="fld-label">输入源</label>
              <div class="type-selector">
                <div v-for="s in sourceTypes" :key="s.key" class="type-card" :class="{ active: form.source_config.type === s.key }" @click="setSourceType(s.key)">
                  <span class="type-icon">{{ s.icon }}</span>
                  <span class="type-name">{{ s.label }}</span>
                </div>
              </div>

              <div v-if="form.source_config.type === 'mail'" class="params-block">
                <label class="fld-label">扫描最近天数</label>
                <input class="fld-input" type="number" v-model.number="form.source_config.days_range" min="1" max="90" />
                <label class="fld-label">发件人过滤（可选，模糊匹配）</label>
                <input class="fld-input" v-model="form.source_config.sender_filter" placeholder="留空=所有发件人" />
              </div>

              <div v-if="form.source_config.type === 'text'" class="params-block">
                <label class="fld-label">文本内容</label>
                <textarea class="fld-textarea tall" v-model="form.source_config.content" placeholder="粘贴或输入要处理的文本..."></textarea>
              </div>

              <div v-if="form.source_config.type === 'file'" class="params-block">
                <label class="fld-label">文件路径</label>
                <div class="file-row">
                  <input class="fld-input" v-model="form.source_config.file_path" placeholder="选择文件..." />
                  <button class="btn btn-ghost" @click="pickFile">浏览</button>
                </div>
                <label class="fld-label">编码</label>
                <input class="fld-input" v-model="form.source_config.encoding" />
              </div>
            </div>

            <!-- Step 2: Trigger -->
            <div v-if="step === 2" class="step-pane">
              <label class="fld-label">触发方式</label>
              <div class="type-selector">
                <div v-for="t in triggerTypes" :key="t.key" class="type-card" :class="{ active: form.trigger_config.type === t.key }" @click="setTriggerType(t.key)">
                  <span class="type-icon">{{ t.icon }}</span>
                  <span class="type-name">{{ t.label }}</span>
                </div>
              </div>
              <div v-if="form.trigger_config.type === 'schedule'" class="params-block">
                <label class="fld-label">Cron 表达式</label>
                <input class="fld-input" v-model="form.trigger_config.cron" placeholder="0 9 * * 1-5（工作日9点）" />
                <div class="cron-presets">
                  <button class="cron-chip" @click="form.trigger_config.cron = '0 9 * * *'">每天 9:00</button>
                  <button class="cron-chip" @click="form.trigger_config.cron = '0 9 * * 1-5'">工作日 9:00</button>
                  <button class="cron-chip" @click="form.trigger_config.cron = '0 18 * * *'">每天 18:00</button>
                  <button class="cron-chip" @click="form.trigger_config.cron = '0 9 * * 1'">每周一 9:00</button>
                </div>
                <p class="hint-text">格式：分 时 日 月 周（* = 任意）</p>
              </div>
              <div v-if="form.trigger_config.type === 'manual'" class="hint-block">
                手动触发：保存后点击规则卡片上的"运行"按钮即可执行。
              </div>
              <div v-if="form.trigger_config.type === 'new_mail'" class="hint-block">
                新邮件到达时自动触发（需要邮件扫描后台运行）。
              </div>
            </div>

            <!-- Step 3: Actions -->
            <div v-if="step === 3" class="step-pane">
              <label class="fld-label">动作链（按顺序执行）</label>
              <div class="actions-chain">
                <div v-for="(a, idx) in form.actions_config" :key="idx" class="action-item">
                  <div class="action-head">
                    <span class="action-idx">{{ idx + 1 }}</span>
                    <span class="action-type">{{ actionLabel(a.type) }}</span>
                    <div class="action-controls">
                      <button class="mini-btn" :disabled="idx === 0" @click="moveAction(idx, -1)" title="上移">↑</button>
                      <button class="mini-btn" :disabled="idx === form.actions_config.length - 1" @click="moveAction(idx, 1)" title="下移">↓</button>
                      <button class="mini-btn danger" @click="removeAction(idx)" title="删除">×</button>
                    </div>
                  </div>
                  <div class="action-params">
                    <component :is="'div'">
                      <template v-if="a.type === 'ai_meeting_extract'">
                        <div class="param-hint">自动识别会议邀请/通知邮件，提取主题、开始/结束时间、时长。无需配置参数。</div>
                      </template>
                      <template v-else-if="a.type === 'ai_analyze'">
                        <label class="mini-label">分析模式</label>
                        <select class="fld-input" v-model="a.params.mode">
                          <option value="extract">提取结构化字段</option>
                          <option value="summarize">摘要</option>
                          <option value="classify">分类</option>
                        </select>
                        <label class="mini-label">输出格式</label>
                        <select class="fld-input" v-model="a.params.output_format">
                          <option value="raw">原始（列表/文本，兼容下游）</option>
                          <option value="markdown">Markdown</option>
                        </select>
                        <template v-if="a.params.mode === 'extract'">
                          <label class="mini-label">提取字段（逗号分隔）</label>
                          <input class="fld-input" v-model="a.params.fields_text" placeholder="subject, start_time, end_time" />
                          <label class="mini-label">附加指令（可选）</label>
                          <textarea class="fld-textarea" v-model="a.params.prompt_extra" placeholder="如：仅提取会议邀请类邮件"></textarea>
                        </template>
                        <template v-else-if="a.params.mode === 'classify'">
                          <label class="mini-label">分类标签（逗号分隔）</label>
                          <input class="fld-input" v-model="a.params.categories_text" placeholder="紧急, 常规, 垃圾" />
                        </template>
                        <template v-else-if="a.params.mode === 'summarize'">
                          <label class="mini-label">最大字数</label>
                          <input class="fld-input" type="number" v-model.number="a.params.max_length" />
                        </template>
                      </template>
                      <template v-else-if="a.type === 'ai_extract'">
                        <label class="mini-label">提取字段（逗号分隔）</label>
                        <input class="fld-input" v-model="a.params.fields_text" placeholder="subject, start_time, end_time" />
                        <label class="mini-label">附加指令（可选）</label>
                        <textarea class="fld-textarea" v-model="a.params.prompt_extra" placeholder="如：仅提取会议邀请类邮件"></textarea>
                      </template>
                      <template v-else-if="a.type === 'ai_summarize'">
                        <label class="mini-label">最大字数</label>
                        <input class="fld-input" type="number" v-model.number="a.params.max_length" />
                      </template>
                      <template v-else-if="a.type === 'ai_classify'">
                        <label class="mini-label">分类标签（逗号分隔）</label>
                        <input class="fld-input" v-model="a.params.categories_text" placeholder="紧急, 常规, 垃圾" />
                      </template>
                      <template v-else-if="a.type === 'create_task'">
                        <label class="mini-label">标题字段名</label>
                        <input class="fld-input" v-model="a.params.title_field" placeholder="title" />
                        <label class="mini-label">优先级</label>
                        <select class="fld-input" v-model="a.params.priority">
                          <option value="high">高</option>
                          <option value="medium">中</option>
                          <option value="low">低</option>
                        </select>
                      </template>
                      <template v-else-if="a.type === 'notify'">
                        <label class="mini-label">通知消息</label>
                        <input class="fld-input" v-model="a.params.message" placeholder="编排执行完成" />
                      </template>
                      <template v-else-if="isCustomAction(a.type)">
                        <ParamForm
                          :paramsDef="componentMap[a.type] ? componentMap[a.type].params : {}"
                          v-model="a.params"
                        />
                      </template>
                    </component>
                  </div>
                </div>
                <div v-if="form.actions_config.length === 0" class="actions-empty">还没有动作，点击下方添加</div>
              </div>
              <div class="add-action">
                <div class="add-action-row">
                  <button v-for="c in systemComponents" :key="c.name" class="add-action-chip" @click="addAction(c.name)">
                    + {{ actionLabel(c.name) }}
                  </button>
                </div>
                <div class="add-action-row" v-if="customComponents.length">
                  <button v-for="c in customComponents" :key="c.name" class="add-action-chip custom-chip" @click="addCustomAction(c.name, c.params)">
                    + ⭐ {{ c.display_name }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="wizard-footer">
          <button class="btn btn-ghost" @click="step = Math.max(0, step - 1)" :disabled="step === 0">上一步</button>
          <div class="footer-right">
            <button v-if="step < 3" class="btn btn-primary" @click="step = Math.min(3, step + 1)">下一步</button>
            <button v-else class="btn btn-primary" @click="saveRule" :disabled="!form.name.trim()">{{ editingId ? '保存' : '创建' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Run Result Dialog -->
    <div v-if="runResult" class="dialog-overlay" @click.self="runResult = null">
      <div class="result-dialog">
        <div class="result-header">
          <h3 class="result-title">运行结果</h3>
          <span class="result-status" :class="runResult.status">{{ runResult.status === 'success' ? '成功' : '失败' }}</span>
        </div>
        <div class="result-body">
          <div class="result-section">
            <div class="result-section-title">执行步骤</div>
            <div v-for="(s, i) in runResult.steps" :key="i" class="result-step">{{ s }}</div>
          </div>
          <div v-if="runResult.artifacts.length > 0" class="result-section">
            <div class="result-section-title">产物文件 ({{ runResult.artifacts.length }})</div>
            <div v-for="(a, i) in runResult.artifacts" :key="i" class="result-artifact">{{ a }}</div>
          </div>
          <div v-if="runResult.message" class="result-section">
            <div class="result-section-title">消息</div>
            <div class="result-message">{{ runResult.message }}</div>
          </div>
        </div>
        <div class="result-footer">
          <button class="btn btn-ghost" @click="runResult = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- Message Dialog (replaces native alert/confirm) -->
    <div v-if="msgBox.show" class="dialog-overlay msg-overlay" @click.self="msgBox.show = false">
      <div class="msg-dialog">
        <div class="msg-header">
          <h3 class="msg-title">{{ msgBox.title }}</h3>
        </div>
        <div class="msg-body">{{ msgBox.message }}</div>
        <div class="msg-footer">
          <button v-if="msgBox.type === 'confirm'" class="btn btn-ghost" @click="msgBox.show = false">取消</button>
          <button class="btn btn-primary" @click="msgBox.onOk">确定</button>
        </div>
      </div>
    </div>

    <!-- Component Manager -->
    <div v-if="showManager" class="dialog-overlay" @click.self="closeComponentManager">
      <div class="msg-dialog" style="max-width:680px; width:92%; max-height:82vh; overflow:auto;">
        <div class="msg-header">
          <h3 class="msg-title">管理组件</h3>
          <button class="wizard-close" @click="closeComponentManager">×</button>
        </div>
        <div class="msg-body">
          <div class="mgr-toolbar">
            <label class="btn btn-ghost mgr-import">
              导入组件（文件夹）
              <input type="file" webkitdirectory @change="onImportFolder" hidden />
            </label>
            <label class="btn btn-ghost mgr-import">
              导入 .zip 包
              <input type="file" accept=".zip" @change="onImportZip" hidden />
            </label>
            <button class="btn btn-ghost" @click="onInstallDeps">安装依赖</button>
            <span class="mgr-hint">自定义组件（共 {{ customComponents.length }} 个）</span>
          </div>
          <div v-if="customComponents.length === 0" class="mgr-empty">
            还没有自定义组件。可在 Chat 中让 AI 生成，或点击「导入组件（文件夹）」选择一个组件目录。
          </div>
          <div v-for="c in customComponents" :key="c.name" class="mgr-row">
            <div class="mgr-info">
              <div class="mgr-name">⭐ {{ c.display_name }}</div>
              <div class="mgr-meta">{{ c.name }} · {{ c.type }} · 输入:{{ c.input_requirement }}</div>
              <div class="mgr-desc">{{ c.description }}</div>
            </div>
            <div class="mgr-actions">
              <button class="mini-btn" @click="onExport(c.name)" title="导出">导出</button>
              <button class="mini-btn danger" @click="onDelete(c.name)" title="删除">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated, reactive, computed } from 'vue'
import { api } from '@/utils/api'
import ParamForm from '@/components/orch/ParamForm.vue'

interface SourceConfig {
  type: 'mail' | 'text' | 'file'
  days_range?: number
  sender_filter?: string
  content?: string
  file_path?: string
  encoding?: string
}

interface TriggerConfig {
  type: 'manual' | 'schedule' | 'new_mail'
  cron?: string
  description?: string
}

interface ActionConfig {
  type: string
  params: Record<string, any>
}

interface RuleItem {
  id: number
  name: string
  description: string
  source_config: SourceConfig
  trigger_config: TriggerConfig
  actions_config: ActionConfig[]
  is_active: boolean
  created_at: string
  updated_at?: string
  last_run_at?: string
  last_run_status?: string
  last_run_message?: string
}

interface RunResult {
  rule_id: number
  status: string
  message: string
  artifacts: string[]
  steps: string[]
  started_at: string
  finished_at: string
}

interface ParamDef {
  type: 'string' | 'number' | 'boolean' | 'select' | 'textarea' | 'file'
  label?: string
  default?: any
  required?: boolean
  description?: string
  options?: string[]
}

interface ComponentMeta {
  name: string
  display_name: string
  description: string
  version?: string
  author?: string
  source: 'system' | 'custom'
  type: string
  input_requirement: string
  output_type?: string
  requires?: string[]
  params: Record<string, ParamDef>
}

const rules = ref<RuleItem[]>([])
const allComponents = ref<ComponentMeta[]>([])
const showManager = ref(false)
const showWizard = ref(false)
const step = ref(0)
const editingId = ref<number | null>(null)
const runningId = ref<number | null>(null)
const runResult = ref<RunResult | null>(null)
const msgBox = reactive<{
  show: boolean
  title: string
  message: string
  type: 'alert' | 'confirm'
  onOk: () => void
}>({
  show: false, title: '', message: '', type: 'alert', onOk: () => {}
})

function showAlert(message: string, title = '提示'): void {
  msgBox.title = title
  msgBox.message = message
  msgBox.type = 'alert'
  msgBox.onOk = () => { msgBox.show = false }
  msgBox.show = true
}

function showConfirm(message: string, onConfirm: () => void, title = '确认'): void {
  msgBox.title = title
  msgBox.message = message
  msgBox.type = 'confirm'
  msgBox.onOk = () => { msgBox.show = false; onConfirm() }
  msgBox.show = true
}

const stepDefs = ['基本信息', '输入源', '触发器', '动作链']

const sourceTypes = [
  { key: 'mail', label: '邮件', icon: '📧' },
  { key: 'text', label: '自定义文本', icon: '📝' },
  { key: 'file', label: '选择文件', icon: '📄' }
]

const triggerTypes = [
  { key: 'manual', label: '手动运行', icon: '▶' },
  { key: 'schedule', label: '定时触发', icon: '⏰' },
  { key: 'new_mail', label: '新邮件到达', icon: '✉' }
]

// The actual system actions surfaced in the "add action" dropdown.
// ai_extract / ai_summarize / ai_classify are kept as registry ALIASES of
// ai_analyze for backward-compatible rule editing, but are not re-offered as
// new adds — ai_analyze is the single entry point for AI analysis.
const PRIMARY_SYSTEM_ACTIONS = ['ai_analyze', 'ai_meeting_extract', 'create_task', 'notify']

function defaultSourceConfig(): SourceConfig {
  return { type: 'text', content: '' }
}
function defaultTriggerConfig(): TriggerConfig {
  return { type: 'manual' }
}

const form = reactive({
  name: '',
  description: '',
  source_config: defaultSourceConfig() as SourceConfig,
  trigger_config: defaultTriggerConfig() as TriggerConfig,
  actions_config: [] as ActionConfig[]
})

onMounted(async () => {
  await Promise.all([loadRules(), loadComponents()])
})

// keep-alive 缓存组件切回时刷新规则列表（AI 在 Chat 页面创建的规则会同步显示）
onActivated(async () => {
  await loadRules()
})

async function loadRules() {
  try {
    rules.value = await api.get<RuleItem[]>('/api/rules')
  } catch {
    rules.value = []
  }
}

async function loadComponents() {
  try {
    allComponents.value = await api.components.list<ComponentMeta[]>()
  } catch {
    allComponents.value = []
  }
}

const customComponents = computed<ComponentMeta[]>(() =>
  allComponents.value.filter(c => c.source === 'custom')
)
const systemComponents = computed<ComponentMeta[]>(() =>
  allComponents.value.filter(c => c.source === 'system' && PRIMARY_SYSTEM_ACTIONS.includes(c.name))
)

// Full name -> meta map (system + custom), used to decide system vs custom
// rendering/serialization and to look up custom manifests.
const componentMap = computed<Record<string, ComponentMeta>>(() =>
  Object.fromEntries(allComponents.value.map(c => [c.name, c]))
)

function isSystemAction(type: string): boolean {
  return componentMap.value[type]?.source === 'system'
}

function isCustomAction(type: string): boolean {
  return !isSystemAction(type)
}

function defaultParamsFromDef(paramsDef: Record<string, ParamDef>): Record<string, any> {
  const out: Record<string, any> = {}
  for (const k in paramsDef) {
    const def = paramsDef[k]
    if (def.default !== undefined) out[k] = def.default
    else if (def.type === 'boolean') out[k] = false
    else if (def.type === 'number') out[k] = 0
    else out[k] = ''
  }
  return out
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.source_config = defaultSourceConfig()
  form.trigger_config = defaultTriggerConfig()
  form.actions_config = []
  step.value = 0
  editingId.value = null
}

function openCreateBlank() {
  resetForm()
  showWizard.value = true
}

function openEdit(rule: RuleItem) {
  resetForm()
  editingId.value = rule.id
  form.name = rule.name
  form.description = rule.description
  form.source_config = JSON.parse(JSON.stringify(rule.source_config))
  form.trigger_config = JSON.parse(JSON.stringify(rule.trigger_config))
  form.actions_config = JSON.parse(JSON.stringify(rule.actions_config))
  form.actions_config.forEach(a => normalizeActionParams(a))
  showWizard.value = true
}

function closeWizard() {
  showWizard.value = false
  resetForm()
}

function normalizeActionParams(a: ActionConfig) {
  if (!isSystemAction(a.type)) {
    a.params = a.params || {}
    return
  }
  if (a.type === 'ai_extract') {
    if (!a.params.fields_text) {
      const f = a.params.fields
      a.params.fields_text = Array.isArray(f) ? f.join(', ') : (f || '')
    }
  }
  if (a.type === 'ai_classify') {
    if (!a.params.categories_text) {
      const c = a.params.categories
      a.params.categories_text = Array.isArray(c) ? c.join(', ') : (c || '')
    }
  }
  if (a.type === 'ai_analyze') {
    const mode = a.params.mode || 'extract'
    if (mode === 'extract' && !a.params.fields_text && a.params.fields) {
      const f = a.params.fields
      a.params.fields_text = Array.isArray(f) ? f.join(', ') : (f || '')
    }
    if (mode === 'classify' && !a.params.categories_text && a.params.categories) {
      const c = a.params.categories
      a.params.categories_text = Array.isArray(c) ? c.join(', ') : (c || '')
    }
  }
}

function setSourceType(key: string) {
  const cur = form.source_config
  if (key === 'mail') {
    form.source_config = { type: 'mail', days_range: cur.days_range || 5, sender_filter: cur.sender_filter || '' }
  } else if (key === 'text') {
    form.source_config = { type: 'text', content: cur.content || '' }
  } else {
    form.source_config = { type: 'file', file_path: cur.file_path || '', encoding: cur.encoding || 'utf-8' }
  }
}

function setTriggerType(key: string) {
  if (key === 'schedule') {
    form.trigger_config = { type: 'schedule', cron: form.trigger_config.cron || '0 9 * * *' }
  } else if (key === 'new_mail') {
    form.trigger_config = { type: 'new_mail' }
  } else {
    form.trigger_config = { type: 'manual' }
  }
}

function addAction(type: string) {
  const params: Record<string, any> = {}
  if (type === 'ai_analyze') { params.mode = 'extract'; params.output_format = 'raw' }
  else if (type === 'ai_meeting_extract') { /* no params */ }
  else if (type === 'ai_extract') { params.fields_text = ''; params.prompt_extra = '' }
  else if (type === 'ai_summarize') { params.max_length = 300 }
  else if (type === 'ai_classify') { params.categories_text = '紧急, 常规, 垃圾' }
  else if (type === 'create_task') { params.title_field = 'title'; params.priority = 'medium' }
  else if (type === 'notify') { params.message = '编排执行完成' }
  form.actions_config.push({ type, params })
}

function addCustomAction(name: string, paramsDef: Record<string, ParamDef>) {
  form.actions_config.push({ type: name, params: defaultParamsFromDef(paramsDef || {}) })
}

function removeAction(idx: number) {
  form.actions_config.splice(idx, 1)
}

function moveAction(idx: number, dir: number) {
  const ni = idx + dir
  if (ni < 0 || ni >= form.actions_config.length) return
  const tmp = form.actions_config[idx]
  form.actions_config[idx] = form.actions_config[ni]
  form.actions_config[ni] = tmp
}

function serializeActionParams(a: ActionConfig): ActionConfig {
  const out: ActionConfig = { type: a.type, params: {} }
  if (!isSystemAction(a.type)) {
    // custom component: params are already structured via ParamForm
    out.params = JSON.parse(JSON.stringify(a.params || {}))
    return out
  }
  if (a.type === 'ai_analyze') {
    out.params.mode = a.params.mode || 'extract'
    out.params.output_format = a.params.output_format || 'raw'
    if (out.params.mode === 'extract') {
      const fields = String(a.params.fields_text || '').split(',').map(s => s.trim()).filter(Boolean)
      if (fields.length) out.params.fields = fields
      if (a.params.prompt_extra) out.params.prompt_extra = a.params.prompt_extra
    } else if (out.params.mode === 'classify') {
      const cats = String(a.params.categories_text || '').split(',').map(s => s.trim()).filter(Boolean)
      if (cats.length) out.params.categories = cats
    } else if (out.params.mode === 'summarize') {
      out.params.max_length = Number(a.params.max_length) || 300
    }
  } else if (a.type === 'ai_extract') {
    out.params.fields = String(a.params.fields_text || '').split(',').map(s => s.trim()).filter(Boolean)
    if (a.params.prompt_extra) out.params.prompt_extra = a.params.prompt_extra
  } else if (a.type === 'ai_classify') {
    out.params.categories = String(a.params.categories_text || '').split(',').map(s => s.trim()).filter(Boolean)
  } else if (a.type === 'ai_summarize') {
    out.params.max_length = Number(a.params.max_length) || 300
  } else if (a.type === 'create_task') {
    out.params.title_field = a.params.title_field || 'title'
    out.params.priority = a.params.priority || 'medium'
  } else if (a.type === 'notify') {
    if (a.params.message) out.params.message = a.params.message
  }
  return out
}

async function saveRule() {
  if (!form.name.trim()) return
  const payload = {
    name: form.name.trim(),
    description: form.description,
    source_config: form.source_config,
    trigger_config: form.trigger_config,
    actions_config: form.actions_config.map(serializeActionParams)
  }
  try {
    if (editingId.value) {
      await api.put(`/api/rules/${editingId.value}`, payload)
    } else {
      await api.post('/api/rules', payload)
    }
    closeWizard()
    await loadRules()
  } catch (e: any) {
    showAlert('保存失败: ' + (e?.message || String(e)))
  }
}

async function toggleRule(rule: RuleItem) {
  try {
    await api.put(`/api/rules/${rule.id}`, { is_active: !rule.is_active })
    rule.is_active = !rule.is_active
  } catch {
    // revert
  }
}

function deleteRule(id: number) {
  showConfirm('确定删除此规则?', async () => {
    try {
      await api.delete(`/api/rules/${id}`)
      await loadRules()
    } catch (e: any) {
      showAlert('删除失败: ' + (e?.message || String(e)))
    }
  })
}

function openComponentManager() {
  showManager.value = true
  loadComponents()
}

function closeComponentManager() {
  showManager.value = false
}

async function onImportFolder(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  try {
    await api.components.importFolder(files)
    await loadComponents()
    showAlert('组件导入成功')
  } catch (err: any) {
    showAlert('导入失败: ' + (err?.message || String(err)))
  } finally {
    input.value = ''
  }
}

async function onImportZip(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files && input.files[0]
  if (!file) return
  try {
    await api.components.importZip(file)
    await loadComponents()
    showAlert('组件导入成功')
  } catch (err: any) {
    showAlert('导入失败: ' + (err?.message || String(err)))
  } finally {
    input.value = ''
  }
}

async function onExport(name: string) {
  try {
    const blob = await api.components.exportZip(name)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name + '.zip'
    a.click()
    URL.revokeObjectURL(url)
  } catch (err: any) {
    showAlert('导出失败: ' + (err?.message || String(err)))
  }
}

async function onDelete(name: string) {
  showConfirm(`确定删除组件 "${name}"?`, async () => {
    try {
      await api.components.remove(name)
      await loadComponents()
    } catch (err: any) {
      showAlert('删除失败: ' + (err?.message || String(err)))
    }
  })
}

async function onInstallDeps() {
  try {
    await api.components.installDeps()
    showAlert('依赖安装已触发，请在后端日志查看结果')
  } catch (err: any) {
    showAlert('安装失败: ' + (err?.message || String(err)))
  }
}

async function runRule(rule: RuleItem) {
  if (runningId.value) return
  runningId.value = rule.id
  try {
    const result = await api.post<RunResult>(`/api/rules/${rule.id}/run`, {})
    runResult.value = result
    await loadRules()
  } catch (e: any) {
    showAlert('运行失败: ' + (e?.message || String(e)))
  } finally {
    runningId.value = null
  }
}

async function openArtifacts(rule: RuleItem) {
  try {
    await api.post(`/api/rules/${rule.id}/open-artifacts`, {})
  } catch (e: any) {
    showAlert('打开目录失败: ' + (e?.message || String(e)))
  }
}

async function pickFile() {
  const path = await window.manchi.pickFile()
  if (path) form.source_config.file_path = path
}

function sourceLabel(c: SourceConfig): string {
  if (c.type === 'mail') return `邮件(最近${c.days_range || 5}天)`
  if (c.type === 'text') return '文本'
  if (c.type === 'file') return '文件'
  return c.type
}

function triggerLabel(c: TriggerConfig): string {
  if (c.type === 'manual') return '手动'
  if (c.type === 'schedule') return `定时(${c.cron || ''})`
  if (c.type === 'new_mail') return '新邮件'
  return c.type
}

function actionLabel(t: string): string {
  const meta = componentMap.value[t]
  if (meta && meta.source === 'custom') return '⭐ ' + (meta.display_name || t)
  const m: Record<string, string> = {
    ai_analyze: 'AI分析', ai_meeting_extract: 'AI会议提取',
    ai_extract: 'AI提取', ai_summarize: 'AI摘要', ai_classify: 'AI分类',
    export_excel: '导出Excel', export_json: '导出JSON',
    export_markdown: '导出Markdown', create_task: '生成Task',
    excel_workload_export: 'Excel工时导出', notify: '通知'
  }
  return m[t] || t
}

function formatTime(s: string): string {
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.orch-page {
  padding: 32px;
  height: 100%;
  overflow-y: auto;
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

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 12px;
  margin-top: 24px;
}

.section-title:first-of-type {
  margin-top: 0;
}

.custom-title {
  margin-top: 36px;
}

/* Rules list */
.rules-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-row {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  transition: all var(--transition-base);
}

.rule-row:hover {
  border-color: var(--border-hover);
  background: var(--bg-elevated);
}

.rule-row-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.rule-row-icon.ok { color: #22C55E; }
.rule-row-icon.failed { color: #EF4444; }

.rule-row-main {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.rule-row-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.rule-row-pipeline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  white-space: nowrap;
}

.chip-source { background: rgba(79, 195, 247, 0.14); color: #4FC3F7; }
.chip-trigger { background: rgba(234, 179, 8, 0.14); color: #EAB308; }
.chip-action { background: rgba(124, 58, 237, 0.14); color: #A78BFA; }
.chip-empty { background: var(--bg-hover); color: var(--text-muted); }

.chip-arrow {
  color: var(--text-muted);
  font-size: 10px;
}

.chain-plus {
  color: var(--text-muted);
  margin-left: 2px;
}

.rule-row-meta {
  font-size: 11px;
}

.meta-text {
  color: var(--text-secondary);
}

.meta-text.success { color: #22C55E; }
.meta-text.failed { color: #EF4444; }
.meta-text.muted { color: var(--text-muted); }

.rule-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.status-pill {
  font-size: 10px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.status-pill.active {
  background: rgba(34, 197, 94, 0.12);
  color: #22C55E;
}

.status-pill.inactive {
  background: var(--bg-hover);
  color: var(--text-muted);
}

.icon-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  transition: all var(--transition-base);
}

.icon-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.icon-btn.danger:hover {
  color: #EF4444;
  background: rgba(239, 68, 68, 0.1);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

/* Wizard dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

/* Global alert/confirm must always sit above other dialogs (e.g. the
   component-manager modal), otherwise it renders behind them. */
.msg-overlay {
  z-index: 200;
}

.wizard {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 640px;
  max-width: 92vw;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
}

.wizard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border);
}

.wizard-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.wizard-close {
  width: 28px;
  height: 28px;
  font-size: 20px;
  color: var(--text-muted);
  border-radius: 4px;
}

.wizard-close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.wizard-steps {
  flex: 1;
  overflow-y: auto;
}

.step-tabs {
  display: flex;
  gap: 4px;
  padding: 14px 24px 0;
  border-bottom: 1px solid var(--border);
}

.step-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-base);
}

.step-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.step-tab.done {
  color: var(--text-secondary);
}

.step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
}

.step-tab.active .step-num {
  background: var(--accent);
  color: var(--bg-primary);
}

.step-body {
  padding: 20px 24px;
}

.step-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fld-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 8px;
}

.fld-label:first-child {
  margin-top: 0;
}

.fld-input {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
}

.fld-input:focus {
  border-color: var(--accent);
}

.fld-textarea {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
  min-height: 60px;
  resize: vertical;
}

.fld-textarea.tall {
  min-height: 140px;
}

.fld-textarea:focus {
  border-color: var(--accent);
}

.type-selector {
  display: flex;
  gap: 8px;
}

.type-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-base);
  background: var(--bg-surface);
}

.type-card:hover {
  border-color: var(--border-hover);
}

.type-card.active {
  border-color: var(--accent);
  background: var(--accent-glow);
}

.type-icon {
  font-size: 20px;
}

.type-name {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}

.type-card.active .type-name {
  color: var(--accent);
}

.params-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-row {
  display: flex;
  gap: 8px;
}

.file-row .fld-input {
  flex: 1;
}

.cron-presets {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.cron-chip {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 4px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.cron-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.hint-text {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.hint-block {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* Actions chain */
.actions-chain {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  overflow: hidden;
}

.action-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-hover);
}

.action-idx {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: var(--accent);
  color: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.action-type {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.action-controls {
  display: flex;
  gap: 2px;
}

.mini-btn {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  color: var(--text-muted);
  font-size: 14px;
}

.mini-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-elevated);
}

.mini-btn:disabled {
  opacity: 0.3;
}

.mini-btn.danger:hover {
  color: #EF4444;
}

.action-params {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mini-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.actions-empty {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 12px;
}

.add-action {
  margin-top: 8px;
}

.add-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.add-action-chip {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px dashed var(--border);
}

.add-action-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
  border-style: solid;
}

.wizard-footer {
  display: flex;
  justify-content: space-between;
  padding: 14px 24px;
  border-top: 1px solid var(--border);
}

.footer-right {
  display: flex;
  gap: 8px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-base);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-primary);
}

.btn-primary:hover:not(:disabled) {
  box-shadow: var(--shadow-glow);
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-ghost {
  color: var(--text-muted);
  background: transparent;
}

.btn-ghost:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Run result dialog */
.result-dialog {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 560px;
  max-width: 92vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border);
}

.result-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.result-status {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
  text-transform: uppercase;
}

.result-status.success {
  background: rgba(34, 197, 94, 0.14);
  color: #22C55E;
}

.result-status.failed {
  background: rgba(239, 68, 68, 0.14);
  color: #EF4444;
}

.result-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.result-step {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 0;
  padding-left: 12px;
  border-left: 2px solid var(--border);
  margin-bottom: 2px;
  font-family: var(--font-mono, monospace);
}

.result-artifact {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 4px 8px;
  background: var(--bg-surface);
  border-radius: 3px;
  margin-bottom: 4px;
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}

.result-message {
  font-size: 12px;
  color: #EF4444;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-sm);
}

.result-footer {
  display: flex;
  justify-content: flex-end;
  padding: 14px 24px;
  border-top: 1px solid var(--border);
}

/* Message dialog (custom alert/confirm) */
.msg-dialog {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 420px;
  max-width: 92vw;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg, 0 8px 32px rgba(0,0,0,0.4));
}

.msg-header {
  padding: 18px 24px 8px;
}

.msg-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.msg-body {
  padding: 4px 24px 20px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary, var(--text-muted));
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 24px 16px;
}

.param-hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 10px;
  background: var(--bg-hover, rgba(255,255,255,0.04));
  border-radius: var(--radius-sm, 6px);
  line-height: 1.5;
}

/* Header actions (manage components button) */
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Custom component add-action chip */
.custom-chip {
  border-color: var(--accent);
  color: var(--accent);
  border-style: solid;
  background: var(--accent-glow, rgba(99, 102, 241, 0.08));
}

.custom-chip:hover {
  color: var(--bg-primary);
  background: var(--accent);
  border-color: var(--accent);
}

/* Component manager dialog */
.mgr-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.mgr-import {
  cursor: pointer;
  padding: 8px 16px;
}

.mgr-import input[type="file"] {
  display: none;
}

.mgr-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

.mgr-empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.mgr-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
}

.mgr-row:last-child {
  border-bottom: none;
}

.mgr-info {
  flex: 1;
  min-width: 0;
}

.mgr-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 3px;
}

.mgr-meta {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  margin-bottom: 3px;
}

.mgr-desc {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.mgr-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
</style>
