<script setup lang="ts">
/**
 * AiChatPanel — AI 实验室对话面板
 *
 * 交互模式参考 MoviePilot AgentAssistantPanel：
 * - SSE 流式渲染：rAF 批量应用 delta，markdown 96ms 节流重渲染（AiMarkdownContent）
 * - 消息按 segments（文本段 / 工具卡片 / 技能 / 思考 / 警告）交错渲染
 * - 发送/停止切换按钮（AbortController 中止，保留已收到的部分内容）
 * - 智能滚动：近底部才自动跟随，上翻时显示回到底部按钮
 * - 会话历史 localStorage 持久化
 * - 斜杠命令：输入 / 选择技能，带 skill_id 发送
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { api, apiFetch } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import AiMarkdownContent from './AiMarkdownContent.vue'
import 'highlight.js/styles/github-dark.css'

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || ''
const STORAGE_KEY = 'ai_lab_chat_messages_v1'
const MAX_PERSISTED_MESSAGES = 50
const MAX_PERSISTED_RESULT_CHARS = 2000
const SCROLL_FOLLOW_THRESHOLD = 80

// ---------- 类型 ----------
interface ToolParamInfo {
  name: string
  type: string
  description?: string
  required?: boolean
}

interface ToolInfo {
  name: string
  description?: string
  category?: string
  parameters?: ToolParamInfo[]
}

interface SkillInfo {
  id: string
  name?: string
  description?: string
  enabled?: boolean
  triggers?: string[]
}

type ChatSegment =
  | { type: 'text'; content: string }
  | {
      type: 'tool'
      toolName: string
      args?: Record<string, unknown>
      message?: string
      result?: any
      success?: boolean
      status: 'running' | 'done' | 'error'
    }
  | { type: 'skill'; skillName: string }
  | { type: 'thinking'; content: string }
  | { type: 'warning'; message: string }

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  segments: ChatSegment[]
  status: 'streaming' | 'done' | 'error' | 'aborted'
  skillId?: string
  skillName?: string
}

// ---------- 状态 ----------
const messages = ref<ChatMessage[]>([])
const chatInput = ref('')
const isBusy = ref(false)
const useTools = ref(true)

const tools = ref<ToolInfo[]>([])
const skills = ref<SkillInfo[]>([])

const scrollerEl = ref<HTMLElement | null>(null)
const composerEl = ref<HTMLTextAreaElement | null>(null)
const pendingSkill = ref<SkillInfo | null>(null)

// ---------- 多会话 ----------
interface SessionMeta {
  id: string
  title: string
  updated_at: number
  message_count: number
}

const sessions = ref<SessionMeta[]>([])
const currentSessionId = ref<string | null>(null)
const historyOpen = ref(false)
// Agent 内部历史快照（含摘要/工具消息），随会话持久化并在下轮请求回传
const agentHistory = ref<any[] | null>(null)

let abortController: AbortController | null = null
let idCounter = 0

function createId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${Date.now()}-${idCounter}`
}

// ---------- 工具/技能信息 ----------
const toolInfoMap = computed(() => {
  const map: Record<string, ToolInfo> = {}
  for (const t of tools.value) map[t.name] = t
  return map
})

function toolCategory(name: string): string {
  return toolInfoMap.value[name]?.category || ''
}

async function fetchLists() {
  const [t, s] = await Promise.all([
    apiFetch<any[]>('/api/assistant/tools').catch(() => []),
    apiFetch<any[]>('/api/assistant/skills').catch(() => []),
  ])
  tools.value = Array.isArray(t) ? t : []
  skills.value = Array.isArray(s) ? s : []
}

async function fetchBaseConfig() {
  try {
    const data = await apiFetch<any>('/api/assistant/config')
    if (data && typeof data.use_tools === 'boolean') useTools.value = data.use_tools
  } catch {
    // 配置加载失败不阻塞对话
  }
}

async function persistUseTools() {
  try {
    await api.post('/api/assistant/config', { use_tools: useTools.value })
    success(useTools.value ? '已允许 AI 调用工具执行操作（全局生效，含 Telegram 默认值）' : '已切换为仅聊天模式：AI 无法执行操作，但响应更快')
  } catch {
    // 非关键
  }
}

// ---------- Markdown 文本聚合 ----------
function messageText(msg: ChatMessage): string {
  if (msg.role === 'user') return msg.content
  const text = msg.segments
    .filter((s): s is Extract<ChatSegment, { type: 'text' }> => s.type === 'text')
    .map(s => s.content)
    .join('\n\n')
    .trim()
  if (text) return text
  return msg.segments
    .filter((s): s is Extract<ChatSegment, { type: 'tool' }> => s.type === 'tool')
    .map(s => s.message || s.toolName)
    .filter(Boolean)
    .join('\n')
}

function buildHistoryPayload() {
  return messages.value
    .filter(m => !(m.role === 'assistant' && (m.status === 'streaming' || m.status === 'error')))
    .map(m => ({ role: m.role, content: messageText(m) }))
    .filter(m => m.content)
}

// ---------- 流式状态机 ----------
function appendToCurrentTextSegment(msg: ChatMessage, piece: string) {
  const last = msg.segments[msg.segments.length - 1]
  if (last && last.type === 'text') {
    last.content += piece
  } else {
    msg.segments.push({ type: 'text', content: piece })
  }
}

// delta 用 requestAnimationFrame 批量应用，避免高频触发响应式更新
let pendingDelta = ''
let pendingDeltaMsg: ChatMessage | null = null
let pendingDeltaFrame: number | null = null

function queuePendingDelta(msg: ChatMessage, piece: string) {
  if (!piece) return
  if (pendingDeltaMsg && pendingDeltaMsg !== msg) flushPendingDelta()
  pendingDeltaMsg = msg
  pendingDelta += piece
  if (pendingDeltaFrame === null) {
    pendingDeltaFrame = requestAnimationFrame(() => {
      pendingDeltaFrame = null
      flushPendingDelta()
    })
  }
}

function flushPendingDelta() {
  if (pendingDeltaFrame !== null) {
    cancelAnimationFrame(pendingDeltaFrame)
    pendingDeltaFrame = null
  }
  if (pendingDeltaMsg && pendingDelta) {
    appendToCurrentTextSegment(pendingDeltaMsg, pendingDelta)
    scheduleScrollUpdate(false)
  }
  pendingDelta = ''
  pendingDeltaMsg = null
}

function markRunningToolsDone(msg: ChatMessage) {
  for (const s of msg.segments) {
    if (s.type === 'tool' && s.status === 'running') s.status = 'done'
  }
}

function applyStreamEvent(type: string, event: any, msg: ChatMessage) {
  if (type === 'stream') {
    queuePendingDelta(msg, event?.content || '')
    return
  }
  flushPendingDelta()

  switch (type) {
    case 'skill':
      msg.segments.push({ type: 'skill', skillName: event?.skill_name || event?.skill_id || '技能' })
      break

    case 'thinking':
      if (event?.content) msg.segments.push({ type: 'thinking', content: event.content })
      break

    case 'tool_call':
      markRunningToolsDone(msg)
      msg.segments.push({
        type: 'tool',
        toolName: event?.tool_name || '',
        args: event?.arguments,
        message: event?.message,
        status: 'running',
      })
      break

    case 'tool_result': {
      const found = [...msg.segments]
        .reverse()
        .find(s => s.type === 'tool' && s.toolName === (event?.tool_name || '') && s.status === 'running')
      if (found && found.type === 'tool') {
        found.result = event?.result
        found.success = event?.success
        found.message = event?.message || found.message
        found.status = event?.success ? 'done' : 'error'
      }
      break
    }

    case 'response': {
      const content = event?.content || ''
      const last = msg.segments[msg.segments.length - 1]
      if (last && last.type === 'text') {
        last.content = content
      } else {
        msg.segments.push({ type: 'text', content })
      }
      break
    }

    case 'warning':
      if (event?.message) msg.segments.push({ type: 'warning', message: event.message })
      break

    case 'history':
      // Agent 内部历史快照（含摘要），随会话保存、下轮回传
      if (Array.isArray(event?.messages)) agentHistory.value = event.messages
      break

    case 'error':
      msg.segments.push({ type: 'warning', message: `错误: ${event?.message || '未知错误'}` })
      msg.status = 'error'
      break
  }
  scheduleScrollUpdate(false)
}

function finalizeMessage(msg: ChatMessage, status: 'done' | 'error' | 'aborted') {
  markRunningToolsDone(msg)
  const empty =
    msg.segments.length === 0 ||
    (msg.segments.length === 1 && msg.segments[0].type === 'text' && !msg.segments[0].content)
  if ((status === 'aborted' || status === 'error') && empty) {
    const idx = messages.value.indexOf(msg)
    if (idx >= 0) messages.value.splice(idx, 1)
    return
  }
  msg.status = status
}

// ---------- SSE 读取 ----------
async function readSseStream(res: Response, msg: ChatMessage) {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const consumeBlock = (block: string) => {
    let data = ''
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('data:')) data += (data ? '\n' : '') + line.slice(5).trimStart()
    }
    if (!data) return
    let event: any
    try {
      event = JSON.parse(data)
    } catch {
      return
    }
    applyStreamEvent(event?.type || '', event, msg)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    for (const b of blocks) consumeBlock(b)
  }
  buffer += decoder.decode()
  if (buffer.trim()) consumeBlock(buffer)
}

// ---------- 发送 / 停止 / 重新生成 ----------
function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

async function submitUserMessage(text: string, skill?: { id: string; name?: string } | null) {
  if (!currentSessionId.value) currentSessionId.value = createId('sess')
  messages.value.push({
    id: createId('user'),
    role: 'user',
    content: text,
    segments: [],
    status: 'done',
    skillId: skill?.id,
    skillName: skill?.name,
  })
  persistState()
  saveSession()
  scheduleScrollUpdate(true)
  await runCompletion(text, skill?.id)
}

async function sendMessage() {
  const text = chatInput.value.trim()
  if (!text || isBusy.value) return
  const skill = pendingSkill.value
  chatInput.value = ''
  pendingSkill.value = null
  autoResizeComposer()
  await submitUserMessage(text, skill)
}

async function sendQuick(text: string) {
  if (isBusy.value) return
  await submitUserMessage(text)
}

async function runCompletion(text: string, skillId?: string) {
  isBusy.value = true
  abortController = new AbortController()

  const assistantMsg: ChatMessage = {
    id: createId('assistant'),
    role: 'assistant',
    content: '',
    segments: [],
    status: 'streaming',
  }
  messages.value.push(assistantMsg)
  scheduleScrollUpdate(true)

  try {
    const res = await fetch(`${API_BASE}/api/assistant/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      signal: abortController.signal,
      body: JSON.stringify({
        messages: buildHistoryPayload(),
        stream: true,
        use_tools: useTools.value,
        skill_id: skillId || null,
        agent_history: useTools.value ? agentHistory.value : null,
      }),
    })

    if (!res.ok || !res.body) {
      let detail = `请求失败 (${res.status})`
      try {
        const data = await res.json()
        if (data?.detail) detail = data.detail
      } catch {
        // 非 JSON 响应体，用默认错误信息
      }
      throw new Error(detail)
    }

    await readSseStream(res, assistantMsg)
    finalizeMessage(assistantMsg, assistantMsg.status === 'error' ? 'error' : 'done')
  } catch (e: any) {
    flushPendingDelta()
    if (e?.name === 'AbortError') {
      finalizeMessage(assistantMsg, 'aborted')
    } else {
      const last = assistantMsg.segments[assistantMsg.segments.length - 1]
      const message = e?.message || '请求失败'
      if (last && last.type === 'warning') {
        last.message = message
      } else {
        assistantMsg.segments.push({ type: 'warning', message })
      }
      finalizeMessage(assistantMsg, 'error')
    }
  } finally {
    flushPendingDelta()
    isBusy.value = false
    abortController = null
    // 纯对话模式没有内部快照，清掉避免与工具模式互相污染
    if (!useTools.value) agentHistory.value = null
    persistState()
    saveSession()
    scheduleScrollUpdate(true)
  }
}

function stopGeneration() {
  abortController?.abort()
}

function regenerate() {
  if (isBusy.value) return
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'user') {
      const text = m.content
      const skill = m.skillId ? { id: m.skillId, name: m.skillName } : null
      messages.value.splice(i + 1)
      runCompletion(text, skill?.id)
      return
    }
  }
}

async function copyMessage(msg: ChatMessage) {
  try {
    await navigator.clipboard.writeText(messageText(msg))
    success('已复制到剪贴板')
  } catch {
    showError('复制失败')
  }
}

async function clearChat() {
  const ok = await confirm({
    title: '确认清空',
    content: '确定要清空当前对话记录吗？',
    confirmText: '确定清空',
    cancelText: '取消',
    confirmColor: 'error',
  })
  if (ok) {
    const id = currentSessionId.value
    messages.value = []
    agentHistory.value = null
    currentSessionId.value = null
    localStorage.removeItem(STORAGE_KEY)
    if (id) {
      api.delete(`/api/assistant/sessions/${id}`)
        .then(() => fetchSessions())
        .catch(() => {})
    }
  }
}

// ---------- 历史持久化 ----------
function compactSegments(segments: ChatSegment[]): ChatSegment[] {
  return segments.map(s => {
    if (s.type === 'tool' && s.result !== undefined) {
      let result = s.result
      try {
        const json = JSON.stringify(result)
        if (json && json.length > MAX_PERSISTED_RESULT_CHARS) {
          result = { _truncated: json.slice(0, MAX_PERSISTED_RESULT_CHARS) + '…' }
        }
      } catch {
        result = undefined
      }
      return { ...s, result }
    }
    return s
  })
}

function compactMessages(list: ChatMessage[]) {
  return list.map(m => ({
    id: m.id,
    role: m.role,
    content: m.role === 'user' ? m.content : messageText(m),
    status: m.status,
    skillId: m.skillId,
    skillName: m.skillName,
    segments: m.role === 'assistant' ? compactSegments(m.segments) : [],
  }))
}

function persistState() {
  try {
    const payload = {
      sessionId: currentSessionId.value,
      messages: compactMessages(messages.value.filter(m => m.status !== 'streaming').slice(-MAX_PERSISTED_MESSAGES)),
      agentHistory: agentHistory.value ? agentHistory.value.slice(-40) : null,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // 存储失败忽略
  }
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    // 兼容旧格式（纯数组，无会话概念）
    const list: any[] = Array.isArray(data) ? data : (data.messages || [])
    currentSessionId.value = Array.isArray(data) ? null : (data.sessionId || null)
    agentHistory.value = Array.isArray(data) ? null : (data.agentHistory || null)
    if (Array.isArray(list) && list.length) {
      messages.value = list.map((m: any) => ({
        id: m.id || createId(m.role === 'user' ? 'user' : 'assistant'),
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content || '',
        segments: Array.isArray(m.segments) ? m.segments : [],
        status: m.status === 'streaming' ? 'done' : m.status || 'done',
        skillId: m.skillId,
        skillName: m.skillName,
      }))
    }
  } catch {
    // 恢复失败忽略
  }
}

// ---------- 会话存取（服务端为权威，localStorage 仅作离线兜底） ----------
async function fetchSessions() {
  try {
    const data = await apiFetch<any[]>('/api/assistant/sessions')
    sessions.value = Array.isArray(data) ? data : []
  } catch {
    sessions.value = []
  }
}

async function saveSession() {
  const id = currentSessionId.value
  if (!id) return
  const display = compactMessages(messages.value.filter(m => m.status !== 'streaming'))
  if (!display.length) return
  try {
    const data = await api.put<any>(`/api/assistant/sessions/${id}`, {
      title: (display.find(m => m.role === 'user')?.content || '').slice(0, 24),
      messages: display,
      agent_history: agentHistory.value,
    })
    const meta = data?.session
    if (meta) {
      const idx = sessions.value.findIndex(s => s.id === id)
      if (idx >= 0) sessions.value[idx] = meta
      else sessions.value.unshift(meta)
    }
  } catch {
    // 保存失败不阻塞对话
  }
}

async function loadSession(id: string, silent = false) {
  if (isBusy.value) return
  try {
    const data = await apiFetch<any>(`/api/assistant/sessions/${id}`)
    const list: any[] = Array.isArray(data?.messages) ? data.messages : []
    messages.value = list.map((m: any) => ({
      id: m.id || createId(m.role === 'user' ? 'user' : 'assistant'),
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content || '',
      segments: Array.isArray(m.segments) ? m.segments : [],
      status: m.status === 'streaming' ? 'done' : m.status || 'done',
      skillId: m.skillId,
      skillName: m.skillName,
    }))
    currentSessionId.value = id
    agentHistory.value = Array.isArray(data?.agent_history) ? data.agent_history : null
    persistState()
    historyOpen.value = false
    await nextTick()
    scrollToBottom()
  } catch (e: any) {
    if (!silent) showError(e?.message || '加载会话失败')
  }
}

function newChat() {
  if (isBusy.value) return
  currentSessionId.value = null
  agentHistory.value = null
  messages.value = []
  persistState()
  historyOpen.value = false
  nextTick(() => composerEl.value?.focus())
}

async function removeSession(id: string) {
  try {
    await api.delete(`/api/assistant/sessions/${id}`)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) newChat()
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

function openHistoryDrawer() {
  fetchSessions()
  historyOpen.value = true
}

const currentTitle = computed(() => {
  const s = sessions.value.find(x => x.id === currentSessionId.value)
  if (s) return s.title
  return messages.value.length ? '当前对话' : '新对话'
})

function formatSessionTime(ts: number): string {
  if (!ts) return ''
  const diff = Date.now() - ts * 1000
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour} 小时前`
  const day = Math.floor(hour / 24)
  if (day < 30) return `${day} 天前`
  return new Date(ts * 1000).toLocaleDateString()
}

// ---------- 滚动跟随 ----------
let scrollShouldFollow = true
let scrollFrame: number | null = null
const showJumpButton = ref(false)

function isNearBottom(): boolean {
  const el = scrollerEl.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_FOLLOW_THRESHOLD
}

function handleScrollerScroll() {
  scrollShouldFollow = isNearBottom()
  showJumpButton.value = !scrollShouldFollow
}

function scheduleScrollUpdate(force = false) {
  if (force) {
    scrollShouldFollow = true
    showJumpButton.value = false
  }
  if (scrollFrame !== null) return
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
    const el = scrollerEl.value
    if (el && scrollShouldFollow) el.scrollTop = el.scrollHeight
  })
}

function scrollToBottom() {
  const el = scrollerEl.value
  if (el) {
    scrollShouldFollow = true
    showJumpButton.value = false
    el.scrollTop = el.scrollHeight
  }
}

// ---------- 斜杠命令 ----------
const slashMenuVisible = ref(false)
const slashActiveIndex = ref(0)

const slashQuery = computed(() => {
  const m = chatInput.value.match(/^\/(\S*)$/)
  return m ? m[1] : null
})

const slashFiltered = computed(() => {
  const q = slashQuery.value
  if (q === null) return []
  const needle = q.toLowerCase()
  return skills.value.filter(
    s =>
      s.enabled !== false &&
      (!needle ||
        (s.name || '').toLowerCase().includes(needle) ||
        (s.id || '').toLowerCase().includes(needle) ||
        (s.description || '').toLowerCase().includes(needle)),
  )
})

function updateSlashMenu() {
  if (slashQuery.value !== null && slashFiltered.value.length > 0) {
    slashMenuVisible.value = true
    if (slashActiveIndex.value >= slashFiltered.value.length) slashActiveIndex.value = 0
  } else {
    slashMenuVisible.value = false
  }
}

function selectSlashSkill(skill: SkillInfo) {
  pendingSkill.value = skill
  chatInput.value = ''
  slashMenuVisible.value = false
  autoResizeComposer()
  nextTick(() => composerEl.value?.focus())
}

function clearPendingSkill() {
  pendingSkill.value = null
  nextTick(() => composerEl.value?.focus())
}

// 供父组件调用：技能管理页「在对话中使用」
function useSkillInChat(skill: { id: string; name?: string }) {
  pendingSkill.value = { id: skill.id, name: skill.name || skill.id } as SkillInfo
  chatInput.value = ''
  nextTick(() => composerEl.value?.focus())
}

defineExpose({ useSkillInChat })

// ---------- 输入框 ----------
function autoResizeComposer() {
  const el = composerEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

watch(chatInput, () => {
  autoResizeComposer()
  updateSlashMenu()
})

function handleComposerKeydown(e: KeyboardEvent) {
  if (slashMenuVisible.value) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      slashActiveIndex.value = (slashActiveIndex.value + 1) % slashFiltered.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      slashActiveIndex.value =
        (slashActiveIndex.value - 1 + slashFiltered.value.length) % slashFiltered.value.length
      return
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      const skill = slashFiltered.value[slashActiveIndex.value]
      if (skill) selectSlashSkill(skill)
      return
    }
    if (e.key === 'Escape') {
      slashMenuVisible.value = false
      return
    }
  }
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing || (e as any).keyCode === 229) return
  e.preventDefault()
  sendMessage()
}

// ---------- 工具卡片展示 ----------
function formatArgs(args?: Record<string, unknown>): string[] {
  if (!args || typeof args !== 'object') return []
  return Object.entries(args).map(([k, v]) => {
    let value: string
    if (v === null || v === undefined) value = ''
    else if (typeof v === 'string') value = v
    else if (typeof v === 'object') value = JSON.stringify(v)
    else value = String(v)
    if (value.length > 120) value = value.slice(0, 120) + '…'
    return `${k}: ${value}`
  })
}

function formatResult(result: any): string {
  if (result === undefined || result === null) return ''
  try {
    const s = JSON.stringify(result, null, 2)
    return s.length > 4000 ? s.slice(0, 4000) + '\n…' : s
  } catch {
    return String(result)
  }
}

// 代码块复制按钮（事件委托）
async function handleContentClick(e: MouseEvent) {
  const target = (e.target as HTMLElement).closest?.('.ai-code-copy') as HTMLElement | null
  if (!target) return
  const block = target.closest('.ai-code-block')
  const code = block?.querySelector('code')?.textContent || ''
  try {
    await navigator.clipboard.writeText(code)
    target.textContent = '已复制'
    setTimeout(() => {
      target.textContent = '复制'
    }, 1500)
  } catch {
    // 忽略复制失败
  }
}

// ---------- 快捷提示词 ----------
const quickPrompts = [
  { icon: 'mdi-format-list-bulleted', label: '查看我的订阅', text: '查看我的订阅列表' },
  { icon: 'mdi-star-outline', label: '推荐新番', text: '推荐一些最近的热门新番' },
  { icon: 'mdi-download-outline', label: '下载任务', text: '最近的下载任务有哪些？' },
  { icon: 'mdi-heart-pulse', label: '系统状态', text: '检查一下系统运行状态' },
]

// ---------- 生命周期 ----------
onMounted(async () => {
  restoreState()
  fetchBaseConfig()
  fetchLists()
  await fetchSessions()
  // 服务端为权威：若本地记住的会话在服务端存在，用服务端版本覆盖本地快照
  if (currentSessionId.value && sessions.value.some(s => s.id === currentSessionId.value)) {
    await loadSession(currentSessionId.value, true)
  }
  await nextTick()
  scrollToBottom()
  composerEl.value?.focus()
})

onBeforeUnmount(() => {
  flushPendingDelta()
  if (scrollFrame !== null) cancelAnimationFrame(scrollFrame)
  abortController?.abort()
})
</script>

<template>
  <v-card
    class="glass-card ai-chat-card"
    style="height: calc(100vh - 280px); display: flex; flex-direction: column; position: relative"
  >
    <!-- 顶栏：历史会话 / 新对话 -->
    <div class="ai-chat-header px-3 py-1 d-flex align-center ga-1">
      <v-btn size="small" variant="text" prepend-icon="mdi-history" @click="openHistoryDrawer">历史会话</v-btn>
      <v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="newChat">新对话</v-btn>
      <v-spacer />
      <span class="ai-session-title text-caption text-medium-emphasis">{{ currentTitle }}</span>
    </div>
    <v-divider />

    <!-- 消息区 -->
    <div
      ref="scrollerEl"
      class="ai-chat-scroller flex-grow-1 overflow-y-auto pa-4"
      style="min-height: 0"
      @scroll="handleScrollerScroll"
      @click="handleContentClick"
    >
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="ai-chat-empty">
        <v-icon size="64" color="primary" class="mb-4">mdi-robot-outline</v-icon>
        <div class="text-h6 font-weight-medium">AI 助手</div>
        <div class="text-body-2 text-medium-emphasis mt-2">输入消息开始对话，支持工具调用与技能</div>
        <div class="ai-quick-prompts mt-6">
          <v-btn
            v-for="p in quickPrompts"
            :key="p.label"
            size="small"
            variant="tonal"
            rounded
            :prepend-icon="p.icon"
            @click="sendQuick(p.text)"
          >{{ p.label }}</v-btn>
        </div>
      </div>

      <div
        v-for="(msg, index) in messages"
        :key="msg.id"
        class="ai-message mb-4"
        :class="msg.role === 'user' ? 'ai-message--user' : 'ai-message--assistant'"
      >
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="d-flex flex-column align-end">
          <v-chip
            v-if="msg.skillName"
            size="x-small"
            color="info"
            variant="tonal"
            class="mb-1"
            prepend-icon="mdi-lightning-bolt-outline"
          >技能 · {{ msg.skillName }}</v-chip>
          <div class="ai-user-bubble">{{ msg.content }}</div>
        </div>

        <!-- 助手消息 -->
        <div v-else class="d-flex flex-column align-start">
          <div class="ai-assistant-bubble">
            <!-- 首个 token 前的打字动画 -->
            <div v-if="msg.status === 'streaming' && msg.segments.length === 0" class="ai-typing">
              <span /><span /><span />
            </div>

            <template v-for="(seg, si) in msg.segments" :key="si">
              <!-- 文本段 -->
              <div v-if="seg.type === 'text' && seg.content" class="ai-segment">
                <AiMarkdownContent
                  :content="seg.content"
                  :streaming="msg.status === 'streaming' && si === msg.segments.length - 1"
                />
              </div>

              <!-- 工具调用卡片 -->
              <div
                v-else-if="seg.type === 'tool'"
                class="ai-tool-card"
                :class="{ 'ai-tool-card--error': seg.status === 'error' }"
              >
                <div class="ai-tool-card__header">
                  <v-progress-circular
                    v-if="seg.status === 'running'"
                    indeterminate
                    size="14"
                    width="2"
                    color="primary"
                  />
                  <v-icon v-else-if="seg.status === 'error'" size="16" color="error">mdi-alert-circle-outline</v-icon>
                  <v-icon v-else size="16" color="success">mdi-check-circle-outline</v-icon>
                  <span class="ai-tool-card__name">{{ seg.toolName }}</span>
                  <span v-if="toolCategory(seg.toolName)" class="ai-tool-card__category">{{ toolCategory(seg.toolName) }}</span>
                  <v-chip
                    size="x-small"
                    variant="tonal"
                    :color="seg.status === 'running' ? 'info' : seg.status === 'error' ? 'error' : 'success'"
                  >
                    {{ seg.status === 'running' ? '执行中' : seg.status === 'error' ? '失败' : '完成' }}
                  </v-chip>
                </div>
                <div v-if="seg.message && seg.status !== 'running'" class="ai-tool-card__message">{{ seg.message }}</div>
                <div v-if="formatArgs(seg.args).length" class="ai-tool-card__args">
                  <div v-for="line in formatArgs(seg.args)" :key="line" class="ai-tool-card__arg">{{ line }}</div>
                </div>
                <details v-if="seg.status !== 'running' && formatResult(seg.result)" class="ai-tool-card__details">
                  <summary>查看结果</summary>
                  <pre>{{ formatResult(seg.result) }}</pre>
                </details>
              </div>

              <!-- 技能触发 -->
              <div v-else-if="seg.type === 'skill'" class="ai-skill-chip">
                <v-icon size="14">mdi-lightning-bolt-outline</v-icon>
                <span>技能 · {{ seg.skillName }}</span>
              </div>

              <!-- 思考过程 -->
              <details v-else-if="seg.type === 'thinking'" class="ai-thinking">
                <summary>思考过程</summary>
                <div class="ai-thinking__body">{{ seg.content }}</div>
              </details>

              <!-- 警告 / 错误 -->
              <v-alert
                v-else-if="seg.type === 'warning'"
                density="compact"
                type="warning"
                variant="tonal"
                class="ai-segment"
              >{{ seg.message }}</v-alert>
            </template>
          </div>

          <!-- 消息操作 -->
          <div v-if="msg.status !== 'streaming'" class="ai-message-actions">
            <v-icon
              size="16"
              class="ai-message-action"
              title="复制"
              @click="copyMessage(msg)"
            >mdi-content-copy</v-icon>
            <v-icon
              v-if="index === messages.length - 1 && !isBusy"
              size="16"
              class="ai-message-action"
              title="重新生成"
              @click="regenerate"
            >mdi-refresh</v-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- 回到底部 -->
    <transition name="ai-fade">
      <v-btn
        v-if="showJumpButton"
        class="ai-jump-bottom"
        size="small"
        icon="mdi-arrow-down"
        variant="tonal"
        color="primary"
        @click="scrollToBottom"
      />
    </transition>

    <v-divider />

    <!-- 输入区 -->
    <div class="ai-composer pa-3">
      <div class="ai-composer__box">
        <!-- 斜杠命令技能菜单 -->
        <div v-if="slashMenuVisible" class="ai-slash-menu">
          <div class="ai-slash-menu__hint">选择技能 · ↑↓ 切换 / Enter 选择 / Esc 关闭</div>
          <div
            v-for="(s, i) in slashFiltered"
            :key="s.id"
            class="ai-slash-menu__item"
            :class="{ 'ai-slash-menu__item--active': i === slashActiveIndex }"
            @mousedown.prevent
            @click="selectSlashSkill(s)"
          >
            <v-icon size="16" color="primary">mdi-lightning-bolt-outline</v-icon>
            <span class="ai-slash-menu__name">{{ s.name || s.id }}</span>
            <span class="ai-slash-menu__desc">{{ s.description }}</span>
          </div>
        </div>

        <!-- 本轮指定技能 -->
        <div v-if="pendingSkill" class="ai-pending-skill">
          <v-icon size="14" color="primary">mdi-lightning-bolt-outline</v-icon>
          <span>本轮使用技能：{{ pendingSkill.name || pendingSkill.id }}</span>
          <v-icon size="14" class="ai-pending-skill__close" title="取消" @click="clearPendingSkill">mdi-close</v-icon>
        </div>

        <div class="d-flex ga-2 align-end">
          <textarea
            ref="composerEl"
            v-model="chatInput"
            class="ai-composer__input"
            rows="1"
            placeholder="输入消息…（/ 选择技能，Enter 发送，Shift+Enter 换行）"
            @keydown="handleComposerKeydown"
            @blur="slashMenuVisible = false"
          />
          <v-btn
            class="ai-composer__send"
            :color="isBusy ? 'error' : 'primary'"
            variant="tonal"
            :icon="isBusy ? 'mdi-stop' : 'mdi-send'"
            :disabled="!isBusy && !chatInput.trim()"
            :title="isBusy ? '停止生成' : '发送'"
            @click="isBusy ? stopGeneration() : sendMessage()"
          />
        </div>

        <div class="ai-composer__footer">
          <div class="d-flex align-center">
            <v-switch
              v-model="useTools"
              :label="useTools ? '允许 AI 操作' : '仅聊天'"
              density="compact"
              hide-details
              color="primary"
              class="ai-composer__switch"
              @update:model-value="persistUseTools"
            />
            <v-tooltip location="top" max-width="360">
              <template #activator="{ props: tooltipProps }">
                <v-icon v-bind="tooltipProps" size="14" class="ai-tools-hint">mdi-information-outline</v-icon>
              </template>
              <span>开启：AI 可调用搜索、订阅、整理、系统等工具替你执行实际操作，对话中会显示工具调用过程。关闭：仅能聊天问答，无法执行任何操作，但响应更快、更省 token。此设置全局生效，也是 Telegram Bot 未单独设置时的默认值。</span>
            </v-tooltip>
          </div>
          <v-spacer />
          <v-btn
            size="x-small"
            variant="text"
            color="error"
            prepend-icon="mdi-delete-outline"
            :disabled="messages.length === 0 || isBusy"
            @click="clearChat"
          >清空对话</v-btn>
        </div>
      </div>
    </div>
  </v-card>

  <!-- 历史会话 -->
  <v-dialog v-model="historyOpen" max-width="460" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-history</v-icon>
        <span class="text-subtitle-1 font-weight-bold">对话历史</span>
        <v-spacer />
        <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-plus" @click="newChat">新对话</v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-2" style="max-height: 60vh; overflow-y: auto">
        <div v-if="sessions.length === 0" class="text-center text-medium-emphasis pa-6">
          暂无历史会话
        </div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="ai-session-item"
          :class="{ 'ai-session-item--active': s.id === currentSessionId }"
          @click="loadSession(s.id)"
        >
          <div class="ai-session-item__body">
            <div class="ai-session-item__title">{{ s.title }}</div>
            <div class="ai-session-item__meta">{{ s.message_count }} 条消息 · {{ formatSessionTime(s.updated_at) }}</div>
          </div>
          <v-icon size="16" class="ai-session-item__delete" title="删除会话" @click.stop="removeSession(s.id)">mdi-delete-outline</v-icon>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* ---------- 顶栏 / 会话 ---------- */
