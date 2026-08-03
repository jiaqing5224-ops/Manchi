<template>
	<div class="settings-page">
		<header class="settings-header">
			<div>
				<h1>设置</h1>
				<p>管理启动行为、AI 模型和邮件扫描参数。</p>
			</div>
			<div class="header-actions">
				<button class="ghost-btn" :disabled="loading || saving" @click="loadSettings">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M16 8h5V3"/></svg>
					刷新
				</button>
				<button class="primary-btn" :disabled="loading || saving" @click="saveSettings">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
					{{ saving ? '保存中...' : '保存设置' }}
				</button>
			</div>
		</header>

		<div v-if="error" class="notice error">{{ error }}</div>
		<div v-else-if="savedMessage" class="notice success">{{ savedMessage }}</div>

		<main class="settings-grid">
			<section class="settings-panel">
				<div class="panel-title">
					<span class="panel-icon">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M2 12h20"/><path d="m4.93 4.93 14.14 14.14"/><path d="m19.07 4.93-14.14 14.14"/></svg>
					</span>
					<div>
						<h2>应用行为</h2>
						<p>控制窗口和系统托盘相关选项。</p>
					</div>
				</div>

				<label class="toggle-row">
					<span>
						<strong>开机自动启动</strong>
						<small>登录 Windows 后自动启动 Manchi。</small>
					</span>
					<input v-model="form.auto_launch" type="checkbox" />
				</label>

				<label class="toggle-row">
					<span>
						<strong>关闭时最小化到托盘</strong>
						<small>保持后台运行，便于继续扫描邮件和处理提醒。</small>
					</span>
					<input v-model="form.minimize_to_tray" type="checkbox" />
				</label>
			</section>

			<section class="settings-panel wide">
				<div class="panel-title">
					<span class="panel-icon">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
					</span>
					<div>
						<h2>AI 服务</h2>
						<p>配置接口格式、服务地址、API Key 和模型。</p>
					</div>
				</div>

				<div class="field-grid ai-grid">
					<label class="field">
						<span>接口格式</span>
						<select v-model="form.api_format">
							<option value="openai_chat_completions">OpenAI Chat Completions</option>
							<option value="anthropic_messages">Anthropic Messages</option>
						</select>
					</label>
				<label class="field">
					<span>模型</span>
					<div class="model-field">
						<select v-if="models.length" v-model="form.model" :disabled="modelsLoading">
							<option v-if="form.model && !models.includes(form.model)" :value="form.model">{{ form.model }}（当前）</option>
							<option v-for="m in models" :key="m" :value="m">{{ m }}</option>
						</select>
						<input v-else v-model.trim="form.model" type="text" :placeholder="modelPlaceholder" :disabled="modelsLoading" />
						<button type="button" class="ghost-btn small" :disabled="modelsLoading || !form.endpoint || !form.api_key" @click="fetchModels()">
							{{ modelsLoading ? '获取中…' : '刷新列表' }}
						</button>
					</div>
					<span v-if="modelsError" class="field-hint error">{{ modelsError }}</span>
				</label>
					<label class="field">
						<span>接口地址</span>
						<input v-model.trim="form.endpoint" type="url" :placeholder="endpointPlaceholder" />
					</label>
					<label class="field">
						<span>API Key</span>
						<input v-model.trim="form.api_key" type="password" autocomplete="off" placeholder="sk-..." />
					</label>
					<label class="field compact-field">
						<span>请求超时（秒）</span>
						<input v-model.number="form.timeout_seconds" type="number" min="5" max="300" />
					</label>
				</div>

				<div class="ai-actions">
					<button class="ghost-btn" :disabled="testing || saving || loading" @click="testLlm">
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17 10 11 4 5"/><path d="M12 19h8"/></svg>
						{{ testing ? '测试中...' : '测试已保存配置' }}
					</button>
					<span v-if="testMessage" :class="['test-result', testOk ? 'ok' : 'bad']">{{ testMessage }}</span>
				</div>

				<footer class="meta-row path-row">
					<span>配置文件</span>
					<strong>{{ settingsPath || '尚未同步' }}</strong>
				</footer>
			</section>

			<section class="settings-panel wide">
				<div class="panel-title">
					<span class="panel-icon">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="m22 6-10 7L2 6"/></svg>
					</span>
					<div>
						<h2>邮件扫描</h2>
						<p>调整扫描频率和单次处理数量。</p>
					</div>
				</div>

				<div class="field-grid compact">
					<label class="field">
						<span>扫描间隔（分钟）</span>
						<input v-model.number="form.scan_interval" type="number" min="1" max="1440" />
					</label>
					<label class="field">
						<span>单次最大邮件数</span>
						<input v-model.number="form.max_mails" type="number" min="1" max="500" />
					</label>
				</div>

				<footer class="meta-row">
					<span>最后更新</span>
					<strong>{{ updatedAtText }}</strong>
				</footer>
			</section>
		</main>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { api } from '@/utils/api'

