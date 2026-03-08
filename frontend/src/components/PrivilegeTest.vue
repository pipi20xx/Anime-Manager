<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { 
  NCard, NInput, NButton, NSpace, NIcon, NDivider, 
  NAlert, NInputGroup, useMessage, NTag, NInputNumber,
  NList, NListItem, NThing, NScrollbar, NTooltip
} from 'naive-ui'
import {
  SecurityOutlined as ShieldIcon,
  BugReportOutlined as BugIcon,
  RefreshOutlined as RefreshIcon,
  InputOutlined as LoadIcon
} from '@vicons/material'

const props = defineProps<{
  apiBase: string
}>()

const message = useMessage()
const loading = ref(false)
const filename = ref('')
const result = ref<any>(null)

// 调试器状态
const customRegex = ref('')
const groupIndex = ref(1)
const builtInRules = ref<any[]>([])

const examples = [
  "[LoliHouse] Mushoku Tensei II - 01 (WebRip 1920x1080 HEVC AAC).mkv",
  "[NC-Raws & LoliHouse] Sousou no Frieren - 12 (B-Global 1920x1080 HEVC AAC).mkv",
  "[SweetSub] Dungeon Meshi [01][HEVC][10bit].mkv",
  "[SweetSub] Shangri-La Frontier - 05 [WebRip 1080p HEVC AAC].mp4"
]

const fetchRules = async () => {
  try {
    const res = await fetch(`${props.apiBase}/api/privilege/rules`)
    builtInRules.value = await res.json()
  } catch (e) {
    message.error("获取内置规则失败")
  }
}

const loadRule = (rule: any) => {
  customRegex.value = rule.pattern
  groupIndex.value = rule.group_index
  message.success(`已载入: ${rule.description}`)
}