.ai-chat-header {
  flex: none;
}

.ai-session-title {
  max-width: 50%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}

.ai-session-item:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}

.ai-session-item--active {
  background: rgba(var(--v-theme-primary), 0.14);
}

.ai-session-item__body {
  flex: 1;
  min-width: 0;
}

.ai-session-item__title {
  font-size: 0.85rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-session-item__meta {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-top: 2px;
}

.ai-session-item__delete {
  opacity: 0.4;
}

.ai-session-item__delete:hover {
  opacity: 1;
  color: rgb(var(--v-theme-error));
}

/* ---------- 消息区 ---------- */
.ai-chat-scroller {
  scroll-behavior: auto;
}

.ai-chat-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.ai-quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 480px;
}

.ai-message--user,
.ai-message--assistant {
  display: flex;
}

.ai-message--user {
  justify-content: flex-end;
}

.ai-message--assistant {
  justify-content: flex-start;
}

.ai-user-bubble {
  max-width: min(78%, 560px);
  padding: 8px 14px;
  border-radius: 14px 14px 4px 14px;
  background: rgba(var(--v-theme-primary), 0.16);
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.875rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.ai-assistant-bubble {
  max-width: 100%;
  width: fit-content;
  min-width: 0;
  padding: 10px 14px;
  border-radius: 14px 14px 14px 4px;
  background: rgba(var(--v-theme-surface-variant), 0.4);
  color: rgb(var(--v-theme-on-surface));
}

.ai-segment + .ai-segment,
.ai-segment + .ai-tool-card,
.ai-tool-card + .ai-segment,
.ai-tool-card + .ai-tool-card {
  margin-top: 8px;
}

.ai-segment {
  min-width: 0;
}

/* 打字动画 */
.ai-typing {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 2px;
}

.ai-typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  opacity: 0.4;
  animation: ai-typing-bounce 1.2s infinite ease-in-out;
}