interface SettingsResponse {
	auto_launch: boolean
	minimize_to_tray: boolean
	api_format: ApiFormat
	model: string
	endpoint: string
	api_key: string
	timeout_seconds: number
	scan_interval: number
	max_mails: number
	updated_at: string
	settings_path: string
}

type ApiFormat = 'openai_chat_completions' | 'anthropic_messages'
type SettingsForm = Omit<SettingsResponse, 'updated_at'>

interface LlmTestResponse {
	ok: boolean
	api_format: ApiFormat
	model: string
	message: string
	response_preview: string
}

interface LlmModelsResponse {
	ok: boolean
	models: string[]
	message: string
}

const form = reactive<SettingsForm>({
	auto_launch: false,
	minimize_to_tray: true,
	api_format: 'openai_chat_completions',
	model: '',
	endpoint: '',
	api_key: '',
	timeout_seconds: 60,
	scan_interval: 15,
	max_mails: 50,
	settings_path: ''
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const error = ref('')
const savedMessage = ref('')
const testMessage = ref('')
const testOk = ref(false)
const updatedAt = ref('')
const settingsPath = ref('')

const models = ref<string[]>([])
const modelsLoading = ref(false)
const modelsError = ref('')

const endpointPlaceholder = computed(() => {
	return form.api_format === 'anthropic_messages'
		? 'https://api.anthropic.com/v1'
		: 'https://api.openai.com/v1'
})

const modelPlaceholder = computed(() => {
	return form.api_format === 'anthropic_messages'
		? 'claude-3-5-sonnet-latest'
		: 'gpt-4o'
})

const updatedAtText = computed(() => {
	if (!updatedAt.value) return '尚未同步'
	const date = new Date(updatedAt.value)
	if (Number.isNaN(date.getTime())) return updatedAt.value
	return date.toLocaleString('zh-CN', { hour12: false })
})

function applySettings(data: SettingsResponse) {
	form.auto_launch = data.auto_launch
	form.minimize_to_tray = data.minimize_to_tray
	form.api_format = data.api_format || 'openai_chat_completions'
	form.model = data.model || ''
	form.endpoint = data.endpoint || ''
	form.api_key = data.api_key || ''
	form.timeout_seconds = data.timeout_seconds || 60
	form.scan_interval = data.scan_interval || 15
	form.max_mails = data.max_mails || 50
	form.settings_path = data.settings_path || ''
	updatedAt.value = data.updated_at
	settingsPath.value = data.settings_path || ''
}

async function loadSettings() {
	loading.value = true
	error.value = ''
	savedMessage.value = ''
	testMessage.value = ''

	try {
		const data = await api.get<SettingsResponse>('/api/settings')
		applySettings(data)
		fetchModels(false)
	} catch (err) {
		error.value = err instanceof Error ? err.message : '读取设置失败'
	} finally {
		loading.value = false
	}
}

async function saveSettings() {
	saving.value = true
	error.value = ''
	savedMessage.value = ''
	testMessage.value = ''

	try {
		const payload: SettingsForm = {
			...form,
			timeout_seconds: Math.max(5, Number(form.timeout_seconds) || 60),
			scan_interval: Math.max(1, Number(form.scan_interval) || 15),
			max_mails: Math.max(1, Number(form.max_mails) || 50),
			settings_path: form.settings_path
		}
		const data = await api.put<SettingsResponse>('/api/settings', payload)
		applySettings(data)
		savedMessage.value = '设置已保存'
	} catch (err) {
		error.value = err instanceof Error ? err.message : '保存设置失败'
	} finally {
		saving.value = false
	}
}

async function testLlm() {
	testing.value = true
	error.value = ''
	savedMessage.value = ''
	testMessage.value = ''
	testOk.value = false

	try {
		const data = await api.post<LlmTestResponse>('/api/settings/test-llm', {})
		testOk.value = data.ok
		testMessage.value = data.response_preview
			? `${data.message}：${data.response_preview}`
			: data.message
	} catch (err) {
		testMessage.value = err instanceof Error ? err.message : 'LLM 连接测试失败'
	} finally {
		testing.value = false
	}
}

async function fetchModels(showError = true) {
	const endpoint = form.endpoint.trim()
	const apiKey = form.api_key.trim()
	if (!endpoint || !apiKey) {
		models.value = []
		modelsError.value = ''
		return
	}
	modelsLoading.value = true
	modelsError.value = ''
	try {
		const data = await api.post<LlmModelsResponse>('/api/settings/llm-models', {
			api_format: form.api_format,
			endpoint,
			api_key: apiKey,
		})
		if (data.ok && data.models.length) {
			models.value = data.models
		} else {
			models.value = []
			if (showError) modelsError.value = data.message
		}
	} catch (err) {
		models.value = []
		if (showError) modelsError.value = err instanceof Error ? err.message : '获取模型列表失败'
	} finally {
		modelsLoading.value = false
	}
}

watchDebounced(
	() => [form.endpoint, form.api_key, form.api_format],
	() => fetchModels(false),
	{ debounce: 700 },
)

onMounted(loadSettings)
</script>

<style scoped>
.settings-page {
	min-height: 100%;
	padding: 40px clamp(24px, 4vw, 56px);
	color: var(--text-primary);
}

.settings-header {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 24px;
	margin-bottom: 24px;
}

h1,
h2,
p {
	margin: 0;
}

h1 {
	font-family: var(--font-display);
	font-size: 22px;
	font-weight: 600;
	line-height: 1.3;
	letter-spacing: 0;
}

.settings-header p,
.panel-title p,
.toggle-row small,
.meta-row {
	color: var(--text-secondary);
}

.settings-header p {
	margin-top: 12px;
	font-size: 15px;
}

.header-actions {
	display: flex;
	gap: 10px;
	flex-wrap: wrap;
}

.ghost-btn,
.primary-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 8px;
	min-height: 40px;
	padding: 0 16px;
	border-radius: var(--radius-md);
	border: 1px solid var(--border);
	color: var(--text-primary);
	transition: all var(--transition-base);
}

.ghost-btn {
	background: var(--bg-elevated);
}

.primary-btn {
	border-color: transparent;
	background: var(--accent);
	color: #061018;
	font-weight: 700;
}

.ghost-btn:hover:not(:disabled),
.primary-btn:hover:not(:disabled) {
	transform: translateY(-1px);
	box-shadow: var(--shadow-glow);
}

.ghost-btn:disabled,
.primary-btn:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}

