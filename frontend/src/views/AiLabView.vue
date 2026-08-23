<script setup lang="ts">
/**
 * AiLabView — AI 实验室
 *
 * 功能:
 * - AI 助手配置 (模型/温度/token/回退等)
 * - AI 对话 (SSE 流式，支持工具调用事件展示)
 * - 工具列表 (按分类分组、搜索)
 * - 技能管理 (搜索、启用/禁用、重载、详情查看)
 * - Telegram Bot 配置
 */
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { api, apiFetch } from '@/api'
import { configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { PasswordInput } from '@/components/common'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

defineOptions({ name: 'AiLabView' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || ''

const activeTab = ref('chat')
const configLoading = ref(false)
const saveLoading = ref(false)

// --- AI 介入测试 ---
const fallbackFilename = ref('')
const fallbackCurrentTitle = ref('')
const fallbackCurrentEpisode = ref<number | null>(null)
const fallbackLoading = ref(false)
const fallbackResult = ref<any>(null)

const fallbackExamples = [
  '[LoliHouse] Spy x Family - 13 [1080p].mkv',
  '[mirufans] 小鲨鱼去郊游剧场版 都市的朋友 [1080p].mkv',
  '[SubGroup] 葬送的芙莉蓮 - 12 [1080p].mkv',
  '[ANi] 無職轉生～到了異世界就拿出真本事～II - 05 [1080p][Bilibili].mkv',
  '[VCB-Studio] 鬼滅の刃 / Kimetsu no Yaiba [01][1080p][x265 10bit FLAC].mkv',
]

// --- 认证头 ---
function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

// --- Markdown 渲染 ---
function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text) as string
  } catch {
    return text
  }
}

// 助手配置
const assistantConfig = reactive({
  base_url: '',
  api_key: '',
  model: '',
  provider: 'ollama',
  temperature: 0.7,
  max_tokens: 64,
  max_iterations: 10,
  ai_fallback_enabled: false,
  use_tools: true,
})

// Telegram Bot 配置
const telegramConfig = reactive({
  enabled: false,
  allowedChats: '',
})

// --- 工具 ---
const tools = ref<any[]>([])
const toolsLoading = ref(false)
const toolSearchQuery = ref('')

// --- 技能 ---
const skills = ref<any[]>([])
const skillsLoading = ref(false)
const skillSearchQuery = ref('')
const expandedSkillId = ref<string | null>(null)
const skillDetail = ref<any>(null)
const skillDetailLoading = ref(false)

// --- 对话 ---
interface ToolCallEvent {
  type: string
  tool_name?: string
  arguments?: any
  result?: any
  success?: boolean
  message?: string
  content?: string
  skill_id?: string
  skill_name?: string
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  loading?: boolean
  events?: ToolCallEvent[]
  isStreaming?: boolean
}

const chatMessages = ref<ChatMessage[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const PROVIDER_OPTIONS = [
  { title: 'Ollama (本地)', value: 'ollama' },
  { title: 'OpenAI / 兼容接口', value: 'openai' },
]

// --- 配置 ---
async function fetchConfig() {
  configLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/config')
    if (data) {
      Object.assign(assistantConfig, data)
    }
  } catch {
    // 配置加载失败不阻塞
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  saveLoading.value = true
  try {
    await api.post('/api/assistant/config', assistantConfig)
    success('AI 配置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function saveUseTools() {
  try {
    await api.post('/api/assistant/config', { use_tools: assistantConfig.use_tools })
    success(assistantConfig.use_tools ? '已启用工具模式' : '已切换为纯对话模式')
  } catch {
    // 非关键
  }
}

// --- Telegram Bot ---
async function fetchTelegramConfig() {
  try {
    const data = await configApi.getConfig()
    if (data) {
      telegramConfig.enabled = data.telegram_bot_enabled || false
      const chats = data.telegram_allowed_chats || []
      telegramConfig.allowedChats = Array.isArray(chats) ? chats.join(',') : ''
    }
  } catch {
    // 非关键
  }
}

async function saveTelegramConfig() {
  try {
    const allowedChats = telegramConfig.allowedChats
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)

    await configApi.saveConfig({
      telegram_bot_enabled: telegramConfig.enabled,
      telegram_allowed_chats: allowedChats,
    })
    success('Telegram Bot 配置已保存，重启服务后生效')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  }
}

// --- 工具列表 ---
async function fetchTools() {
  toolsLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/tools')
    tools.value = Array.isArray(data) ? data : []
  } catch {
    tools.value = []
  } finally {
    toolsLoading.value = false
  }
}

const groupedTools = computed(() => {
  const groups: Record<string, any[]> = {}
  const query = toolSearchQuery.value.toLowerCase().trim()
  for (const tool of tools.value) {
    const cat = tool.category || 'general'
    if (query) {
      const matchName = tool.name.toLowerCase().includes(query)
      const matchDesc = (tool.description || '').toLowerCase().includes(query)
      const matchCat = cat.toLowerCase().includes(query)
      if (!matchName && !matchDesc && !matchCat) continue
    }
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(tool)
  }
  return groups
})

// --- 技能 ---
async function fetchSkills() {
  skillsLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/skills')
    skills.value = Array.isArray(data) ? data : []
  } catch {
    skills.value = []
  } finally {
    skillsLoading.value = false
  }
}

