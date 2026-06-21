<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { 
  NCard, NSpace, NButton, NInput, NDivider, 
  NTag, useMessage, NAlert, NText, NSwitch, NSlider,
  NCollapse, NCollapseItem, NForm, NFormItem, NInputNumber, NEmpty,
  NTabs, NTabPane, NList, NListItem, NThing,
  NSpin, NRadioGroup, NRadioButton, NCode
} from 'naive-ui'
import { marked } from 'marked'
import {
  SmartToyOutlined as ChatIcon,
  BuildOutlined as ToolsIcon,
  SchoolOutlined as SkillsIcon,
  SettingsOutlined as ConfigIcon
} from '@vicons/material'

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text: string) => {
  if (!text) return ''
  return marked.parse(text) as string
}

const props = defineProps<{
  externalConfig?: any
}>()

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const activeTab = ref('chat')

const configLoading = ref(false)
const saveLoading = ref(false)

const internalConfig = ref({
  base_url: '',
  api_key: '',
  model: '',
  provider: 'ollama',
  temperature: 0.7,
  max_tokens: 64,
  max_iterations: 10,
  ai_fallback_enabled: false,
  use_tools: true
})

const assistantConfig = computed(() => {
  if (props.externalConfig?.assistant_config) {
    return props.externalConfig.assistant_config
  }
  return internalConfig.value
})

const internalUseTools = ref(true)

