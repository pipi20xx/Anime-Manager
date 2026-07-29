<script setup lang="ts">
/**
 * AiLabView — AI 实验室
 *
 * 功能:
 * - AI 助手配置 (模型/温度/token/回退等)
 * - AI 对话 (流式)
 * - 技能管理
 * - Telegram Bot 配置
 */
import { ref, reactive, onMounted, nextTick } from 'vue'
import { apiFetch } from '@/api/client'
import { configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'AiLabView' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const activeTab = ref('chat')
const configLoading = ref(false)
const saveLoading = ref(false)

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

// 技能
const skills = ref<any[]>([])
const skillsLoading = ref(false)
const expandedSkillId = ref<string | null>(null)
const skillDetail = ref<any>(null)
const skillDetailLoading = ref(false)

// 对话
interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  loading?: boolean
  events?: any[]
  isStreaming?: boolean
}

const chatMessages = ref<ChatMessage[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const PROVIDER_OPTIONS = [
  { title: 'Ollama', value: 'ollama' },
  { title: 'OpenAI', value: 'openai' },
  { title: 'DeepSeek', value: 'deepseek' },
  { title: '自定义', value: 'custom' },
]

// --- 配置 ---
async function fetchConfig() {
  configLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/config')
    if (data) {
      Object.assign(assistantConfig, data)
    }
  } catch (e) {
    // 配置加载失败不阻塞
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  saveLoading.value = true
  try {
    await apiFetch('/api/assistant/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(assistantConfig),
    })
    success('AI 配置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saveLoading.value = false
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
  } catch (e) {
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

// --- 技能 ---
async function fetchSkills() {
  skillsLoading.value = true
  try {
    const data = await apiFetch('/api/assistant/skills')
    skills.value = Array.isArray(data) ? data : []
  } catch (e) {
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
  } catch (e) {
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
  try {
    await apiFetch('/api/assistant/skills/' + skill.id + '/enabled', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newEnabled }),
    })
    skill.enabled = newEnabled
    success('技能已' + (newEnabled ? '启用' : '禁用'))
  } catch (e: any) {
    showError(e?.message || '操作失败')
  }
}

// --- 对话 ---
async function sendMessage() {
  if (!chatInput.value.trim() || chatLoading.value) return

  const userMessage = chatInput.value.trim()
  chatInput.value = ''

  chatMessages.value.push({
    role: 'user',
    content: userMessage,
  })

  // 添加助手占位
  const assistantMessage: ChatMessage = {
    role: 'assistant',
    content: '',
    loading: true,
    events: [],
  }
  chatMessages.value.push(assistantMessage)
  chatLoading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const data = await apiFetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        use_tools: assistantConfig.use_tools,
      }),
    })

    assistantMessage.content = (data as any)?.response || (data as any)?.content || (data as any)?.message || JSON.stringify(data)
    assistantMessage.loading = false
    assistantMessage.events = (data as any)?.events || []
  } catch (e: any) {
    assistantMessage.content = '对话失败: ' + (e?.message || '未知错误')
    assistantMessage.loading = false
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function clearChat() {
  chatMessages.value = []
}

onMounted(() => {
  fetchConfig()
  fetchTelegramConfig()
  fetchSkills()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <h1 class="text-h5 font-weight-bold">AI 实验室</h1>
      <div class="text-body-2 text-medium-emphasis mt-1">AI 语义解析与智能助手</div>
    </div>

    <v-tabs v-model="activeTab" color="primary" class="sticky-tabs">
      <v-tab value="chat">
        <v-icon start size="18">mdi-chat-outline</v-icon>
        AI 对话
      </v-tab>
      <v-tab value="config">
        <v-icon start size="18">mdi-cog-outline</v-icon>
        助手配置
      </v-tab>
      <v-tab value="skills">
        <v-icon start size="18">mdi-lightning-bolt-outline</v-icon>
        技能管理
      </v-tab>
      <v-tab value="telegram">
        <v-icon start size="18">mdi-telegram</v-icon>
        Telegram Bot
      </v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- AI 对话 -->
      <v-window-item value="chat">
        <v-card class="glass-card" style="height: calc(100vh - 280px); display: flex; flex-direction: column;">
          <!-- 对话消息区 -->
          <div ref="chatContainer" class="flex-grow-1 overflow-y-auto pa-4" style="min-height: 0">
            <div v-if="chatMessages.length === 0" class="text-center pa-8">
              <v-icon size="64" color="primary" class="mb-4">mdi-robot-outline</v-icon>
              <div class="text-h6 font-weight-medium">AI 助手</div>
              <div class="text-body-2 text-medium-emphasis mt-2">输入消息开始对话，支持工具调用</div>
            </div>

            <div v-for="(msg, index) in chatMessages" :key="index" class="mb-4">
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="d-flex justify-end">
                <v-chip color="primary" variant="flat" class="pa-3" style="max-width: 80%; white-space: pre-wrap;">
                  {{ msg.content }}
                </v-chip>
              </div>

              <!-- 助手消息 -->
              <div v-else class="d-flex justify-start">
                <v-chip variant="tonal" class="pa-3" style="max-width: 80%; white-space: pre-wrap;">
                  <v-icon v-if="msg.loading" class="mr-2" size="16">mdi-loading mdi-spin</v-icon>
                  {{ msg.content || '...' }}
                </v-chip>
              </div>

              <!-- 工具调用事件 -->
              <div v-if="msg.events?.length" class="mt-1 ml-8">
                <div v-for="(event, ei) in msg.events" :key="ei" class="text-caption text-medium-emphasis mb-1">
                  <v-icon size="12" color="info">mdi-wrench-outline</v-icon>
                  {{ event.tool_name || event.type }}
                  <span v-if="event.success !== undefined" :class="event.success ? 'text-success' : 'text-error'">
                    {{ event.success ? ' ✓' : ' ✗' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <v-divider />

          <!-- 输入区 -->
          <div class="pa-3 d-flex ga-2">
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
              color="primary"
              variant="flat"
              icon="mdi-send"
              :loading="chatLoading"
              @click="sendMessage"
            />
            <v-btn
              variant="tonal"
              color="error"
              size="small"
              prepend-icon="mdi-delete-outline"
              @click="clearChat"
            >清空</v-btn>
          </div>
        </v-card>
      </v-window-item>

      <!-- 助手配置 -->
      <v-window-item value="config">
        <v-row>
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2">
                <div class="text-subtitle-1 font-weight-bold">AI 模型配置</div>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <v-select v-model="assistantConfig.provider" label="模型提供商" :items="PROVIDER_OPTIONS" density="compact" class="mb-3" />
                <v-text-field v-model="assistantConfig.base_url" label="API 地址" density="compact" class="mb-3" placeholder="如 http://localhost:11434" />
                <v-text-field v-model="assistantConfig.api_key" label="API Key" density="compact" type="password" class="mb-3" />
                <v-text-field v-model="assistantConfig.model" label="模型名称" density="compact" class="mb-3" placeholder="如 qwen2.5:7b" />
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2">
                <div class="text-subtitle-1 font-weight-bold">推理参数</div>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <div class="d-flex align-center ga-3 mb-4">
                  <span class="text-body-2 text-medium-emphasis" style="min-width: 80px">温度</span>
                  <v-slider v-model="assistantConfig.temperature" :min="0" :max="2" :step="0.1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ assistantConfig.temperature }}</v-chip>
                </div>
                <v-text-field v-model.number="assistantConfig.max_tokens" label="最大 Token 数" type="number" density="compact" class="mb-3" />
                <v-text-field v-model.number="assistantConfig.max_iterations" label="最大迭代次数" type="number" density="compact" class="mb-3" />
                <v-switch v-model="assistantConfig.use_tools" label="启用工具调用" density="compact" hide-details color="primary" class="mb-2" />
                <v-switch v-model="assistantConfig.ai_fallback_enabled" label="AI 识别回退" density="compact" hide-details color="primary" hint="识别失败时自动使用 AI 解析" persistent-hint />
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <div class="mt-4 d-flex justify-end ga-2">
          <v-btn color="primary" variant="flat" :loading="saveLoading" @click="saveConfig">
            保存配置
          </v-btn>
        </div>
      </v-window-item>

      <!-- 技能管理 -->
      <v-window-item value="skills">
        <template v-if="skillsLoading">
          <v-skeleton-loader v-for="i in 3" :key="i" type="list-item-two-line" class="mb-3" />
        </template>

        <template v-else-if="skills.length > 0">
          <v-card v-for="skill in skills" :key="skill.id" class="glass-card mb-3">
            <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
              <div class="d-flex align-center ga-3">
                <v-icon color="primary">mdi-lightning-bolt-outline</v-icon>
                <div>
                  <div class="text-subtitle-2 font-weight-bold">{{ skill.name || skill.id }}</div>
                  <div v-if="skill.description" class="text-caption text-medium-emphasis">{{ skill.description }}</div>
                </div>
              </div>
              <div class="d-flex ga-2 align-center">
                <v-switch
                  :model-value="skill.enabled"
                  density="compact"
                  hide-details
                  color="primary"
                  @update:model-value="toggleSkillEnabled(skill)"
                />
                <v-btn
                  size="small"
                  variant="text"
                  :icon="expandedSkillId === skill.id ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                  @click="toggleSkillExpand(skill.id)"
                />
              </div>
            </v-card-title>

            <v-expand-transition>
              <div v-if="expandedSkillId === skill.id">
                <v-divider />
                <v-card-text class="pa-4">
                  <div v-if="skillDetailLoading" class="text-center pa-4">
                    <v-progress-circular indeterminate size="24" color="primary" />
                  </div>
                  <div v-else-if="skillDetail">
                    <div class="text-body-2 mb-3" style="white-space: pre-wrap;">{{ skillDetail.description || '暂无描述' }}</div>

                    <div v-if="skillDetail.tools?.length" class="mb-3">
                      <div class="text-subtitle-2 font-weight-medium mb-2">可用工具</div>
                      <v-chip v-for="tool in skillDetail.tools" :key="tool.name || tool" size="small" variant="tonal" class="mr-1 mb-1">
                        {{ tool.name || tool }}
                      </v-chip>
                    </div>

                    <div v-if="skillDetail.parameters">
                      <div class="text-subtitle-2 font-weight-medium mb-2">参数</div>
                      <pre class="text-caption bg-surface-variant pa-3 rounded-lg overflow-auto" style="max-height: 200px;">{{ JSON.stringify(skillDetail.parameters, null, 2) }}</pre>
                    </div>
                  </div>
                  <div v-else class="text-caption text-medium-emphasis">加载失败</div>
                </v-card-text>
              </div>
            </v-expand-transition>
          </v-card>
        </template>

        <div v-else class="text-center pa-8">
          <v-icon size="48" color="primary" class="mb-3">mdi-lightning-bolt-outline</v-icon>
          <div class="text-body-1">暂无技能</div>
        </div>
      </v-window-item>

      <!-- Telegram Bot -->
      <v-window-item value="telegram">
        <v-row>
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">Telegram Bot</div>
                  <div class="text-caption text-medium-emphasis">通过 Telegram 机器人远程控制</div>
                </div>
                <v-switch v-model="telegramConfig.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <v-textarea
                  v-model="telegramConfig.allowedChats"
                  label="允许的 Chat ID"
                  placeholder="输入 Chat ID，多个用逗号分隔"
                  density="compact"
                  rows="3"
                  hide-details
                  class="mb-3"
                />
                <div class="text-caption text-medium-emphasis">
                  提示：配置保存后需重启服务才能生效
                </div>
              </v-card-text>
              <v-divider />
              <v-card-actions class="pa-4">
                <v-spacer />
                <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveTelegramConfig">保存配置</v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>
    </v-window>
  </v-container>
</template>