async function fetchSkillDetail(skillId: string) {
  skillDetailLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/skills/' + skillId)
    skillDetail.value = data
  } catch {
    skillDetail.value = null
  } finally {
    skillDetailLoading.value = false
  }
}

async function toggleSkillExpand(skillId: string) {
  if (expandedSkillId.value === skillId) {
    expandedSkillId.value = null
    skillDetail.value = null
  } else {
    expandedSkillId.value = skillId
    skillDetail.value = null
    await fetchSkillDetail(skillId)
  }
}

async function toggleSkillEnabled(skill: any) {
  const newEnabled = !skill.enabled
  skill.enabled = newEnabled // 乐观更新
  try {
    await api.put('/api/assistant/skills/' + skill.id + '/enabled', { enabled: newEnabled })
    success('技能已' + (newEnabled ? '启用' : '禁用'))
  } catch (e: any) {
    skill.enabled = !newEnabled // 回滚
    showError(e?.message || '操作失败')
  }
}

async function reloadSkills() {
  skillsLoading.value = true
  try {
    const data: any = await apiFetch('/api/assistant/skills/reload', { method: 'POST' })
    success(data?.message || '重载完成')
    await fetchSkills()
  } catch (e: any) {
    showError(e?.message || '重载失败')
  } finally {
    skillsLoading.value = false
  }
}

const filteredSkills = computed(() => {
  const query = skillSearchQuery.value.toLowerCase().trim()
  if (!query) return skills.value
  return skills.value.filter(s => {
    return (s.name || '').toLowerCase().includes(query) ||
           (s.description || '').toLowerCase().includes(query) ||
           (s.id || '').toLowerCase().includes(query) ||
           (s.triggers || []).some((t: string) => t.toLowerCase().includes(query))
  })
})

