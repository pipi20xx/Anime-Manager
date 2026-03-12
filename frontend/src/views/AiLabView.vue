<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NInput, NDivider, NGrid, NGi, 
  NTag, useMessage, NCode, NLog, NScrollbar, NAlert, NText,
  NCollapse, NCollapseItem, NForm, NFormItem
} from 'naive-ui'
import {
  SmartToyOutlined as AiIcon,
  ScienceOutlined as LabIcon,
  PlayArrowOutlined as RunIcon,
  CodeOutlined as CodeIcon,
  SettingsOutlined as ConfigIcon,
  SaveOutlined as SaveIcon
} from '@vicons/material'

const message = useMessage()
const loading = ref(false)
const configLoading = ref(false)
const saveLoading = ref(false)
const inputFilename = ref('')
const result = ref<any>(null)
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

// 完整配置对象缓存
const fullConfig = ref<any>({})
const aiConfig = ref({
  openai_base_url: '',
  openai_api_key: '',
  openai_model: ''
})

const fetchConfig = async () => {
  configLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/config`)
    const data = await res.json()
    fullConfig.value = data
    if (data.ai_config) {
      aiConfig.value = { ...data.ai_config }
    }
  } catch (e) {
    message.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

const saveAiConfig = async () => {
  saveLoading.value = true
  try {
    // 更新 fullConfig 中的 ai_config
    fullConfig.value.ai_config = { ...aiConfig.value }
    
    await fetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fullConfig.value)
    })
    message.success('AI 配置已保存')
  } catch (e) {
    message.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

const runAiTest = async () => {
  if (!inputFilename.value) return
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/ai/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: inputFilename.value })
    })
    result.value = await res.json()
    if (result.value.status === 'success') {
      message.success('AI 提取完成')
    } else {
      message.error(result.value.message || '解析失败')
    }
  } catch (e) {
    message.error('请求失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div class="ai-lab-view">
    <div class="page-header">
      <div>
        <h1>AI 实验室</h1>
        <div class="subtitle">大语言模型解析沙箱</div>
      </div>
      <n-tag type="info" size="large" round ghost>OpenAI Compatible</n-tag>
    </div>

    <n-space vertical size="large">
      <n-alert type="warning" title="全局策略提示" show-icon>
        当前系统已移除自动化流程中的 AI 介入逻辑。AI 引擎目前仅供本实验室<b>手动测试</b>使用，不会参与实际的文件整理或扫描。
      </n-alert>

      <n-card bordered style="background: var(--app-surface-card)">
        <template #header>
          <div class="card-title-box">
            <n-icon style="color: var(--n-primary-color)"><RunIcon /></n-icon>
            <span class="card-title-text">语义提取测试</span>
          </div>
        </template>
        
        <n-space vertical>
          <n-collapse default-expanded-names="config">
            <n-collapse-item title="AI 实验室定位与测试重点" name="mechanism">
              <template #header-extra>
                <n-icon><LabIcon /></n-icon>
              </template>
              <div class="mechanism-box">
                <n-p>
                  <n-text type="info" strong>本实验室是一个独立的语义解析沙箱，用于验证大语言模型 (LLM) 在极端复杂场景下的提取表现。</n-text><br/>
                  <n-text depth="3">当前系统的核心识别流水线已完全回归高性能正则内核，AI 不再自动介入实际整理流程。您可以在此处测试以下极端情况：</n-text>
                </n-p>
                <ul class="mechanism-list">
                  <li>
                    <b>🔍 极端标题提取</b>：测试模型是否能从充满无关广告词、乱码的文件名中准确“拎”出真正的作品名。
                  </li>
                  <li>
                    <b>🧠 复杂集数推断</b>：测试模型对“第12话”、“Total 24 Eps”、“Part.II”等非标描述的理解能力。
                  </li>
                  <li>
                    <b>🧩 语义消除歧义</b>：当文件名中包含多个年份、分辨率数字或罗马数字时，观察 LLM 的逻辑推理是否比正则更准确。
                  </li>
                  <li>
                    <b>📝 Prompt 提示词工程</b>：通过观察返回的 JSON 结构，评估当前选用的模型是否适合处理此类垂直领域的语义任务。
                  </li>
                </ul>
                <n-text depth="3" style="font-size: 12px">
                  * 实验室调用不消耗系统资源，仅依赖您配置的外部模型接口。
                </n-text>
              </div>
            </n-collapse-item>

            <n-collapse-item title="连接配置 (OpenAI / Ollama)" name="config">
              <template #header-extra>
                <n-icon><ConfigIcon /></n-icon>
              </template>
              <n-form label-placement="left" label-width="100" size="small">
                <n-form-item label="Base URL">
                  <n-input v-model:value="aiConfig.openai_base_url" placeholder="http://localhost:11434/v1" />
                </n-form-item>
                <n-form-item label="API Key">
                  <n-input v-model:value="aiConfig.openai_api_key" type="password" show-password-on="click" placeholder="sk-..." />
                </n-form-item>
                <n-form-item label="模型名称">
                  <n-input v-model:value="aiConfig.openai_model" placeholder="qwen2.5:1.5b" />
                </n-form-item>
                <n-form-item>
                  <n-button type="primary" secondary size="small" :loading="saveLoading" @click="saveAiConfig">
                    <template #icon><n-icon><SaveIcon /></n-icon></template>
                    保存配置
                  </n-button>
                </n-form-item>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <div class="tip">在此处测试使用大语言模型直接从文件名提取元数据的效果。</div>
          
            <n-p>
              AI 实验室通过集成大语言模型 (LLM)，对传统正则解析无法处理的复杂、不规范命名进行语义理解和修正。
              目前支持通过 <b>OpenAI 兼容接口</b> 连接任意大模型（如 ChatGPT, DeepSeek, Ollama 等）。
            </n-p>

          <div class="input-row">
            <n-input
              v-model:value="inputFilename"
              type="textarea"
              :autosize="{ minRows: 2 }"
              placeholder="粘贴一个复杂的文件名进行测试..."
            />
            <n-button 
              type="primary" 
              size="large" 
              :loading="loading" 
              @click="runAiTest"
              class="mt-2"
            >
              <template #icon><n-icon><RunIcon /></n-icon></template>
              运行语义提取
            </n-button>
          </div>
        </n-space>
      </n-card>

      <n-grid :cols="12" :x-gap="24">
        <n-gi :span="8">
          <n-card bordered title="解析结果">
            <n-scrollbar style="max-height: 600px">
              <pre v-if="result" class="json-code">{{ JSON.stringify(result, null, 2) }}</pre>
              <n-empty v-else description="等待运行测试..." />
            </n-scrollbar>
          </n-card>
        </n-gi>
        <n-gi :span="4">
          <n-card bordered title="提取到的字段">
            <div v-if="result?.result" class="fields-list">
              <div v-for="(val, key) in result.result" :key="key" class="field-item">
                <span class="key">{{ key }}</span>
                <span class="val">{{ val }}</span>
              </div>
            </div>
            <n-empty v-else description="无数据" />
          </n-card>
        </n-gi>
      </n-grid>
    </n-space>
  </div>
</template>

<style scoped>
.header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; }

.tip { font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }
.json-code { 
  font-family: 'JetBrains Mono', monospace; 
  font-size: 12px; 
  color: var(--n-primary-color); 
  background: var(--app-surface-inner); 
  padding: 12px; 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--n-border-color);
}

.fields-list { display: flex; flex-direction: column; gap: 8px; }
.field-item { 
  display: flex; 
  justify-content: space-between; 
  padding: 8px; 
  background: var(--app-surface-card); 
  border-radius: var(--button-border-radius, 4px); 
  border: 1px solid var(--n-border-color);
}
.field-item .key { color: var(--text-muted); font-size: 12px; font-weight: bold; }
.field-item .val { color: var(--text-secondary); font-size: 13px; font-family: monospace; }

.mt-2 { margin-top: 8px; }

.mechanism-box {
  background: var(--bg-surface);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}
.mechanism-list {
  margin: 8px 0 12px 20px;
  padding: 0;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.8;
}
.mechanism-list b { color: var(--n-primary-color); }
</style>