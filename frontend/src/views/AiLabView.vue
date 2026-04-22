<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NDivider, NGrid, NGi, 
  NTag, useMessage, NScrollbar, NAlert, NText, NSwitch, NSlider,
  NCollapse, NCollapseItem, NForm, NFormItem, NInputNumber, NEmpty,
  NTabs, NTabPane, NList, NListItem, NThing, NBadge, NAvatar,
  NSkeleton, NSpin, NRadioGroup, NRadioButton
} from 'naive-ui'
import {
  SmartToyOutlined as AiIcon,
  SettingsOutlined as ConfigIcon,
  SaveOutlined as SaveIcon,
  ExtensionOutlined as SkillIcon,
  SendOutlined as SendIcon
} from '@vicons/material'

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const activeTab = ref('chat')

const configLoading = ref(false)
const saveLoading = ref(false)

const assistantConfig = ref({
  base_url: '',
  api_key: '',
  model: '',
  provider: 'ollama',
  temperature: 0.7,
  max_tokens: 64
})

const skills = ref<any[]>([])
const skillsLoading = ref(false)

const chatMessages = ref<Array<{role: string, content: string, loading?: boolean}>>([])
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

const sendMessage = async () => {
  if (!chatInput.value.trim() || chatLoading.value) return
  
  const userMessage = chatInput.value.trim()
  chatMessages.value.push({ role: 'user', content: userMessage })
  chatInput.value = ''
  chatLoading.value = true
  
  const msgIndex = chatMessages.value.length
  chatMessages.value.push({ role: 'assistant', content: '', loading: true })
  
  await nextTick()
  scrollToBottom()
  
  try {
    const res = await fetch(`${API_BASE}/api/assistant/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        messages: chatMessages.value.filter(m => !m.loading).map(m => ({ role: m.role, content: m.content })),
        stream: false
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      chatMessages.value[msgIndex].content = data.choices?.[0]?.message?.content || '无响应'
    } else {
      const errorData = await res.json()
      chatMessages.value[msgIndex].content = errorData.detail || '请求失败，请检查模型配置'
    }
  } catch (e) {
    chatMessages.value[msgIndex].content = '网络错误，请稍后重试'
  } finally {
    chatMessages.value[msgIndex].loading = false
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
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

onMounted(() => {
  fetchConfig()
  fetchSkills()
})
</script>

<template>
  <div class="ai-lab-view">
    <div class="page-header">
      <div>
        <h1>智能助手</h1>
        <div class="subtitle">AI 驱动的番剧管理助手</div>
      </div>
      <n-tag type="info" size="large" round ghost>Beta</n-tag>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated class="assistant-tabs">
      <n-tab-pane name="chat" tab="智能对话">
        <n-card bordered class="chat-card">
          <div class="chat-container" ref="chatContainer">
            <div v-if="chatMessages.length === 0" class="chat-empty">
              <n-icon size="48" :depth="3"><AiIcon /></n-icon>
              <p>开始与智能助手对话</p>
              <p class="hint">你可以询问关于番剧识别、订阅管理、配置优化等问题</p>
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
                <div class="message-content">
                  <n-spin v-if="msg.loading" size="small" />
                  <span v-else>{{ msg.content }}</span>
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
      
      <n-tab-pane name="skills" tab="技能管理">
        <n-card bordered>
          <template #header>
            <div class="card-title-box">
              <n-icon style="color: var(--n-primary-color)"><SkillIcon /></n-icon>
              <span class="card-title-text">可用技能</span>
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
                  <n-radio-button value="ollama">Ollama (本地)</n-radio-button>
                  <n-radio-button value="openai">OpenAI / 兼容接口</n-radio-button>
                </n-radio-group>
              </n-form-item>
              
              <n-form-item label="Base URL">
                <n-input 
                  v-model:value="assistantConfig.base_url" 
                  placeholder="http://localhost:11434" 
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
                  placeholder="qwen2.5:7b 或 gpt-4" 
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
      
      <n-tab-pane name="lab" tab="AI 实验室">
        <n-alert type="info" title="AI 实验室" style="margin-bottom: 16px;">
          大语言模型解析沙箱，用于测试复杂文件名的语义提取能力。
        </n-alert>
        
        <n-card bordered title="功能说明">
          <p>AI 实验室提供以下测试功能：</p>
          <ul class="feature-list">
            <li>极端标题提取 - 从复杂文件名中提取作品名</li>
            <li>复杂集数推断 - 理解非标准集数描述</li>
            <li>语义消除歧义 - 处理多义性文件名</li>
            <li>Prompt 提示词工程 - 评估模型表现</li>
          </ul>
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
  max-width: 80%;
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

.feature-list {
  margin: 12px 0 0 20px;
  padding: 0;
  color: var(--text-secondary);
  line-height: 2;
}
</style>