.notice {
	margin-bottom: 18px;
	padding: 12px 14px;
	border-radius: var(--radius-md);
	border: 1px solid var(--border);
	background: var(--bg-elevated);
}

.notice.error {
	color: #FCA5A5;
	border-color: rgba(239, 68, 68, 0.35);
	background: rgba(239, 68, 68, 0.1);
}

.notice.success {
	color: #86EFAC;
	border-color: rgba(34, 197, 94, 0.32);
	background: rgba(34, 197, 94, 0.1);
}

.settings-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 16px;
}

.settings-panel {
	padding: 26px;
	border: 1px solid var(--border);
	border-radius: var(--radius-lg);
	background: var(--bg-elevated);
	box-shadow: var(--shadow-md);
}

.settings-panel.wide {
	grid-column: span 2;
}

.panel-title {
	display: flex;
	align-items: flex-start;
	gap: 12px;
	margin-bottom: 20px;
}

.panel-icon {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 36px;
	height: 36px;
	flex: 0 0 auto;
	border-radius: var(--radius-md);
	background: var(--accent-glow);
	color: var(--accent);
}

.panel-title h2 {
	font-family: var(--font-display);
	font-size: 16px;
	font-weight: 600;
	line-height: 1.3;
}

.panel-title p {
	margin-top: 5px;
	font-size: 13px;
}

