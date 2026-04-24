<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NDivider, NGrid, NGi, 
  NTag, useMessage, NScrollbar, NAlert, NText, NSwitch, NSlider,
  NCollapse, NCollapseItem, NForm, NFormItem, NInputNumber, NEmpty,
  NTabs, NTabPane, NList, NListItem, NThing, NBadge, NAvatar,
  NSkeleton, NSpin, NRadioGroup, NRadioButton, NCode, NTooltip
} from 'naive-ui'
import {
  SmartToyOutlined as AiIcon,
  SettingsOutlined as ConfigIcon,
  SaveOutlined as SaveIcon,
  ExtensionOutlined as SkillIcon,
  SendOutlined as SendIcon,
  BuildOutlined as ToolIcon,
  PlayArrowOutlined as PlayIcon,
  CheckCircleOutlined as SuccessIcon,
  ErrorOutlined as ErrorIcon,
  LightbulbOutlined as ThinkingIcon
} from '@vicons/material'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text: string) => {
  if (!text) return ''
  return marked.parse(text) as string
}

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const activeTab = ref('chat')

const configLoading = ref(false)
const saveLoading = ref(false)

const assistantConfig = ref({
  base_url: '',
  api_key: '',
  model: '',
  provider: 'openai',
  temperature: 0.7,
  max_tokens: 64,
  max_iterations: 10,
  ai_fallback_enabled: false
})

const telegramBotConfig = ref({
  enabled: false,
  allowedChats: ''
})

const skills = ref<any[]>([])
const tools = ref<any[]>([])
const toolsLoading = ref(false)
const skillsLoading = ref(false)

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
  role: string
  content: string
  loading?: boolean
  events?: ToolCallEvent[]
  isStreaming?: boolean
}

const chatMessages = ref<ChatMessage[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const useTools = ref(true)

const getAuthHeaders = () => {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

const fetchConfig = async () => {
  configLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/assistant/config`, {
      headers: getAuthHeaders()
    })
    if (res.ok) {
      const data = await res.json()
      assistantConfig.value = { ...assistantConfig.value, ...data }
    }
  } catch (e) {
    message.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

const saveConfig = async () => {
  saveLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/assistant/config`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(assistantConfig.value)
    })
    if (res.ok) {
      message.success('配置已保存')
    } else {
      message.error('保存失败')
    }
  } catch (e) {
    message.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

const fetchTelegramBotConfig = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/config`, { headers: getAuthHeaders() })
    if (res.ok) {
      const data = await res.json()
      telegramBotConfig.value.enabled = data.telegram_bot_enabled || false
      const chats = data.telegram_allowed_chats || []
      telegramBotConfig.value.allowedChats = Array.isArray(chats) ? chats.join(',') : ''
    }
  } catch (e) {
    console.error('获取 Telegram Bot 配置失败', e)
  }
}

const saveTelegramBotConfig = async () => {
  try {
    const allowedChats = telegramBotConfig.value.allowedChats
      .split(',')
      .map(s => s.trim())
      .filter(s => s)
      .map(s => isNaN(Number(s)) ? s : Number(s))
    
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        telegram_bot_enabled: telegramBotConfig.value.enabled,
        telegram_allowed_chats: allowedChats
      })
    })
    if (res.ok) {
      message.success('Telegram Bot 配置已保存，重启服务后生效')
    } else {
      message.error('保存失败')
    }
  } catch (e) {
    message.error('保存失败')
  }
}

const fetchSkills = async () => {
  skillsLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/assistant/skills`, {
      headers: getAuthHeaders()
    })
    if (res.ok) {
      skills.value = await res.json()
    }
  } catch (e) {
    console.error('加载技能失败', e)
  } finally {
    skillsLoading.value = false
  }
}