.ai-typing span:nth-child(2) {
  animation-delay: 0.15s;
}

.ai-typing span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes ai-typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

/* 工具调用卡片 */
.ai-tool-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  padding: 8px 12px;
  background: rgba(var(--v-theme-surface), 0.6);
  min-width: 0;
  max-width: 100%;
}

.ai-tool-card--error {
  border-color: rgba(var(--v-theme-error), 0.4);
}

.ai-tool-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-tool-card__name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
}

.ai-tool-card__category {
  font-size: 0.7rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.ai-tool-card__message {
  margin-top: 4px;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.ai-tool-card__args {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-tool-card__arg {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.65);
  word-break: break-all;
}

.ai-tool-card__details {
  margin-top: 4px;
}

.ai-tool-card__details summary {
  font-size: 0.72rem;
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  user-select: none;
}

.ai-tool-card__details pre {
  margin: 6px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.35);
  color: rgba(var(--v-theme-on-surface), 0.85);
  font-size: 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow: auto;
  max-height: 220px;
}

/* 技能 chip */
.ai-skill-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.12);
  width: fit-content;
}

/* 思考过程 */
.ai-thinking {
  border-left: 2px solid rgba(var(--v-theme-on-surface), 0.2);
  padding-left: 10px;
}

.ai-thinking summary {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  cursor: pointer;
  user-select: none;
}