// --- 对话 (SSE 流式) ---
async function sendMessage() {
  if (!chatInput.value.trim() || chatLoading.value) return

  const userMessage = chatInput.value.trim()
  chatInput.value = ''

  chatMessages.value.push({ role: 'user', content: userMessage })
  chatLoading.value = true

  const msgIndex = chatMessages.value.length
  chatMessages.value.push({
    role: 'assistant',
    content: '',
    loading: true,
    events: [],
    isStreaming: true,
  })

  await nextTick()
  scrollToBottom()

  try {
    const res = await fetch(`${API_BASE}/api/assistant/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        messages: chatMessages.value
          .filter(m => !m.loading && !m.isStreaming)
          .map(m => ({ role: m.role, content: m.content })),
        stream: true,
        use_tools: assistantConfig.use_tools,
      }),
    })

    if (!res.ok) {
      let detail = `请求失败 (${res.status})`
      try {
        const errorData = await res.json()
        detail = errorData.detail || detail
      } catch { /* ignore */ }
      chatMessages.value[msgIndex].content = detail
      chatMessages.value[msgIndex].loading = false
      chatMessages.value[msgIndex].isStreaming = false
      chatLoading.value = false
      return
    }

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (reader) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            handleStreamEvent(msgIndex, event)
          } catch {
            // 忽略解析错误
          }
        }
      }

      await nextTick()
      scrollToBottom()
    }
  } catch {
    chatMessages.value[msgIndex].content = '网络错误，请稍后重试'
  } finally {
    chatMessages.value[msgIndex].loading = false
    chatMessages.value[msgIndex].isStreaming = false
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleStreamEvent(msgIndex: number, event: any) {
  const msg = chatMessages.value[msgIndex]
  if (!msg) return

  switch (event.type) {
    case 'skill':
      msg.events!.push({
        type: 'skill',
        message: event.message,
        skill_name: event.skill_name,
      })
      break

    case 'thinking':
      if (event.content) {
        msg.events!.push({
          type: 'thinking',
          content: event.content,
        })
      }
      break

    case 'tool_call':
      msg.events!.push({
        type: 'tool_call',
        tool_name: event.tool_name,
        arguments: event.arguments,
        message: event.message,
      })
      break

    case 'tool_result': {
      const lastToolEvent = [...msg.events!]
        .reverse()
        .find((e: any) => e.type === 'tool_call' && e.tool_name === event.tool_name)
      if (lastToolEvent) {
        lastToolEvent.result = event.result
        lastToolEvent.success = event.success
      }
      msg.events!.push({
        type: 'tool_result',
        tool_name: event.tool_name,
        success: event.success,
        message: event.message,
      })
      break
    }

    case 'response':
      msg.content = event.content || ''
      break

    case 'error':
      msg.content = `错误: ${event.message}`
      break
  }
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

async function clearChat() {
  const ok = await confirm({
    title: '确认清空',
    content: '确定要清空所有对话记录吗？',
    confirmText: '确定清空',
    cancelText: '取消',
    confirmColor: 'error',
  })
  if (ok) {
    chatMessages.value = []
  }
}

function getEventColor(event: ToolCallEvent): string {
  if (event.type === 'tool_result') {
    return event.success ? 'success' : 'error'
  }
  if (event.type === 'error') return 'error'
  if (event.type === 'skill') return 'info'
  return 'default'
}

function getEventLabel(event: ToolCallEvent): string {
  switch (event.type) {
    case 'tool_call': return '调用工具'
    case 'tool_result': return '执行结果'
    case 'skill': return '触发技能'
    case 'thinking': return '思考'
    default: return event.type
  }
}

// --- AI 介入测试 ---
async function runFallbackTest() {
  if (!fallbackFilename.value.trim() || fallbackLoading.value) return
  fallbackLoading.value = true
  fallbackResult.value = null
  try {
    const body: any = { filename: fallbackFilename.value.trim() }
    if (fallbackCurrentTitle.value.trim()) body.current_title = fallbackCurrentTitle.value.trim()
    if (fallbackCurrentEpisode.value) body.current_episode = fallbackCurrentEpisode.value
    const data = await apiFetch<any>('/api/ai/fallback-test', { method: 'POST', body })
    fallbackResult.value = data
    if (data.status === 'success') {
      success('AI 推断成功')
    }
  } catch (e: any) {
    fallbackResult.value = { status: 'error', message: e?.message || '请求失败' }
  } finally {
    fallbackLoading.value = false
  }
}

function getConfidenceColor(conf: number): string {
  if (conf >= 0.8) return 'success'
  if (conf >= 0.5) return 'warning'
  return 'error'
}

function getMediaTypeIcon(type?: string): string {
  if (type === 'movie') return 'mdi-movie'
  if (type === 'tv') return 'mdi-television'
  return 'mdi-help-circle-outline'
}

function getMediaTypeLabel(type?: string): string {
  if (type === 'movie') return '电影 / 剧场版'
  if (type === 'tv') return '剧集 / 番剧'
  return '未知'
}

onMounted(() => {
  fetchConfig()
  fetchTelegramConfig()
  fetchSkills()
  fetchTools()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between">
      <div>
        <h1 class="page-title text-h5 font-weight-bold">AI 实验室</h1>
        <div class="page-subtitle text-body-2 text-medium-emphasis mt-1">AI 语义解析与智能助手</div>
      </div>
      <div class="d-flex align-center ga-3">
        <v-switch
          v-model="assistantConfig.use_tools"
          density="compact"
          hide-details
          color="primary"
          :label="assistantConfig.use_tools ? '工具模式' : '纯对话'"
          @update:model-value="saveUseTools"
        />
        <v-chip color="primary" variant="tonal" size="small">Beta</v-chip>
      </div>
    </div>

    <div class="sticky-tabs">
      <v-tabs v-model="activeTab" color="primary">
        <v-tab value="chat">
          <v-icon start size="18">mdi-chat-outline</v-icon>
          AI 对话
        </v-tab>
        <v-tab value="tools">
          <v-icon start size="18">mdi-toolbox-outline</v-icon>
          工具列表
        </v-tab>
        <v-tab value="skills">
          <v-icon start size="18">mdi-lightning-bolt-outline</v-icon>
          技能管理
        </v-tab>
        <v-tab value="config">
          <v-icon start size="18">mdi-cog-outline</v-icon>
          助手配置
        </v-tab>
        <v-tab value="fallback-test">
          <v-icon start size="18">mdi-robot-excited-outline</v-icon>
          AI 介入测试
        </v-tab>
        <v-tab value="telegram">
          <v-icon start size="18">mdi-send-circle-outline</v-icon>
          Telegram Bot
        </v-tab>
      </v-tabs>
    </div>

    <v-window v-model="activeTab">
      <!-- AI 对话 -->
      <v-window-item value="chat">
        <v-card class="glass-card" style="height: calc(100vh - 280px); display: flex; flex-direction: column;">
          <!-- 对话消息区 -->
          <div ref="chatContainer" class="flex-grow-1 overflow-y-auto pa-4" style="min-height: 0">
            <div v-if="chatMessages.length === 0" class="empty-state">
              <v-icon size="64" color="primary" class="mb-4">mdi-robot-outline</v-icon>
              <div class="text-h6 font-weight-medium">AI 助手</div>
              <div class="text-body-2 text-medium-emphasis mt-2">输入消息开始对话，支持工具调用</div>
            </div>

            <div v-for="(msg, index) in chatMessages" :key="index" class="mb-4">
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="d-flex justify-end">
                <div class="user-bubble">{{ msg.content }}</div>
              </div>

              <!-- 助手消息 -->
              <div v-else class="d-flex justify-start">
                <div class="assistant-bubble">
                  <!-- 工具调用事件 -->
                  <div v-if="msg.events?.length" class="mb-2">
                    <div
                      v-for="(event, ei) in msg.events"
                      :key="ei"
                      class="event-item mb-1"
                      :class="event.type"
                    >
                      <div class="d-flex align-center ga-2">
                        <span class="text-caption font-weight-medium">{{ getEventLabel(event) }}</span>
                        <span v-if="event.tool_name" class="text-caption font-mono text-primary">{{ event.tool_name }}</span>
                        <span v-if="event.skill_name" class="text-caption font-mono text-primary">{{ event.skill_name }}</span>
                        <v-chip
                          v-if="event.type === 'tool_result'"
                          :color="getEventColor(event)"
                          size="x-small"
                          variant="flat"
                        >
                          {{ event.success ? '成功' : '失败' }}
                        </v-chip>
                      </div>
                      <div v-if="event.message" class="text-caption text-medium-emphasis mt-1">{{ event.message }}</div>
                      <details v-if="event.arguments || event.result" class="mt-1">
                        <summary class="text-caption text-primary cursor-pointer">详情</summary>
                        <pre class="text-caption pa-2 rounded mt-1" style="background: rgba(0,0,0,0.06); overflow-x: auto; max-height: 200px;">{{ JSON.stringify(event.arguments || event.result, null, 2) }}</pre>
                      </details>
                    </div>
                  </div>

                  <!-- 消息内容 -->
                  <v-progress-circular v-if="msg.loading" indeterminate size="20" color="primary" class="mr-2" />
                  <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                </div>
              </div>
            </div>
          </div>

          <v-divider />

          <!-- 输入区 -->
          <div class="pa-3 d-flex ga-2 align-center">
            <v-text-field
              v-model="chatInput"
              placeholder="输入消息..."
              density="comfortable"
              variant="outlined"
              hide-details
              :disabled="chatLoading"
              @keydown.enter="sendMessage"
              class="flex-grow-1"
            />
            <v-btn
              variant="tonal" color="primary"
              icon="mdi-send"
              :loading="chatLoading"
              :disabled="!chatInput.trim()"
              @click="sendMessage"
            />
            <v-btn
              variant="tonal"
              color="warning"
              size="small"
              prepend-icon="mdi-delete-outline"
              :disabled="chatMessages.length === 0"
              @click="clearChat"
            >清空</v-btn>
          </div>
        </v-card>
      </v-window-item>

      <!-- 工具列表 -->
      <v-window-item value="tools">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-toolbox-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">可用工具 ({{ tools.length }})</span>
          </v-card-title>
          <div class="pa-4 pb-2 d-flex justify-end">
            <v-text-field
              v-model="toolSearchQuery"
              placeholder="搜索工具名称或描述..."
              density="compact"
              variant="outlined"
              hide-details
              prepend-inner-icon="mdi-magnify"
              class="tool-search-field"
            />
          </div>
          <v-divider />

          <v-card-text class="pa-4">
            <v-progress-linear v-if="toolsLoading" indeterminate color="primary" class="mb-3" />

            <template v-else-if="Object.keys(groupedTools).length > 0">
              <div v-for="(toolList, category) in groupedTools" :key="category" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold mb-2">
                  {{ category }} ({{ toolList.length }})
                </div>
                <v-card v-for="tool in toolList" :key="tool.name" class="glass-card tool-card mb-2" variant="flat">
                  <div class="d-flex align-center justify-space-between mb-1">
                    <span class="font-mono font-weight-bold text-body-2">{{ tool.name }}</span>
                    <v-chip size="x-small" variant="tonal" :color="tool.parameters?.length ? 'primary' : 'default'">
                      {{ tool.parameters?.length || 0 }} 参数
                    </v-chip>
                  </div>
                  <div class="text-body-2 text-medium-emphasis">{{ tool.description }}</div>
                  <div v-if="tool.parameters?.length" class="mt-2">
                    <div v-for="p in tool.parameters" :key="p.name" class="d-flex align-center ga-2 text-caption mb-1">
                      <v-chip size="x-small" :color="p.required ? 'primary' : 'default'" variant="flat">
                        {{ p.name }}<span v-if="p.required">*</span>
                      </v-chip>
                      <span class="font-mono text-primary tool-param-type">{{ p.type }}</span>
                      <span class="text-medium-emphasis">{{ p.description }}</span>
                    </div>
                  </div>
                </v-card>
              </div>
            </template>

            <div v-else class="empty-state">
              <v-icon size="48" color="primary" class="mb-3">mdi-toolbox-outline</v-icon>
              <div class="text-body-1">{{ toolSearchQuery ? '未找到匹配的工具' : '暂无工具' }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- 技能管理 -->
      <v-window-item value="skills">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-lightning-bolt-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">可用技能 ({{ skills.length }})</span>
          </v-card-title>
          <div class="pa-4 pb-2 d-flex align-center justify-end ga-2">
            <v-text-field
              v-model="skillSearchQuery"
              placeholder="搜索技能..."
              density="compact"
              variant="outlined"
              hide-details
              prepend-inner-icon="mdi-magnify"
              class="skill-search-field"
            />
            <v-btn
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-refresh"
              :loading="skillsLoading"
              @click="reloadSkills"
            >重载</v-btn>
          </div>
          <v-divider />

          <v-card-text class="pa-4">
            <v-progress-linear v-if="skillsLoading" indeterminate color="primary" class="mb-3" />

            <template v-else-if="filteredSkills.length > 0">
              <v-card v-for="skill in filteredSkills" :key="skill.id" class="glass-card skill-card mb-3">
                <!-- 标题行 -->
                <div class="manage-card__header">
                  <div class="d-flex align-center ga-3 manage-card__title">
                    <v-icon color="primary">mdi-lightning-bolt-outline</v-icon>
                    <div class="d-flex flex-column">
                      <span class="text-subtitle-2 font-weight-bold" :class="{ 'text-medium-emphasis': !skill.enabled }">
                        {{ skill.name || skill.id }}
                      </span>
                      <span v-if="skill.description" class="text-caption text-medium-emphasis manage-card__desc">{{ skill.description }}</span>
                    </div>
                  </div>
                  <div class="d-flex align-center ga-2 manage-card__badge">
                    <v-chip v-if="skill.version" size="x-small" variant="tonal">v{{ skill.version }}</v-chip>
                    <v-chip v-if="skill.tools_needed?.length" size="x-small" variant="tonal" color="primary">
                      {{ skill.tools_needed.length }} 工具
                    </v-chip>
                    <v-switch
                      :model-value="skill.enabled"
                      density="compact"
                      hide-details
                      color="primary"
                      @update:model-value="toggleSkillEnabled(skill)"
                    />
                  </div>
                </div>

                <!-- 标签区 -->
                <div v-if="skill.triggers?.length || skill.tools_needed?.length" class="manage-card__body">
                  <div v-if="skill.triggers?.length" class="manage-card__tags">
                    <span class="text-caption text-medium-emphasis">触发词：</span>
                    <v-chip v-for="t in skill.triggers" :key="t" size="x-small" variant="tonal" color="info">{{ t }}</v-chip>
                  </div>
                  <div v-if="skill.tools_needed?.length" class="manage-card__tags">
                    <span class="text-caption text-medium-emphasis">关联工具：</span>
                    <v-chip v-for="t in skill.tools_needed" :key="t" size="x-small" variant="tonal" color="success">{{ t }}</v-chip>
                  </div>
                </div>

                <!-- 操作区 -->
                <v-card-actions class="manage-card__actions">
                  <v-btn
                    size="small"
                    variant="text"
                    color="primary"
                    :prepend-icon="expandedSkillId === skill.id ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    @click="toggleSkillExpand(skill.id)"
                  >
                    {{ expandedSkillId === skill.id ? '收起详情' : '查看详情' }}
                  </v-btn>
                </v-card-actions>

                <!-- 展开详情 -->
                <v-expand-transition>
                  <div v-show="expandedSkillId === skill.id">
                    <v-divider />
                    <v-card-text class="pa-4">
                      <div v-if="skillDetailLoading" class="text-center pa-4">
                        <v-progress-circular indeterminate size="24" color="primary" />
                      </div>
                      <div v-else-if="skillDetail && skillDetail.id === skill.id">
                        <div class="text-caption text-medium-emphasis mb-2">
                          路径：<code>{{ skillDetail.path }}</code>
                        </div>
                        <v-divider class="mb-3" />
                        <div class="markdown-body skill-markdown" v-html="renderMarkdown(skillDetail.content || '')"></div>
                      </div>
                      <div v-else class="text-caption text-medium-emphasis">加载失败</div>
                    </v-card-text>
                  </div>
                </v-expand-transition>
              </v-card>
            </template>

            <div v-else class="empty-state">
              <v-icon size="48" color="primary" class="mb-3">mdi-lightning-bolt-outline</v-icon>
              <div class="text-body-1">{{ skillSearchQuery ? '未找到匹配的技能' : '暂无技能' }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- 助手配置 -->
      <v-window-item value="config">
        <div class="d-flex justify-end mb-4">
          <v-btn variant="tonal" color="primary" :loading="saveLoading" prepend-icon="mdi-content-save-outline" @click="saveConfig">
            保存全部修改
          </v-btn>
        </div>

        <!-- AI 模型配置 -->
        <v-card class="glass-card mb-4">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-brain</v-icon>
            <span class="text-subtitle-1 font-weight-bold">AI 模型配置</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 font-weight-medium mb-2">模型提供商</div>
            <v-radio-group v-model="assistantConfig.provider" inline density="compact" class="mb-4" hide-details>
              <v-radio value="ollama" label="Ollama (本地)" />
              <v-radio value="openai" label="OpenAI / 兼容接口" />
            </v-radio-group>

            <v-text-field v-model="assistantConfig.base_url" label="API 地址" density="compact" class="mb-1" placeholder="如 http://localhost:11434" hide-details />
            <div class="text-caption text-medium-emphasis mb-3">Ollama 默认 http://localhost:11434，OpenAI 兼容接口填完整 v1 地址</div>

            <PasswordInput v-if="assistantConfig.provider === 'openai'" v-model="assistantConfig.api_key" label="API Key" density="compact" class="mb-3" hide-details />

            <v-text-field v-model="assistantConfig.model" label="模型名称" density="compact" hide-details placeholder="如 qwen2.5:7b 或 gpt-4o" />
          </v-card-text>
        </v-card>

        <!-- 推理参数 -->
        <v-card class="glass-card mb-4">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-tune-vertical</v-icon>
            <span class="text-subtitle-1 font-weight-bold">推理参数</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="d-flex align-center ga-3 mb-4">
              <span class="text-body-2 text-medium-emphasis" style="min-width: 80px">温度</span>
              <v-slider v-model="assistantConfig.temperature" :min="0" :max="2" :step="0.1" hide-details thumb-label />
              <v-chip size="small" variant="tonal">{{ assistantConfig.temperature }}</v-chip>
            </div>

            <v-text-field v-model.number="assistantConfig.max_tokens" label="最大 Token 数 (K)" type="number" density="compact" class="mb-3" hide-details />
            <v-text-field v-model.number="assistantConfig.max_iterations" label="最大迭代次数" type="number" density="compact" class="mb-4" hide-details />

            <v-divider class="mb-4" />

            <div class="d-flex align-center ga-3 mb-4">
              <v-switch v-model="assistantConfig.use_tools" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">启用工具调用</div>
                <div class="text-caption text-medium-emphasis">允许 AI 调用系统工具执行实际操作</div>
              </div>
            </div>

            <div class="d-flex align-center ga-3">
              <v-switch v-model="assistantConfig.ai_fallback_enabled" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">AI 智能介入</div>
                <div class="text-caption text-medium-emphasis">识别失败时，让 AI 猜测标题并重新搜索</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- AI 介入测试 -->
      <v-window-item value="fallback-test">
        <v-card class="glass-card mb-4">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-robot-excited-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">AI 智能介入测试</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 text-medium-emphasis mb-4">
              输入文件名，让 AI 推断真实标题。此功能模拟识别失败后 AI 介入猜测标题的行为，仅测试 AI 推断能力，不涉及 TMDB/Bangumi 搜索。
            </div>

            <!-- 输入区 -->
            <v-text-field
              v-model="fallbackFilename"
              placeholder="输入文件名，如 [LoliHouse] Spy x Family - 13 [1080p].mkv"
              density="comfortable"
              variant="outlined"
              hide-details
              class="mb-3"
              :loading="fallbackLoading"
              :disabled="fallbackLoading"
              prepend-inner-icon="mdi-file-search-outline"
              @keydown.enter="runFallbackTest"
            />

            <!-- 高级参数 -->
            <v-expansion-panels class="mb-3">
              <v-expansion-panel title="高级参数（可选）">
                <v-expansion-panel-text>
                  <v-text-field
                    v-model="fallbackCurrentTitle"
                    placeholder="当前解析出的标题（可选，辅助 AI 判断）"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-3"
                  />
                  <v-text-field
                    v-model.number="fallbackCurrentEpisode"
                    placeholder="当前解析出的集数（可选）"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- 示例 -->
            <div class="d-flex align-center flex-wrap ga-2 mb-4">
              <span class="text-caption text-medium-emphasis">示例：</span>
              <v-chip
                v-for="(ex, i) in fallbackExamples"
                :key="i"
                size="x-small"
                variant="tonal"
                color="primary"
                @click="fallbackFilename = ex"
                style="cursor: pointer"
              >
                {{ ex.length > 30 ? ex.slice(0, 30) + '...' : ex }}
              </v-chip>
            </div>

            <!-- 测试按钮 -->
            <div class="d-flex ga-2 mb-4">
              <v-btn
                variant="tonal" color="primary"
                prepend-icon="mdi-robot"
                :loading="fallbackLoading"
                :disabled="!fallbackFilename.trim()"
                @click="runFallbackTest"
              >
                发送给 AI
              </v-btn>
              <v-btn
                variant="tonal"
                prepend-icon="mdi-eraser"
                :disabled="fallbackLoading"
                @click="fallbackFilename = ''; fallbackCurrentTitle = ''; fallbackCurrentEpisode = null; fallbackResult = null"
              >
                清空
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <!-- 结果展示 -->
        <v-progress-linear v-if="fallbackLoading" indeterminate color="primary" class="mb-4" />

        <v-card v-if="fallbackResult" class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
            <div class="d-flex align-center ga-2">
              <v-icon
                :color="fallbackResult.status === 'success' ? 'success' : 'error'"
                size="24"
              >
                {{ fallbackResult.status === 'success' ? 'mdi-check-circle' : 'mdi-alert-circle' }}
              </v-icon>
              <span class="text-subtitle-1 font-weight-bold">
                {{ fallbackResult.status === 'success' ? 'AI 推断结果' : '测试失败' }}
              </span>
            </div>
            <v-chip v-if="fallbackResult.elapsed != null" size="small" variant="tonal" color="info">
              <v-icon start size="14">mdi-timer-outline</v-icon>
              {{ fallbackResult.elapsed }}s
            </v-chip>
          </v-card-title>
          <v-divider />

          <!-- 成功结果 -->
          <v-card-text v-if="fallbackResult.status === 'success'" class="pa-4">
            <!-- 核心信息卡片 -->
            <v-row class="mb-4">
              <v-col cols="12" sm="6" md="4">
                <div class="info-block">
                  <div class="info-block__label">🎯 真实标题</div>
                  <div class="info-block__value">{{ fallbackResult.result?.real_title || '-' }}</div>
                </div>
              </v-col>
              <v-col cols="12" sm="6" md="4">
                <div class="info-block">
                  <div class="info-block__label">📝 原名</div>
                  <div class="info-block__value">{{ fallbackResult.result?.original_name || '-' }}</div>
                </div>
              </v-col>
              <v-col cols="12" sm="6" md="4">
                <div class="info-block">
                  <div class="info-block__label">🇨🇳 中文名</div>
                  <div class="info-block__value">{{ fallbackResult.result?.chinese_name || '-' }}</div>
                </div>
              </v-col>
            </v-row>

            <!-- 媒体类型 & 置信度 & 季集信息 -->
            <v-row class="mb-4">
              <v-col cols="6" sm="3">
                <div class="d-flex align-center ga-2">
                  <v-icon size="20" color="primary">
                    {{ getMediaTypeIcon(fallbackResult.result?.media_type) }}
                  </v-icon>
                  <div>
                    <div class="text-caption text-medium-emphasis">媒体类型</div>
                    <div class="text-body-2 font-weight-medium">
                      {{ getMediaTypeLabel(fallbackResult.result?.media_type) }}
                    </div>
                  </div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="d-flex align-center ga-2">
                  <v-icon size="20" color="primary">mdi-numeric</v-icon>
                  <div>
                    <div class="text-caption text-medium-emphasis">季号</div>
                    <div class="text-body-2 font-weight-medium">
                      {{ fallbackResult.result?.season != null ? 'S' + fallbackResult.result.season : '-' }}
                    </div>
                  </div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="d-flex align-center ga-2">
                  <v-icon size="20" color="primary">mdi-play-box-outline</v-icon>
                  <div>
                    <div class="text-caption text-medium-emphasis">集数</div>
                    <div class="text-body-2 font-weight-medium">
                      {{ fallbackResult.result?.episode != null ? 'E' + fallbackResult.result.episode : '-' }}
                    </div>
                  </div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="d-flex align-center ga-2">
                  <v-icon size="20" :color="getConfidenceColor(fallbackResult.result?.confidence || 0)">
                    mdi-gauge
                  </v-icon>
                  <div>
                    <div class="text-caption text-medium-emphasis">置信度</div>
                    <v-chip
                      size="x-small"
                      :color="getConfidenceColor(fallbackResult.result?.confidence || 0)"
                      variant="tonal"
                    >
                      {{ ((fallbackResult.result?.confidence || 0) * 100).toFixed(0) }}%
                    </v-chip>
                  </div>
                </div>
              </v-col>
            </v-row>

            <!-- 备选标题 -->
            <div v-if="fallbackResult.result?.alternative_titles?.length" class="mb-4">
              <div class="text-caption text-medium-emphasis mb-2">📋 备选标题</div>
              <div class="d-flex flex-wrap ga-2">
                <v-chip
                  v-for="(alt, i) in fallbackResult.result.alternative_titles"
                  :key="i"
                  size="small"
                  variant="tonal"
                  color="info"
                >
                  {{ alt }}
                </v-chip>
              </div>
            </div>

            <!-- 搜索变体预览 -->
            <div class="mb-4">
              <div class="text-caption text-medium-emphasis mb-2">🔍 将用于搜索的标题顺序</div>
              <div class="d-flex flex-column ga-1">
                <div
                  v-for="(title, i) in [
                    fallbackResult.result?.original_name,
                    fallbackResult.result?.chinese_name,
                    fallbackResult.result?.real_title,
                    ...(fallbackResult.result?.alternative_titles || [])
                  ].filter(Boolean).filter((v, idx, arr) => arr.indexOf(v) === idx)"
                  :key="i"
                  class="d-flex align-center ga-2 pa-2 rounded"
                  style="background: rgba(var(--v-theme-surface-variant), 0.15)"
                >
                  <v-chip size="x-small" variant="flat" color="primary">{{ i + 1 }}</v-chip>
                  <span class="text-body-2 font-mono">{{ title }}</span>
                </div>
              </div>
            </div>

            <!-- 原始 JSON -->
            <details>
              <summary class="text-caption text-primary cursor-pointer mb-2">查看原始 JSON 响应</summary>
              <pre class="pa-3 rounded text-caption" style="background: rgba(0,0,0,0.06); overflow-x: auto; max-height: 300px;">{{ JSON.stringify(fallbackResult.result, null, 2) }}</pre>
            </details>
          </v-card-text>

          <!-- 错误信息 -->
          <v-card-text v-else class="pa-4">
            <v-alert type="error" variant="tonal" class="mb-3">
              {{ fallbackResult.message || '未知错误' }}
            </v-alert>

            <!-- 调试信息 -->
            <div v-if="fallbackResult.debug" class="mt-3">
              <div class="text-caption text-medium-emphasis mb-2">🔧 调试信息</div>
              <div class="d-flex flex-column ga-2">
                <div class="d-flex align-center ga-2">
                  <span class="text-body-2 text-medium-emphasis" style="min-width: 120px">AI 可用性</span>
                  <v-chip size="x-small" :color="fallbackResult.debug.is_available ? 'success' : 'error'" variant="tonal">
                    {{ fallbackResult.debug.is_available ? '✅ 可用' : '❌ 不可用' }}
                  </v-chip>
                </div>
                <div class="d-flex align-center ga-2">
                  <span class="text-body-2 text-medium-emphasis" style="min-width: 120px">介入开关</span>
                  <v-chip size="x-small" :color="fallbackResult.debug.is_fallback_enabled ? 'success' : 'default'" variant="tonal">
                    {{ fallbackResult.debug.is_fallback_enabled ? '已开启' : '未开启' }}
                  </v-chip>
                </div>
                <div class="d-flex align-center ga-2">
                  <span class="text-body-2 text-medium-emphasis" style="min-width: 120px">模型</span>
                  <code class="text-caption">{{ fallbackResult.debug.model || '-' }}</code>
                </div>
                <div class="d-flex align-center ga-2">
                  <span class="text-body-2 text-medium-emphasis" style="min-width: 120px">API 地址</span>
                  <code class="text-caption">{{ fallbackResult.debug.base_url || '-' }}</code>
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>

        <!-- 空状态 -->
        <v-card v-if="!fallbackResult && !fallbackLoading" class="glass-card">
          <v-card-text class="pa-8 text-center">
            <v-icon size="48" color="primary" class="mb-3">mdi-robot-outline</v-icon>
            <div class="text-body-1 text-medium-emphasis">输入文件名后点击「发送给 AI」开始测试</div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Telegram Bot -->
      <v-window-item value="telegram">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-send-circle-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">Telegram Bot</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="d-flex align-center ga-3 mb-4">
              <v-switch v-model="telegramConfig.enabled" density="compact" hide-details color="primary" />
              <div>
                <div class="text-body-2 font-weight-medium">启用 Bot 对话</div>
                <div class="text-caption text-medium-emphasis">通过 Telegram 与智能助手对话，远程控制番剧管理</div>
              </div>
            </div>

            <v-textarea
              v-model="telegramConfig.allowedChats"
              label="允许的 Chat ID"
              placeholder="输入 Chat ID，多个用逗号分隔，留空则不限制"
              density="compact"
              rows="3"
              hide-details
              class="mb-3"
              :disabled="!telegramConfig.enabled"
            />
            <div class="text-caption text-medium-emphasis">
              提示：配置保存后需重启服务才能生效。需要先在「系统设置 → 基础配置」中配置 Bot Token。
            </div>
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-4">
            <v-spacer />
            <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="saveTelegramConfig">保存配置</v-btn>
          </v-card-actions>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>