const fetchTools = async () => {
  toolsLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/assistant/tools`, {
      headers: getAuthHeaders()
    })
    if (res.ok) {
      tools.value = await res.json()
    }
  } catch (e) {
    console.error('加载工具失败', e)
  } finally {
    toolsLoading.value = false
  }
}

const sendMessage = async () => {
  if (!chatInput.value.trim() || chatLoading.value) return
  
  const userMessage = chatInput.value.trim()
  chatMessages.value.push({ role: 'user', content: userMessage })
  chatInput.value = ''
  chatLoading.value = true
  
  const msgIndex = chatMessages.value.length
  chatMessages.value.push({ role: 'assistant', content: '', loading: true, events: [], isStreaming: true })
  
  await nextTick()
  scrollToBottom()
  
  try {
    const res = await fetch(`${API_BASE}/api/assistant/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        messages: chatMessages.value.filter(m => !m.loading && !m.isStreaming).map(m => ({ role: m.role, content: m.content })),
        stream: true,
        use_tools: useTools.value
      })
    })
    
    if (!res.ok) {
      const errorData = await res.json()
      chatMessages.value[msgIndex].content = errorData.detail || '请求失败，请检查模型配置'
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
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
      
      await nextTick()
      scrollToBottom()
    }
    
  } catch (e) {
    chatMessages.value[msgIndex].content = '网络错误，请稍后重试'
  } finally {
    chatMessages.value[msgIndex].loading = false
    chatMessages.value[msgIndex].isStreaming = false
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const handleStreamEvent = (msgIndex: number, event: any) => {
  const msg = chatMessages.value[msgIndex]
  if (!msg) return
  
  switch (event.type) {
    case 'skill':
      msg.events.push({
        type: 'skill',
        message: event.message,
        skill_name: event.skill_name
      })
      break
    
    case 'thinking':
      if (event.content) {
        msg.events.push({
          type: 'thinking',
          content: event.content
        })
      }
      break
    
    case 'tool_call':
      msg.events.push({
        type: 'tool_call',
        tool_name: event.tool_name,
        arguments: event.arguments,
        message: event.message
      })
      break
    
    case 'tool_result':
      const lastToolEvent = msg.events.findLast((e: any) => e.type === 'tool_call' && e.tool_name === event.tool_name)
      if (lastToolEvent) {
        lastToolEvent.result = event.result
        lastToolEvent.success = event.success
      }
      msg.events.push({
        type: 'tool_result',
        tool_name: event.tool_name,
        success: event.success,
        message: event.message
      })
      break
    
    case 'response':
      msg.content = event.content || ''
      break
    
    case 'error':
      msg.content = `错误: ${event.message}`
      break
  }
}

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const clearChat = () => {
  chatMessages.value = []
}

const getEventIcon = (type: string) => {
  switch (type) {
    case 'tool_call': return ToolIcon
    case 'tool_result': return SuccessIcon
    case 'thinking': return ThinkingIcon
    case 'skill': return SkillIcon
    case 'error': return ErrorIcon
    default: return PlayIcon
  }
}

const getEventColor = (event: ToolCallEvent) => {
  if (event.type === 'tool_result') {
    return event.success ? 'success' : 'error'
  }
  if (event.type === 'error') return 'error'
  if (event.type === 'skill') return 'info'
  return 'default'
}

const groupedTools = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const tool of tools.value) {
    const cat = tool.category || 'general'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(tool)
  }
  return groups
})

onMounted(() => {
  fetchConfig()
  fetchTelegramBotConfig()
  fetchSkills()
  fetchTools()
})
</script>