const useTools = computed({
  get: () => {
    if (props.externalConfig?.assistant_config?.use_tools !== undefined) {
      return props.externalConfig.assistant_config.use_tools
    }
    return internalUseTools.value
  },
  set: (val) => {
    if (props.externalConfig?.assistant_config) {
      props.externalConfig.assistant_config.use_tools = val
    } else {
      internalUseTools.value = val
    }
  }
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

const getAuthHeaders = () => {
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

const fetchConfig = async () => {
  if (props.externalConfig) return
  
  configLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/assistant/config`, {
      headers: getAuthHeaders()
    })
    if (res.ok) {
      const data = await res.json()
      internalConfig.value = { ...internalConfig.value, ...data }
      internalUseTools.value = data.use_tools !== undefined ? data.use_tools : true
    }
  } catch (e) {
    message.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

const saveUseTools = async () => {
  if (props.externalConfig) return
  
  try {
    const res = await fetch(`${API_BASE}/api/assistant/config`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ use_tools: useTools.value })
    })
    if (res.ok) {
      message.success(useTools.value ? '已启用工具模式' : '已切换为纯对话模式')
    }
  } catch (e) {
    console.error('保存工具模式失败', e)
  }
}

const saveConfig = async () => {
  if (props.externalConfig) {
    message.success('配置已保存，请点击页面右上角的"保存全部修改"按钮')
    return
  }
  
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
      msg.events.push({ type: 'skill', message: event.message, skill_name: event.skill_name })
      break
    case 'thinking':
      if (event.content) {
        msg.events.push({ type: 'thinking', content: event.content })
      }
      break
    case 'tool_call':
      msg.events.push({ type: 'tool_call', tool_name: event.tool_name, arguments: event.arguments, message: event.message })
      break
    case 'tool_result':
      const lastToolEvent = msg.events.findLast((e: any) => e.type === 'tool_call' && e.tool_name === event.tool_name)
      if (lastToolEvent) {
        lastToolEvent.result = event.result
        lastToolEvent.success = event.success
      }
      msg.events.push({ type: 'tool_result', tool_name: event.tool_name, success: event.success, message: event.message })
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
  <div class="m-page m-page-safe-bottom">
    <!-- Header -->
    <div class="m-header">
      <div class="m-header-title" style="font-size: var(--m-text-lg);">AI 智能助手</div>
      <n-space align="center">
        <n-switch v-model:value="useTools" size="small" @update:value="saveUseTools">
          <template #checked>工具</template>
          <template #unchecked>对话</template>
        </n-switch>
        <n-tag type="info" size="small" round ghost>Beta</n-tag>
      </n-space>
    </div>

    <!-- Content -->
    <div class="ai-content">
      <n-tabs v-model:value="activeTab" type="line" animated class="m-tabs ai-tabs" pane-class="ai-tab-pane">
        <n-tab-pane name="chat" tab="对话">
          <template #tab>
            <div class="tab-label">
              <n-icon size="18"><ChatIcon /></n-icon>
              <span>对话</span>
            </div>
          </template>
          <div class="chat-tab">
            <div class="chat-container-mobile" ref="chatContainer">
              <div v-if="chatMessages.length === 0" class="m-empty" style="padding: var(--m-spacing-2xl) 0;">
                <div class="m-empty-title">开始与智能助手对话</div>
                <div class="m-empty-desc">可询问番剧识别、订阅管理、配置优化等问题</div>
                <div v-if="useTools" class="m-empty-desc" style="margin-top: var(--m-spacing-sm);">工具模式已启用，助手可以执行实际操作</div>
              </div>
              <div v-else class="chat-messages-mobile">
                <div 
                  v-for="(msg, idx) in chatMessages" 
                  :key="idx" 
                  :class="['message-mobile', msg.role]"
                >
                  <div v-if="msg.events && msg.events.length > 0" class="tool-events-mobile">
                    <div 
                      v-for="(event, eIdx) in msg.events" 
                      :key="eIdx"
                      :class="['event-item-mobile', event.type]"
                    >
                      <div class="event-header-mobile">
                        <span class="event-type-mobile">
                          {{ event.type === 'tool_call' ? '调用工具' : 
                             event.type === 'tool_result' ? '执行结果' :
                             event.type === 'skill' ? '触发技能' :
                             event.type === 'thinking' ? '思考' : event.type }}
                        </span>
                        <span v-if="event.tool_name" class="event-name-mobile">{{ event.tool_name }}</span>
                        <span v-if="event.skill_name" class="event-name-mobile">{{ event.skill_name }}</span>
                        <n-tag v-if="event.type === 'tool_result'" :type="getEventColor(event)" size="tiny">
                          {{ event.success ? '成功' : '失败' }}
                        </n-tag>
                      </div>
                      <div v-if="event.message" class="event-message-mobile">{{ event.message }}</div>
                      <n-collapse v-if="event.arguments || event.result" class="event-details-mobile">
                        <n-collapse-item title="详情">
                          <n-code :code="JSON.stringify(event.arguments || event.result, null, 2)" language="json" />
                        </n-collapse-item>
                      </n-collapse>
                    </div>
                  </div>
                  <div class="message-content-mobile">
                    <n-spin v-if="msg.loading" size="small" />
                    <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="chat-input-area-mobile">
              <n-input
                v-model:value="chatInput"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 4 }"
                placeholder="输入消息..."
                @keypress.enter.prevent="sendMessage"
              />
              <n-button type="primary" :loading="chatLoading" :disabled="!chatInput.trim()" @click="sendMessage">
                发送
              </n-button>
            </div>
          </div>
        </n-tab-pane>
        
        <n-tab-pane name="tools" tab="工具">
          <template #tab>
            <div class="tab-label">
              <n-icon size="18"><ToolsIcon /></n-icon>
              <span>工具</span>
            </div>
          </template>
          <div class="m-tab-content">
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
                          <n-tag size="tiny">{{ tool.parameters?.length || 0 }} 参数</n-tag>
                        </template>
                        <div v-if="tool.parameters && tool.parameters.length > 0" class="tool-params-mobile">
                          <n-tag v-for="p in tool.parameters" :key="p.name" size="tiny" :type="p.required ? 'info' : 'default'">
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
          </div>
        </n-tab-pane>
        
        <n-tab-pane name="skills" tab="技能">
          <template #tab>
            <div class="tab-label">
              <n-icon size="18"><SkillsIcon /></n-icon>
              <span>技能</span>
            </div>
          </template>
          <div class="m-tab-content">
            <n-spin :show="skillsLoading">
              <n-list v-if="skills.length > 0" bordered>
                <n-list-item v-for="skill in skills" :key="skill.id">
                  <n-thing :title="skill.name" :description="skill.description">
                    <template #header-extra>
                      <n-tag size="tiny">v{{ skill.version }}</n-tag>
                    </template>
                    <div v-if="skill.triggers && skill.triggers.length > 0" class="skill-triggers-mobile">
                      <span class="trigger-label-mobile">触发词：</span>
                      <n-tag v-for="t in skill.triggers" :key="t" size="tiny" type="info">{{ t }}</n-tag>
                    </div>
                  </n-thing>
                </n-list-item>
              </n-list>
              <n-empty v-else description="暂无技能" />
            </n-spin>
          </div>
        </n-tab-pane>
        
        <n-tab-pane name="config" tab="配置">
          <template #tab>
            <div class="tab-label">
              <n-icon size="18"><ConfigIcon /></n-icon>
              <span>配置</span>
            </div>
          </template>
          <div class="m-tab-content">
            <n-spin :show="configLoading">
              <n-form label-placement="top" size="medium">
                <n-form-item label="模型提供商">
                  <n-radio-group v-model:value="assistantConfig.provider">
                    <n-radio-button value="openai">OpenAI / 兼容接口</n-radio-button>
                    <n-radio-button value="ollama">Ollama (本地)</n-radio-button>
                  </n-radio-group>
                </n-form-item>
                
                <n-form-item label="Base URL">
                  <n-input v-model:value="assistantConfig.base_url" placeholder="http://localhost:11434 或 https://api.openai.com" />
                </n-form-item>
                
                <n-form-item v-if="assistantConfig.provider === 'openai'" label="API Key">
                  <n-input v-model:value="assistantConfig.api_key" type="password" show-password-on="click" placeholder="sk-..." />
                </n-form-item>
                
                <n-form-item label="模型名称">
                  <n-input v-model:value="assistantConfig.model" placeholder="gpt-4o 或 qwen2.5:7b" />
                </n-form-item>
                
                <n-form-item label="Temperature">
                  <n-slider v-model:value="assistantConfig.temperature" :min="0" :max="2" :step="0.1" />
                  <span class="slider-value-mobile">{{ assistantConfig.temperature }}</span>
                </n-form-item>
                
                <n-form-item label="Max Tokens (K)">
                  <n-input-number v-model:value="assistantConfig.max_tokens" :min="1" :max="128" />
                </n-form-item>
                
                <n-form-item label="最大迭代次数">
                  <n-input-number v-model:value="assistantConfig.max_iterations" :min="1" :max="20" />
                </n-form-item>
                
                <n-divider>识别增强</n-divider>
                
                <n-form-item label="AI 智能介入">
                  <n-switch v-model:value="assistantConfig.ai_fallback_enabled" />
                  <n-text depth="3" style="margin-left: 12px; font-size: 12px">
                    识别失败时，让 AI 猜测标题并重新搜索
                  </n-text>
                </n-form-item>
                
                <n-alert type="info" size="small" :show-icon="false" style="margin-bottom: 16px;">
                  启用后，当常规识别流程无法匹配到 TMDB 数据时，AI 会分析文件名并猜测可能的标题变体，然后重新搜索。
                </n-alert>
                
                <n-divider>Telegram Bot</n-divider>
                
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
                </n-form-item>
                
                <n-alert type="info" size="small" :show-icon="false" style="margin-bottom: 16px;">
                  启用后，向你的 Telegram Bot 发送消息即可与智能体对话。需要先在设置中配置 Bot Token。
                </n-alert>
                
                <n-form-item>
                  <n-button type="primary" block :loading="saveLoading" @click="saveConfig">
                    保存配置
                  </n-button>
                </n-form-item>
              </n-form>
            </n-spin>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<style scoped>
.ai-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ai-tabs :deep(.n-tabs-nav) {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
}

.ai-tabs :deep(.n-tabs-tab) {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
}

.ai-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

.ai-tab-pane {
  height: 100%;
  overflow: hidden;
  padding: 0;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-xs);
  font-size: var(--m-text-sm);
}

.chat-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--m-spacing-md);
  box-sizing: border-box;
}

.chat-container-mobile {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-spacing-md);
  background: var(--bg-surface);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-spacing-md);
  -webkit-overflow-scrolling: touch;
}

.chat-messages-mobile {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-lg);
}

.message-mobile {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
  max-width: 92%;
}

.message-mobile.user {
  margin-left: auto;
  align-items: flex-end;
}

.message-mobile.assistant {
  align-items: flex-start;
}

.message-content-mobile {
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-lg);
  background: var(--app-surface-card);
  border: 1px solid var(--border-light);
  line-height: 1.6;
  font-size: var(--m-text-md);
}

.message-mobile.user .message-content-mobile {
  background: var(--n-primary-color);
  color: white;
  border: none;
}

.tool-events-mobile {
  width: 100%;
}

.event-item-mobile {
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  background: var(--bg-surface-2);
  margin-bottom: var(--m-spacing-xs);
  font-size: var(--m-text-sm);
}

.event-item-mobile.tool_call {
  border-left: 3px solid var(--n-primary-color);
}

.event-item-mobile.tool_result {
  border-left: 3px solid var(--n-success-color);
}

.event-item-mobile.tool_result:not(.success) {
  border-left-color: var(--n-error-color);
}

.event-item-mobile.skill {
  border-left: 3px solid var(--n-info-color);
}

.event-header-mobile {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  flex-wrap: wrap;
}

.event-type-mobile {
  font-weight: 500;
  color: var(--text-secondary);
}

.event-name-mobile {
  color: var(--n-primary-color);
  font-family: monospace;
  font-size: var(--m-text-xs);
}

.event-message-mobile {
  margin-top: var(--m-spacing-xs);
  color: var(--text-tertiary);
}

.event-details-mobile {
  margin-top: var(--m-spacing-sm);
}

.chat-input-area-mobile {
  display: flex;
  gap: var(--m-spacing-md);
  align-items: flex-end;
  flex-shrink: 0;
  padding: var(--m-spacing-sm);
  background: var(--app-surface-card);
  border: 1px solid var(--border-light);
  border-radius: var(--m-radius-lg);
}

.chat-input-area-mobile .n-input {
  flex: 1;
}

.tool-params-mobile {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-spacing-xs);
  margin-top: var(--m-spacing-sm);
}

.skill-triggers-mobile {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--m-spacing-xs);
  margin-top: var(--m-spacing-sm);
}

.trigger-label-mobile {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
}

.slider-value-mobile {
  margin-left: var(--m-spacing-md);
  min-width: 40px;
  text-align: center;
  font-family: monospace;
  font-size: var(--m-text-sm);
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

.markdown-body h1 { font-size: 1.3em; }
.markdown-body h2 { font-size: 1.15em; }
.markdown-body h3 { font-size: 1.05em; }

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: var(--m-text-sm);
}

.markdown-body th,
.markdown-body td {
  border: 1px solid var(--border-light);
  padding: 6px 8px;
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

.message-mobile.user .markdown-body code {
  background: rgba(255,255,255,0.2);
}

.message-mobile.user .markdown-body th,
.message-mobile.user .markdown-body td {
  border-color: rgba(255,255,255,0.3);
}

.message-mobile.user .markdown-body th {
  background: rgba(255,255,255,0.1);
}
</style>