.ai-thinking__body {
  margin-top: 4px;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

/* 消息操作 */
.ai-message-actions {
  display: flex;
  gap: 4px;
  margin-top: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.ai-message--assistant:hover .ai-message-actions {
  opacity: 1;
}

.ai-message-action {
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.5);
  padding: 2px;
  border-radius: 4px;
}

.ai-message-action:hover {
  color: rgb(var(--v-theme-primary));
}

/* 回到底部 */
.ai-jump-bottom {
  position: absolute;
  right: 20px;
  bottom: 150px;
  z-index: 3;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.ai-fade-enter-active,
.ai-fade-leave-active {
  transition: opacity 0.2s;
}

.ai-fade-enter-from,
.ai-fade-leave-to {
  opacity: 0;
}

/* ---------- 输入区 ---------- */
.ai-composer__box {
  position: relative;
}

.ai-composer__input {
  flex-grow: 1;
  resize: none;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.875rem;
  line-height: 1.55;
  font-family: inherit;
  color: rgb(var(--v-theme-on-surface));
  background: transparent;
  outline: none;
  max-height: 160px;
  transition: border-color 0.15s;
}

.ai-composer__input:focus {
  border-color: rgb(var(--v-theme-primary));
}

.ai-composer__input::placeholder {
  color: rgba(var(--v-theme-on-surface), 0.4);
}

.ai-composer__footer {
  display: flex;
  align-items: center;
  margin-top: 4px;
}

.ai-composer__switch {
  flex: none;
  transform: scale(0.85);
  transform-origin: left center;
}

.ai-tools-hint {
  color: rgba(var(--v-theme-on-surface), 0.45);
  cursor: help;
  margin-left: -2px;
}

/* 斜杠命令菜单 */
.ai-slash-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 260px;
  overflow-y: auto;
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  z-index: 4;
  padding: 6px;
}

.ai-slash-menu__hint {
  font-size: 0.7rem;
  color: rgba(var(--v-theme-on-surface), 0.45);
  padding: 4px 10px 6px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  margin-bottom: 4px;
}

.ai-slash-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  min-width: 0;
}

.ai-slash-menu__item--active,
.ai-slash-menu__item:hover {
  background: rgba(var(--v-theme-primary), 0.1);
}

.ai-slash-menu__name {
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}

.ai-slash-menu__desc {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* 本轮指定技能 */
.ai-pending-skill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  margin-bottom: 6px;
  border-radius: 999px;
  font-size: 0.72rem;
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.12);
}

.ai-pending-skill__close {
  cursor: pointer;
  opacity: 0.6;
}

.ai-pending-skill__close:hover {
  opacity: 1;
}
</style>