<template>
  <div class="ai-lab-view">
    <div class="page-header">
      <div>
        <h1>智能助手</h1>
        <div class="subtitle">AI 驱动的番剧管理助手 - 支持工具调用</div>
      </div>
      <n-space align="center">
        <n-switch v-model:value="useTools" size="small">
          <template #checked>工具模式</template>
          <template #unchecked>纯对话</template>
        </n-switch>
        <n-tag type="info" size="large" round ghost>Beta</n-tag>
      </n-space>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated class="assistant-tabs">
      <n-tab-pane name="chat" tab="智能对话">
        <n-card bordered class="chat-card">
          <div class="chat-container" ref="chatContainer">
            <div v-if="chatMessages.length === 0" class="chat-empty">
              <n-icon size="48" :depth="3"><AiIcon /></n-icon>
              <p>开始与智能助手对话</p>
              <p class="hint">你可以询问关于番剧识别、订阅管理、配置优化等问题</p>
              <p class="hint" v-if="useTools">工具模式已启用，助手可以执行实际操作</p>
            </div>
            <div v-else class="chat-messages">
              <div 
                v-for="(msg, idx) in chatMessages" 
                :key="idx" 
                :class="['message', msg.role]"
              >
                <div class="message-avatar">
                  <n-icon v-if="msg.role === 'user'" size="20"><AiIcon /></n-icon>
                  <n-icon v-else size="20"><AiIcon /></n-icon>
                </div>
                <div class="message-content-wrapper">
                  <div v-if="msg.events && msg.events.length > 0" class="tool-events">
                    <div 
                      v-for="(event, eIdx) in msg.events" 
                      :key="eIdx"
                      :class="['event-item', event.type]"
                    >
                      <div class="event-header">
                        <n-icon size="16">
                          <component :is="getEventIcon(event.type)" />
                        </n-icon>
                        <span class="event-type">
                          {{ event.type === 'tool_call' ? '调用工具' : 
                             event.type === 'tool_result' ? '执行结果' :
                             event.type === 'skill' ? '触发技能' :
                             event.type === 'thinking' ? '思考' : event.type }}
                        </span>
                        <span v-if="event.tool_name" class="event-name">{{ event.tool_name }}</span>
                        <span v-if="event.skill_name" class="event-name">{{ event.skill_name }}</span>
                        <n-tag v-if="event.type === 'tool_result'" :type="getEventColor(event)" size="small">
                          {{ event.success ? '成功' : '失败' }}
                        </n-tag>
                      </div>
                      <div v-if="event.message" class="event-message">{{ event.message }}</div>
                      <n-collapse v-if="event.arguments || event.result" class="event-details">
                        <n-collapse-item title="详情">
                          <n-code :code="JSON.stringify(event.arguments || event.result, null, 2)" language="json" />
                        </n-collapse-item>
                      </n-collapse>
                    </div>
                  </div>
                  <div class="message-content">
                    <n-spin v-if="msg.loading" size="small" />
                    <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="chat-input-area">
            <n-input
              v-model:value="chatInput"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="输入消息..."
              @keypress.enter.prevent="sendMessage"
            />
            <n-space>
              <n-button size="small" @click="clearChat" :disabled="chatMessages.length === 0">
                清空对话
              </n-button>
              <n-button type="primary" @click="sendMessage" :loading="chatLoading" :disabled="!chatInput.trim()">
                <template #icon><n-icon><SendIcon /></n-icon></template>
                发送
              </n-button>
            </n-space>
          </div>
        </n-card>
      </n-tab-pane>
      
      <n-tab-pane name="tools" tab="工具列表">
        <n-card bordered>
          <template #header>
            <div class="card-title-box">
              <n-icon style="color: var(--n-primary-color)"><ToolIcon /></n-icon>
              <span class="card-title-text">可用工具 ({{ tools.length }})</span>
            </div>
          </template>
          
          <n-spin :show="toolsLoading">
            <n-collapse v-if="Object.keys(groupedTools).length > 0">
              <n-collapse-item 
                v-for="(toolList, category) in groupedTools" 
                :key="category"
                :title="`${category} (${toolList.length})`"
              >
                <n-list bordered>
                  <n-list-item v-for="tool in toolList" :key="tool.name">
                    <n-thing :title="tool.name" :description="tool.description">
                      <template #header-extra>
                        <n-tag size="small">{{ tool.parameters?.length || 0 }} 参数</n-tag>
                      </template>
                      <div v-if="tool.parameters && tool.parameters.length > 0" class="tool-params">
                        <n-tag v-for="p in tool.parameters" :key="p.name" size="small" :type="p.required ? 'info' : 'default'">
                          {{ p.name }}
                          <span v-if="p.required">*</span>
                        </n-tag>
                      </div>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </n-collapse-item>
            </n-collapse>
            <n-empty v-else description="暂无工具" />
          </n-spin>
        </n-card>
      </n-tab-pane>
      
      <n-tab-pane name="skills" tab="技能管理">
        <n-card bordered>
          <template #header>
            <div class="card-title-box">
              <n-icon style="color: var(--n-primary-color)"><SkillIcon /></n-icon>
              <span class="card-title-text">可用技能 ({{ skills.length }})</span>
            </div>
          </template>
          
          <n-spin :show="skillsLoading">
            <n-list v-if="skills.length > 0" bordered>
              <n-list-item v-for="skill in skills" :key="skill.id">
                <n-thing :title="skill.name" :description="skill.description">
                  <template #avatar>
                    <n-avatar round>
                      <n-icon><SkillIcon /></n-icon>
                    </n-avatar>
                  </template>
                  <template #header-extra>
                    <n-tag size="small">v{{ skill.version }}</n-tag>
                  </template>
                  <div v-if="skill.triggers && skill.triggers.length > 0" class="skill-triggers">
                    <span class="trigger-label">触发词：</span>
                    <n-tag v-for="t in skill.triggers" :key="t" size="small" type="info">{{ t }}</n-tag>
                  </div>
                </n-thing>
              </n-list-item>
            </n-list>
            <n-empty v-else description="暂无技能" />
          </n-spin>
        </n-card>
      </n-tab-pane>
      
      <n-tab-pane name="config" tab="模型配置">
        <n-card bordered>
          <template #header>
            <div class="card-title-box">
              <n-icon style="color: var(--n-primary-color)"><ConfigIcon /></n-icon>
              <span class="card-title-text">模型配置</span>
            </div>
          </template>
          
          <n-spin :show="configLoading">
            <n-form label-placement="left" label-width="120" size="medium">
              <n-form-item label="模型提供商">
                <n-radio-group v-model:value="assistantConfig.provider">
                  <n-radio-button value="openai">OpenAI / 兼容接口</n-radio-button>
                  <n-radio-button value="ollama">Ollama (本地)</n-radio-button>
                </n-radio-group>
              </n-form-item>
              
              <n-form-item label="Base URL">
                <n-input 
                  v-model:value="assistantConfig.base_url" 
                  placeholder="http://localhost:11434 或 https://api.openai.com" 
                />
              </n-form-item>
              
              <n-form-item v-if="assistantConfig.provider === 'openai'" label="API Key">
                <n-input 
                  v-model:value="assistantConfig.api_key" 
                  type="password" 
                  show-password-on="click"
                  placeholder="sk-..." 
                />
              </n-form-item>
              
              <n-form-item label="模型名称">
                <n-input 
                  v-model:value="assistantConfig.model" 
                  placeholder="gpt-4o 或 qwen2.5:7b" 
                />
              </n-form-item>
              
              <n-form-item label="Temperature">
                <n-slider 
                  v-model:value="assistantConfig.temperature" 
                  :min="0" 
                  :max="2" 
                  :step="0.1"
                />
                <span class="slider-value">{{ assistantConfig.temperature }}</span>
              </n-form-item>
              
              <n-form-item label="Max Tokens (K)">
                <n-input-number 
                  v-model:value="assistantConfig.max_tokens" 
                  :min="1" 
                  :max="128"
                />
              </n-form-item>
              
              <n-form-item label="最大迭代次数">
                <n-input-number 
                  v-model:value="assistantConfig.max_iterations" 
                  :min="1" 
                  :max="20"
                />
                <n-tooltip>
                  <template #trigger>
                    <n-icon size="18" style="margin-left: 8px; cursor: help;"><ThinkingIcon /></n-icon>
                  </template>
                  工具调用的最大循环次数，防止无限循环
                </n-tooltip>
              </n-form-item>
              
              <n-divider style="margin: 16px 0;">识别增强</n-divider>
              
              <n-form-item label="AI 智能介入">
                <n-switch v-model:value="assistantConfig.ai_fallback_enabled" />
                <n-text depth="3" style="margin-left: 12px; font-size: 12px">
                  识别失败时，让 AI 猜测标题并重新搜索
                </n-text>
              </n-form-item>
              
              <n-alert type="info" size="small" :show-icon="false" style="margin-bottom: 16px;">
                启用后，当常规识别流程无法匹配到 TMDB 数据时，AI 会分析文件名并猜测可能的标题变体，然后重新搜索。
              </n-alert>
              
              <n-divider style="margin: 16px 0;">Telegram Bot</n-divider>
              
              <n-form-item label="启用 Bot 对话">
                <n-switch v-model:value="telegramBotConfig.enabled" @update:value="saveTelegramBotConfig" />
                <n-text depth="3" style="margin-left: 12px; font-size: 12px">
                  通过 Telegram 与智能体对话
                </n-text>
              </n-form-item>
              
              <n-form-item label="允许的 Chat ID" :style="{ opacity: telegramBotConfig.enabled ? 1 : 0.5 }">
                <n-input 
                  v-model:value="telegramBotConfig.allowedChats"
                  placeholder="多个用逗号分隔，留空则不限制"
                  :disabled="!telegramBotConfig.enabled"
                  @blur="saveTelegramBotConfig"
                />
                <n-tooltip>
                  <template #trigger>
                    <n-icon size="18" style="margin-left: 8px; cursor: help;"><ThinkingIcon /></n-icon>
                  </template>
                  只有指定的 Chat ID 才能使用 Bot，留空则允许所有人
                </n-tooltip>
              </n-form-item>
              
              <n-alert type="info" size="small" :show-icon="false" style="margin-bottom: 16px;">
                启用后，向你的 Telegram Bot 发送消息即可与智能体对话。需要先在设置中配置 Bot Token。
              </n-alert>
              
              <n-form-item>
                <n-button type="primary" :loading="saveLoading" @click="saveConfig">
                  <template #icon><n-icon><SaveIcon /></n-icon></template>
                  保存配置
                </n-button>
              </n-form-item>
            </n-form>
          </n-spin>
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: var(--text-primary);
}