const handleTest = async () => {
  if (!filename.value) {
    message.warning("请输入测试文件名")
    return
  }
  if (!customRegex.value) {
    message.warning("请输入正则表达式")
    return
  }

  loading.value = true
  try {
    const res = await fetch(`${props.apiBase}/api/privilege/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        filename: filename.value,
        custom_regex: customRegex.value,
        group_index: groupIndex.value
      })
    })
    result.value = await res.json()
    if (result.value.hit) {
      message.success("匹配成功")
    } else if (result.value.error) {
      message.error("正则语法错误")
    } else {
      message.info("未命中")
    }
  } catch (e: any) {
    message.error("调试接口失败")
  } finally {
    loading.value = false
  }
}

const useExample = (ex: string) => {
  filename.value = ex
}

onMounted(fetchRules)
</script>

<template>
  <div class="privilege-lab">
    <n-grid x-gap="12" cols="1 1000:2">
      <n-gi>
        <n-space vertical size="large">
          <!-- 1. 调试台 -->
          <n-card title="正则调试台" bordered segmented>
            <template #header-extra>
              <n-tag type="primary" size="small" round>隔离调试模式</n-tag>
            </template>
            
            <n-space vertical size="medium">
              <div>
                <div class="label-mini">测试对象 (文件名)</div>
                <n-input 
                  v-model:value="filename" 
                  type="textarea"
                  :autosize="{ minRows: 2, maxRows: 3 }"
                  placeholder="粘贴文件名..."
                  style="font-family: monospace;"
                />
                <div class="examples-row">
                  <n-button 
                    v-for="ex in examples" 
                    :key="ex" 
                    quaternary 
                    size="tiny" 
                    @click="useExample(ex)"
                  >
                    {{ ex.split(']')[0] + ']' }}
                  </n-button>
                </div>
              </div>

              <n-divider dashed style="margin: 8px 0" />

              <div>
                <div class="label-mini">正则表达式 (Regex)</div>
                <n-input 
                  v-model:value="customRegex" 
                  placeholder="输入正则..."
                  style="font-family: monospace;"
                >
                  <template #prefix><n-icon :component="BugIcon" /></template>
                </n-input>
              </div>

              <n-space align="center" justify="space-between">
                <n-space align="center">
                  <span class="label-mini">捕获组索引:</span>
                  <n-input-number v-model:value="groupIndex" :min="1" :max="10" size="small" style="width: 80px" />
                </n-space>
                <n-button type="primary" @click="handleTest" :loading="loading" style="padding: 0 32px">
                  运行测试
                </n-button>
              </n-space>
            </n-space>

            <div v-if="result" class="result-area">
              <div v-if="result.hit" class="hit-card">
                <div class="hit-header">
                  <div class="hit-val">E{{ result.episode }}</div>
                  <div class="hit-status">MATCHED</div>
                </div>
                <div class="hit-logs">
                  <div v-if="result.match_detail">
                    <div style="color: var(--text-secondary); margin-bottom: 4px;">捕获组细节:</div>
                    <div v-for="(g, i) in result.match_detail.groups" :key="i" class="log-line">
                      Group[{{ i+1 }}]: <span style="color: var(--n-primary-color)">{{ g }}</span>
                    </div>
                  </div>
                  <div v-else v-for="(log, idx) in result.logs" :key="idx" class="log-line">{{ log }}</div>
                </div>
              </div>

              <div v-else class="miss-card" :style="result.error ? 'border-color: var(--color-error); background: var(--color-error-bg)' : ''">
                <div class="miss-header" :style="result.error ? 'color: var(--color-error)' : ''">
                  {{ result.error ? '正则语法错误' : '未匹配 (MISS)' }}
                </div>
                <div class="miss-desc">
                  {{ result.error ? result.logs[0] : '该正则未能在测试文件名中提取到有效的集数。' }}
                </div>
              </div>
            </div>
          </n-card>

          <n-alert type="info" size="small" :show-icon="false">
             <b>提示</b>: 通常集数位于正则的第一个括号 <code>(\d+)</code> 中，此时索引填 1。
          </n-alert>
        </n-space>
      </n-gi>

      <n-gi>
        <!-- 2. 内置规则库 -->
        <n-card title="内置规则参考" bordered segmented>
          <n-scrollbar style="max-height: 520px">
            <n-list hoverable clickable>
              <n-list-item v-for="(rule, idx) in builtInRules" :key="idx">
                <n-thing :title="rule.description">
                  <template #description>
                    <code class="rule-code">{{ rule.pattern }}</code>
                  </template>
                  <template #header-extra>
                    <n-button size="tiny" secondary type="primary" @click="loadRule(rule)">
                      <template #icon><n-icon :component="LoadIcon" /></template>
                      载入调试
                    </n-button>
                  </template>
                  <div style="font-size: 11px; opacity: 0.6; margin-top: 4px;">
                    目标捕获组: Group[{{ rule.group_index }}]
                  </div>
                </n-thing>
              </n-list-item>
            </n-list>
          </n-scrollbar>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<style scoped>
.label-mini {
  font-size: 11px;
  font-weight: bold;
  color: var(--n-text-color-3);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.examples-row {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.rule-code {
  display: block;
  margin-top: 4px;
  padding: 4px 8px;
  background: var(--app-surface-inner);
  color: var(--n-primary-color);
  font-size: 12px;
  word-break: break-all;
}

.result-area {
  margin-top: 16px;
  animation: fadeIn 0.3s ease;
}

.hit-card {
  padding: 12px;
  border-radius: 8px;
  background: var(--color-success-bg);
  border: 1px solid var(--color-success);
}
.hit-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}
.hit-val {
  font-size: 28px;
  font-weight: 900;
  color: var(--color-success);
  line-height: 1;
}
.hit-status {
  font-size: 11px;
  font-weight: bold;
  color: var(--color-success);
  opacity: 0.7;
}
.hit-logs {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-muted);
  background: var(--app-surface-inner);
  padding: 8px;
  border-radius: 4px;
}
.log-line {
  line-height: 1.5;
}

.miss-card {
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
}
.miss-header {
  font-size: 16px;
  font-weight: bold;
  color: var(--n-text-color-3);
}
.miss-desc {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.6;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
