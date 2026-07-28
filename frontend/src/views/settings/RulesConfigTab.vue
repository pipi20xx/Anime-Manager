<script setup lang="ts">
/**
 * RulesConfigTab — 识别与订阅规则
 *
 * 包含: 自定义识别词、制作组、渲染词、特权规则（本地/远程双向绑定）
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { configApi } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'RulesConfigTab' })

const { success, error: showError } = useNotification()

const loading = ref(false)
const saving = ref(false)
const syncLoading = ref(false)
const config = reactive<any>({})

/* ========== 本地/远程文本双向绑定 ========== */
function arrayToText(arr: string[] | undefined) {
  return (arr || []).join('\n')
}
function textToArray(val: string) {
  return String(val || '').split('\n').map((s: string) => s.trim()).filter(Boolean)
}

const noiseLocalText = computed({
  get() { return arrayToText(config.custom_noise_words) },
  set(v) { config.custom_noise_words = textToArray(v) }
})
const noiseRemoteText = computed({
  get() { return arrayToText(config.remote_noise_urls) },
  set(v) { config.remote_noise_urls = textToArray(v) }
})

const groupLocalText = computed({
  get() { return arrayToText(config.custom_release_groups) },
  set(v) { config.custom_release_groups = textToArray(v) }
})
const groupRemoteText = computed({
  get() { return arrayToText(config.remote_group_urls) },
  set(v) { config.remote_group_urls = textToArray(v) }
})

const renderLocalText = computed({
  get() { return arrayToText(config.custom_render_words) },
  set(v) { config.custom_render_words = textToArray(v) }
})
const renderRemoteText = computed({
  get() { return arrayToText(config.remote_render_urls) },
  set(v) { config.remote_render_urls = textToArray(v) }
})

const privilegedLocalText = computed({
  get() { return arrayToText(config.custom_privileged_rules) },
  set(v) { config.custom_privileged_rules = textToArray(v) }
})
const privilegedRemoteText = computed({
  get() { return arrayToText(config.remote_privileged_urls) },
  set(v) { config.remote_privileged_urls = textToArray(v) }
})

async function fetchConfig() {
  loading.value = true
  try {
    const data = await configApi.getConfig()
    Object.keys(data).forEach(key => {
      config[key] = data[key]
    })
  } catch (e) {
    showError('获取配置失败')
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  saving.value = true
  try {
    await configApi.saveConfig({ ...config })
    success('配置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function refreshRemoteRules() {
  syncLoading.value = true
  try {
    const data = await configApi.refreshRemoteRules()
    success(data?.message || '同步成功')
    await fetchConfig()
  } catch (e: any) {
    showError(e?.message || '同步失败')
  } finally {
    syncLoading.value = false
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div v-if="loading" class="d-flex justify-center pa-8">
    <v-progress-circular indeterminate color="primary" size="32" />
  </div>

  <div v-else class="rules-config-tab">
    <!-- 工具栏 -->
    <div class="d-flex justify-end mb-4">
      <v-btn color="primary" variant="tonal" size="small" :loading="syncLoading" prepend-icon="mdi-sync" @click="refreshRemoteRules">
        同步远程规则
      </v-btn>
    </div>

    <!-- 自定义识别词 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-text-search-variant</v-icon>
        <span class="text-subtitle-1 font-weight-bold">自定义识别词</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-row>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">可编辑</v-chip>
            </div>
            <v-textarea
              v-model="noiseLocalText"
              placeholder="例如: 10月新番&#10;或者: 藤本树 17-26 => 藤本树 17_26"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">远程订阅</span>
              <v-chip size="x-small" color="info" variant="tonal">仅同步</v-chip>
            </div>
            <v-textarea
              v-model="noiseRemoteText"
              placeholder="http://example.com/rules.txt"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 自定义制作组 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-account-group-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">自定义制作组</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-row>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">可编辑</v-chip>
            </div>
            <v-textarea
              v-model="groupLocalText"
              placeholder="例如: SweetSub&#10;Mikanani"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">远程订阅</span>
              <v-chip size="x-small" color="info" variant="tonal">仅同步</v-chip>
            </div>
            <v-textarea
              v-model="groupRemoteText"
              placeholder="http://example.com/rules.txt"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 自定义渲染词 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-format-text-variant-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">自定义渲染词</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-row>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">可编辑</v-chip>
            </div>
            <v-textarea
              v-model="renderLocalText"
              placeholder="例如: 剧场版 => {[type=movie]}&#10;S2 => {[s=2]}"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">远程订阅</span>
              <v-chip size="x-small" color="info" variant="tonal">仅同步</v-chip>
            </div>
            <v-textarea
              v-model="renderRemoteText"
              placeholder="http://example.com/rules.txt"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 自定义特权规则 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
        <v-icon color="primary" size="20">mdi-shield-crown-outline</v-icon>
        <span class="text-subtitle-1 font-weight-bold">自定义特权规则</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-row>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">本地规则</span>
              <v-chip size="x-small" color="info" variant="tonal">可编辑</v-chip>
            </div>
            <v-textarea
              v-model="privilegedLocalText"
              placeholder="格式: 正则表达式 => {[字段=值;字段=值]}&#10;例如: ^\[([^\]]+)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3]}"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
          <v-col cols="12" md="6">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-body-2 font-weight-medium">远程订阅</span>
              <v-chip size="x-small" color="info" variant="tonal">仅同步</v-chip>
            </div>
            <v-textarea
              v-model="privilegedRemoteText"
              placeholder="http://example.com/rules.txt"
              variant="outlined"
              density="compact"
              rows="8"
              hide-details
              class="font-monospace"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- 保存按钮 -->
    <div class="d-flex justify-end">
      <v-btn color="primary" variant="flat" :loading="saving" @click="saveAll" prepend-icon="mdi-content-save-outline">
        保存全部修改
      </v-btn>
    </div>
  </div>
</template>