.subtitle {
  font-size: 14px;
  color: var(--n-primary-color);
  letter-spacing: 1px;
  font-weight: bold;
}

.assistant-tabs :deep(.n-tabs-tab) {
  padding: 0 24px;
}

.chat-card {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 280px);
  min-height: 400px;
}

.chat-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding: 16px;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg-surface);
  border-radius: 8px;
  margin-bottom: 16px;
  min-height: 0;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
}

.chat-empty .hint {
  font-size: 12px;
  color: var(--text-quaternary);
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 90%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--n-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.message.assistant .message-avatar {
  background: var(--n-success-color);
}

.message-content-wrapper {
  flex: 1;
  min-width: 0;
}

.tool-events {
  margin-bottom: 8px;
}

.event-item {
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-surface-2);
  margin-bottom: 6px;
  font-size: 13px;
}

.event-item.tool_call {
  border-left: 3px solid var(--n-primary-color);
}

.event-item.tool_result {
  border-left: 3px solid var(--n-success-color);
}

.event-item.tool_result:not(.success) {
  border-left-color: var(--n-error-color);
}

.event-item.skill {
  border-left: 3px solid var(--n-info-color);
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-type {
  font-weight: 500;
  color: var(--text-secondary);
}

.event-name {
  color: var(--n-primary-color);
  font-family: monospace;
}

.event-message {
  margin-top: 4px;
  color: var(--text-tertiary);
}

.event-details {
  margin-top: 8px;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--app-surface-card);
  border: 1px solid var(--border-light);
  line-height: 1.6;
}

