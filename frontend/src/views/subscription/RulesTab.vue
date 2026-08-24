<script setup lang="ts">
/**
 * RulesTab — 下载规则
 *
 * 对标旧前端 Rules Tab:
 * - 规则卡片（含关键词、排除词、匹配模式、下载器、保存路径）
 * - 复制规则
 * - 下载记录弹窗
 * - 规则预览
 */
import { ref, onMounted } from 'vue'
import { subscriptionApi, clientsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import DownloadHistoryModal from './DownloadHistoryModal.vue'

defineOptions({ name: 'RulesTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const rules = ref<any[]>([])
const feeds = ref<any[]>([])
const clients = ref<any[]>([])
const loading = ref(false)

// 规则编辑弹窗
const showRuleModal = ref(false)
const isNewRule = ref(false)
const ruleForm = ref<any>({})
const ruleSelectedFeedIds = ref<string[]>([])

// 规则预览弹窗
const showPreviewModal = ref(false)
const previewRuleData = ref<any>(null)
const previewItems = ref<any[]>([])
const previewLoading = ref(false)

// 下载记录弹窗
const showHistoryModal = ref(false)

const clientNameMap = ref<Record<string, string>>({})
const feedNameMap = ref<Record<string, string>>({})

async function fetchRules() {
  loading.value = true
  try {
    const [ruleData, feedData, clientData] = await Promise.all([
      subscriptionApi.getRules(),
      subscriptionApi.getFeeds(),
      clientsApi.getClients(),
    ])
    rules.value = ruleData || []
    feeds.value = feedData || []
    clients.value = clientData || []
    const cMap: Record<string, string> = {}
    clients.value.forEach(c => { cMap[c.id] = c.name })
    clientNameMap.value = cMap
    const fMap: Record<string, string> = {}
    feeds.value.forEach((f: any) => { fMap[String(f.id)] = f.title || f.url || `Feed #${f.id}` })
    feedNameMap.value = fMap
  } catch { showError('加载数据失败') }
  finally { loading.value = false }
}

/** 仅刷新订阅源列表，用于弹窗打开时确保数据最新 */
async function refreshFeeds() {
  try {
    const feedData = await subscriptionApi.getFeeds()
    feeds.value = feedData || []
    const fMap: Record<string, string> = {}
    feeds.value.forEach((f: any) => { fMap[String(f.id)] = f.title || f.url || `Feed #${f.id}` })
    feedNameMap.value = fMap
  } catch { /* 静默失败，保留旧数据 */ }
}

function getTargetFeedNames(targetFeeds: string | undefined | null): string {
  if (!targetFeeds) return '全部源'
  const ids = String(targetFeeds).split(',').filter(Boolean)
  if (ids.length === 0) return '全部源'
  const names = ids.map(id => feedNameMap.value[id] || `#${id}`)
  return names.join(', ')
}

// --- CRUD ---
async function openAddRule() {
  await refreshFeeds()
  isNewRule.value = true
  ruleForm.value = {
    name: '', enabled: true, must_contain: '', must_not_contain: '',
    use_regex: false, target_feeds: '', target_client_id: '', save_path: '',
    category: '', tags: '', paused: false,
  }
  ruleSelectedFeedIds.value = []
  showRuleModal.value = true
}

async function openEditRule(rule: any) {
  await refreshFeeds()
  isNewRule.value = false
  ruleForm.value = { ...rule }
  if (rule.target_feeds) {
    ruleSelectedFeedIds.value = String(rule.target_feeds).split(',').filter(Boolean)
  } else {
    ruleSelectedFeedIds.value = []
  }
  showRuleModal.value = true
}

async function handleSaveRule() {
  const payload = { ...ruleForm.value }
  payload.target_feeds = ruleSelectedFeedIds.value.join(',')
  try {
    await subscriptionApi.saveRule(payload)
    success('规则已保存')
    showRuleModal.value = false
    fetchRules()
  } catch { showError('保存失败') }
}

async function duplicateRule(rule: any) {
  const newRule = { ...rule }
  delete newRule.id
  newRule.name = (newRule.name || '未命名') + ' (副本)'
  try {
    await subscriptionApi.saveRule(newRule)
    success('规则复制成功')
    fetchRules()
  } catch { showError('复制失败') }
}

async function deleteRule(rule: any) {
  const ok = await confirm({ title: '确认删除', content: `确定要删除规则「${rule.name}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try { await subscriptionApi.deleteRule(rule.id); success('规则已删除'); fetchRules() }
  catch { showError('删除失败') }
}

async function previewRule(rule: any) {
  previewRuleData.value = rule
  showPreviewModal.value = true
  previewLoading.value = true
  try {
    const data = await subscriptionApi.previewRule(rule)
    previewItems.value = data?.items || data || []
  } catch { previewItems.value = [] }
  finally { previewLoading.value = false }
}

onMounted(fetchRules)

defineExpose({ fetchRules })
</script>

<template>
  <div>
    <!-- 操作栏 -->
    <div class="d-flex justify-end mb-4 ga-2 flex-wrap">
      <v-btn variant="tonal" size="small" color="info" prepend-icon="mdi-history" @click="showHistoryModal = true">下载记录</v-btn>
      <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-plus" @click="openAddRule">创建新规则</v-btn>
    </div>

    <v-skeleton-loader v-if="loading" type="card@3" />

    <v-row v-else-if="rules.length > 0">
      <v-col v-for="rule in rules" :key="rule.id" cols="12" sm="6" md="4">
        <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEditRule(rule)">
          <!-- 标题行 -->
          <div class="manage-card__header">
            <div class="manage-card__title">{{ rule.name || '未命名规则' }}</div>
            <v-chip size="x-small" :color="rule.enabled !== false ? 'success' : 'error'" variant="tonal" class="manage-card__badge">
              {{ rule.enabled !== false ? '生效中' : '未启用' }}
            </v-chip>
          </div>

          <!-- 信息区 -->
          <div class="manage-card__body">
            <div class="manage-card__info">
              <span class="manage-card__info-label">包含</span>
              <span class="manage-card__info-value" :title="rule.must_contain">{{ rule.must_contain || '无' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">排除</span>
              <span class="manage-card__info-value" :title="rule.must_not_contain">{{ rule.must_not_contain || '无' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">模式</span>
              <span class="manage-card__info-value">{{ rule.use_regex ? '正则' : '普通' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">下载器</span>
              <span class="manage-card__info-value">{{ clientNameMap[rule.target_client_id] || '默认' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">路径</span>
              <span class="manage-card__info-value" :title="rule.save_path">{{ rule.save_path || '默认' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">作用范围</span>
              <span class="manage-card__info-value" :title="getTargetFeedNames(rule.target_feeds)">{{ getTargetFeedNames(rule.target_feeds) }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">分类</span>
              <span class="manage-card__info-value" :title="rule.category">{{ rule.category || '无' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">标签</span>
              <span class="manage-card__info-value" :title="rule.tags">{{ rule.tags || '无' }}</span>
            </div>
            <div class="manage-card__info">
              <span class="manage-card__info-label">下载方式</span>
              <span class="manage-card__info-value">{{ rule.paused ? '添加后暂停' : '自动开始' }}</span>
            </div>
          </div>

          <v-divider />
          <v-card-actions class="manage-card__actions">
            <v-spacer />
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-eye-outline" @click.stop="previewRule(rule)">预览</v-btn>
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-content-copy" @click.stop="duplicateRule(rule)">复制</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteRule(rule)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-filter-outline</v-icon>
      <div class="text-h6 font-weight-medium">暂无规则</div>
      <div class="text-body-2 text-medium-emphasis mt-2">点击"创建规则"开始</div>
    </div>

    <!-- 规则编辑弹窗 -->
    <v-dialog v-model="showRuleModal" max-width="640" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start>mdi-filter-outline</v-icon>
          {{ isNewRule ? '创建匹配规则' : '编辑匹配规则' }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showRuleModal = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field v-model="ruleForm.name" label="规则名称" variant="outlined" density="compact" class="mb-3" />
          <div class="d-flex align-center ga-3 mb-3">
            <span class="text-body-2 font-weight-medium">匹配模式:</span>
            <v-switch v-model="ruleForm.use_regex" color="primary" density="compact" hide-details :label="ruleForm.use_regex ? '正则表达式' : '普通关键词'" />
          </div>
          <v-textarea v-model="ruleForm.must_contain" label="包含关键词" placeholder="普通模式: 空格=且, |=或" variant="outlined" density="compact" rows="2" auto-grow class="mb-3" />
          <v-text-field v-model="ruleForm.must_not_contain" label="排除关键词" placeholder="用 | 分隔" variant="outlined" density="compact" class="mb-3" />
          <v-select v-model="ruleSelectedFeedIds" label="作用范围 (留空则监控所有源)" :items="feeds.map(f => ({ title: f.title || f.url, value: String(f.id) }))" multiple chips clearable variant="outlined" density="compact" class="mb-3" />
          <v-select v-model="ruleForm.target_client_id" label="指定下载器" :items="clients.map(c => ({ title: c.name, value: c.id }))" clearable variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="ruleForm.save_path" label="保存路径" variant="outlined" density="compact" class="mb-3" />
          <v-row density="compact">
            <v-col cols="6"><v-text-field v-model="ruleForm.category" label="分类" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="ruleForm.tags" label="标签" variant="outlined" density="compact" /></v-col>
          </v-row>
          <v-switch v-model="ruleForm.paused" color="primary" density="compact" hide-details class="mt-2" :label="ruleForm.paused ? '添加后暂停' : '自动开始'" />
          <v-switch v-model="ruleForm.enabled" color="primary" density="compact" hide-details class="mt-2" label="启用规则" />
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showRuleModal = false">取消</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="handleSaveRule">保存规则</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 规则预览弹窗 -->
    <v-dialog v-model="showPreviewModal" max-width="800" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-eye-outline</v-icon>
          规则预览 — {{ previewRuleData?.name }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showPreviewModal = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-skeleton-loader v-if="previewLoading" type="list-item@5" />
          <template v-else-if="previewItems.length > 0">
            <v-card v-for="item in previewItems" :key="item.guid || item.link || item.title" class="glass-card hover-lift pa-3 mb-2" variant="flat">
              <div class="text-body-2 font-weight-medium">{{ item.raw_title || item.title }}</div>
              <div v-if="item.description" class="text-caption text-medium-emphasis mt-1 text-truncate">{{ item.description }}</div>
            </v-card>
          </template>
          <div v-else class="text-center pa-6 text-medium-emphasis">未匹配到任何条目</div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showPreviewModal = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 下载记录弹窗 -->
    <DownloadHistoryModal v-model:show="showHistoryModal" :feeds="feeds" />
  </div>
</template>

<!-- scoped 样式已迁移至 global.css .hover-lift / .kv-row / .kv-label / .kv-value -->