.toggle-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 18px;
	padding: 16px 0;
	border-top: 1px solid var(--border);
}

.toggle-row span {
	display: grid;
	gap: 5px;
}

.toggle-row strong,
.field span {
	font-size: 14px;
	font-weight: 600;
	color: var(--text-primary);
	letter-spacing: 0.01em;
}

.toggle-row small {
	font-size: 12px;
	line-height: 1.5;
}

.toggle-row input[type='checkbox'] {
	width: 44px;
	height: 24px;
	flex: 0 0 auto;
	appearance: none;
	border-radius: 999px;
	border: 1px solid var(--border-hover);
	background: var(--bg-hover);
	cursor: pointer;
	position: relative;
	transition: all var(--transition-base);
}

.toggle-row input[type='checkbox']::after {
	content: '';
	position: absolute;
	width: 18px;
	height: 18px;
	top: 2px;
	left: 2px;
	border-radius: 50%;
	background: var(--text-secondary);
	transition: all var(--transition-base);
}

.toggle-row input[type='checkbox']:checked {
	border-color: var(--accent);
	background: rgba(79, 195, 247, 0.24);
}

.toggle-row input[type='checkbox']:checked::after {
	left: 22px;
	background: var(--accent);
}

.field-grid {
	display: grid;
	grid-template-columns: 0.8fr 1.2fr;
	gap: 14px;
}

.field-grid.compact {
	grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field {
	display: grid;
	gap: 8px;
}

.field input,
.field select {
	width: 100%;
	height: 42px;
	padding: 0 13px;
	border: 1px solid var(--border);
	border-radius: var(--radius-md);
	background: var(--bg-primary);
	color: var(--text-primary);
	outline: none;
	transition: all var(--transition-base);
}

.field select {
	appearance: none;
	cursor: pointer;
}

.field input:focus,
.field select:focus {
	border-color: var(--accent);
	box-shadow: 0 0 0 3px var(--accent-glow);
}

.field input::placeholder {
	color: var(--text-muted);
}

.ai-grid {
	grid-template-columns: repeat(2, minmax(0, 1fr));
}

.model-field {
	display: flex;
	gap: 8px;
	align-items: center;
}

.model-field select,
.model-field input {
	flex: 1;
	min-width: 0;
}

.ghost-btn.small {
	height: 42px;
	white-space: nowrap;
	padding: 0 12px;
}

.field-hint {
	font-size: 12px;
	color: var(--text-muted);
}

.field-hint.error {
	color: #e5484d;
}

.compact-field {
	max-width: 220px;
}

.ai-actions {
	display: flex;
	align-items: center;
	gap: 12px;
	flex-wrap: wrap;
	margin-top: 18px;
}

.test-result {
	font-size: 13px;
	line-height: 1.5;
}

.test-result.ok {
	color: #86EFAC;
}

.test-result.bad {
	color: #FCA5A5;
}

.path-row strong {
	overflow-wrap: anywhere;
	font-family: var(--font-mono);
	font-size: 12px;
}

.meta-row {
	display: flex;
	justify-content: space-between;
	gap: 14px;
	margin-top: 20px;
	padding-top: 16px;
	border-top: 1px solid var(--border);
	font-size: 13px;
}

.meta-row strong {
	color: var(--text-primary);
	font-weight: 600;
}

@media (max-width: 860px) {
	.settings-header {
		align-items: flex-start;
		flex-direction: column;
	}

	.settings-grid,
	.field-grid,
	.field-grid.compact {
		grid-template-columns: 1fr;
	}

	.settings-panel.wide {
		grid-column: auto;
	}
}
</style>