.message.user .message-content {
  background: var(--n-primary-color);
  color: white;
  border: none;
}

.markdown-body {
  line-height: 1.7;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.markdown-body h1 { font-size: 1.4em; }
.markdown-body h2 { font-size: 1.2em; }
.markdown-body h3 { font-size: 1.1em; }

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid var(--border-light);
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: var(--app-surface-hover);
  font-weight: 600;
}

.markdown-body code {
  background: var(--app-surface-hover);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.markdown-body pre {
  background: var(--app-surface-hover);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-body pre code {
  background: none;
  padding: 0;
}

.markdown-body blockquote {
  border-left: 4px solid var(--n-primary-color);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--text-secondary);
}

.markdown-body hr {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: 16px 0;
}

.markdown-body strong {
  font-weight: 600;
}

.message.user .markdown-body code {
  background: rgba(255,255,255,0.2);
}

.message.user .markdown-body th,
.message.user .markdown-body td {
  border-color: rgba(255,255,255,0.3);
}

.message.user .markdown-body th {
  background: rgba(255,255,255,0.1);
}

.chat-input-area {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title-text {
  font-weight: 600;
}

.slider-value {
  margin-left: 12px;
  min-width: 40px;
  text-align: center;
  font-family: monospace;
}

.tool-params {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.skill-triggers {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.trigger-label {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
