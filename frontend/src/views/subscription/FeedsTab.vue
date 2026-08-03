<script setup lang="ts">
/**
 * FeedsTab — 订阅源管理
 *
 * 对标旧前端 Feeds Tab:
 * - Feed 卡片列表（含状态标签、URL 展示、编辑/删除）
 * - 订阅源详情弹窗（聚合浏览条目）
 * - Jackett 同步
 * - TMDB 屏蔽管理
 */
import { ref, onMounted } from 'vue'
import { subscriptionApi, clientsApi, api } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import TmdbBlocklistModal from './TmdbBlocklistModal.vue'
import FeedItemsModal from './FeedItemsModal.vue'

defineOptions({ name: 'FeedsTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const feeds = ref<any[]>([])
const loading = ref(false)
const clients = ref<any[]>([])

// Feed 编辑弹窗
const showFeedModal = ref(false)
const isNewFeed = ref(false)
const feedForm = ref<any>({})

// 订阅源详情弹窗
const showItemsModal = ref(false)
const currentFeedForItems = ref<any>(null)

// TMDB 屏蔽列表
const showTmdbBlocklist = ref(false)

async function fetchFeeds() {
  loading.value = true
  try { feeds.value = (await subscriptionApi.getFeeds()) || [] }
  catch { showError('加载订阅源失败') }
  finally { loading.value = false }
}

async function fetchClients() {
  try { clients.value = (await clientsApi.getClients()) || [] } catch { /* */ }
}

// --- Feed CRUD ---
function openAddFeed() {
  isNewFeed.value = true
  feedForm.value = {
    title: '', url: '', enabled: true, for_subscription: true, for_rules: true,
    anime_priority: true, check_emby_exists: false, batch_enhance: false,
    include_keywords: '', exclude_keywords: '',
  }
  showFeedModal.value = true
}

function openEditFeed(feed: any) {
  isNewFeed.value = false
  feedForm.value = { ...feed }
  if (feedForm.value.for_subscription === undefined) feedForm.value.for_subscription = true
  if (feedForm.value.for_rules === undefined) feedForm.value.for_rules = true
  if (feedForm.value.anime_priority === undefined) feedForm.value.anime_priority = true
  showFeedModal.value = true
}

async function handleSaveFeed() {
  try {
    await subscriptionApi.saveFeed({ ...feedForm.value })
    success('Feed 已保存')
    showFeedModal.value = false
    fetchFeeds()
  } catch { showError('保存失败') }
}

async function deleteFeed(feed: any) {
  const ok = await confirm({ title: '确认删除', content: `确定要删除订阅源「${feed.title || feed.url}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try { await subscriptionApi.deleteFeed(feed.id); success('已删除'); fetchFeeds() }
  catch { showError('删除失败') }
}

async function resetFeedHistory(feed: any) {
  const ok = await confirm({ title: '确认重置', content: `重置「${feed.title || feed.url}」的抓取历史后，已记录的条目将被清除，下次轮询时会重新拉取所有条目。确定要重置吗？`, confirmColor: 'warning' })
  if (!ok) return
  try { await subscriptionApi.resetFeedHistory(feed.id); success('历史已重置') }
  catch { showError('重置失败') }
}

function openFeedItems(feed?: any) {
  currentFeedForItems.value = feed || null
  showItemsModal.value = true
}

async function syncJackettFeeds() {
  try {
    const data = await subscriptionApi.syncJackettFeeds()
    if (data?.success) { success(data.message || '同步成功'); fetchFeeds() }
    else showError(data?.message || '同步失败')
  } catch (e: any) { showError(e?.message || '同步失败') }
}

onMounted(() => {
  fetchFeeds()
  fetchClients()
})

defineExpose({ fetchFeeds })
</script>

<template>
  <div>
    <!-- 操作栏 -->
    <div class="d-flex justify-end mb-4 ga-2 flex-wrap">
      <v-btn variant="tonal" size="small" prepend-icon="mdi-eye-outline" color="info" @click="showItemsModal = true">订阅源详情</v-btn>
      <v-btn variant="tonal" size="small" prepend-icon="mdi-database-sync-outline" color="info" @click="syncJackettFeeds">同步 Jackett 源</v-btn>
      <v-btn variant="tonal" size="small" prepend-icon="mdi-shield-off-outline" color="error" @click="showTmdbBlocklist = true">TMDB屏蔽管理</v-btn>
      <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAddFeed">新增订阅源</v-btn>
    </div>

    <v-skeleton-loader v-if="loading" type="card@3" />

    <v-row v-else-if="feeds.length > 0">
      <v-col v-for="feed in feeds" :key="feed.id" cols="12" sm="6" md="4">
        <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEditFeed(feed)">
          <!-- 标题行 -->
          <div class="manage-card__header">
            <div class="manage-card__title">{{ feed.title || '未命名订阅' }}</div>
            <v-chip size="x-small" :color="feed.enabled !== false ? 'success' : 'error'" variant="tonal" class="manage-card__badge">
              {{ feed.enabled !== false ? '监控中' : '已暂停' }}
            </v-chip>
          </div>

          <!-- 信息区 -->
          <div class="manage-card__body">
            <div class="manage-card__info">
              <span class="manage-card__info-label">地址</span>
              <span class="manage-card__info-value" :title="feed.url">{{ feed.url }}</span>
            </div>
            <div class="manage-card__tags">
              <v-chip v-if="feed.for_subscription" size="x-small" variant="tonal" color="info">追剧</v-chip>
              <v-chip v-if="feed.for_rules" size="x-small" variant="tonal" color="info">规则</v-chip>
              <v-chip v-if="feed.anime_priority" size="x-small" variant="tonal" color="info">动漫优先</v-chip>
            </div>
          </div>

          <v-divider />
          <v-card-actions class="manage-card__actions">
            <v-spacer />
            <v-btn size="small" variant="tonal" color="warning" prepend-icon="mdi-restore" @click.stop="resetFeedHistory(feed)">重置</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteFeed(feed)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-rss-off</v-icon>
      <div class="text-h6 font-weight-medium">暂无订阅源</div>
      <div class="text-body-2 text-medium-emphasis mt-2">点击"新增订阅源"开始</div>
    </div>

    <!-- Feed 编辑弹窗 -->
    <v-dialog v-model="showFeedModal" max-width="560" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start>mdi-rss</v-icon>
          {{ isNewFeed ? '添加 RSS 订阅源' : '编辑 RSS 订阅源' }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showFeedModal = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field v-model="feedForm.title" label="订阅名称" placeholder="例如: 蜜柑 - 季度新番" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="feedForm.url" label="RSS 地址" placeholder="支持 Mikan, Nyaa, Jackett 等标准 RSS 链接" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="feedForm.include_keywords" label="前置包含词 (可选)" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="feedForm.exclude_keywords" label="前置排除词 (可选)" variant="outlined" density="compact" class="mb-4" />

          <div class="text-subtitle-2 font-weight-medium mb-3">自动监控设置</div>
          <div class="d-flex flex-column ga-3">
            <div class="switch-row">
              <v-switch v-model="feedForm.enabled" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">全局监控</div>
                <div class="switch-desc">启用后定时轮询此 RSS 源，拉取最新资源条目</div>
              </div>
            </div>
            <div class="switch-row">
              <v-switch v-model="feedForm.for_subscription" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">追剧订阅</div>
                <div class="switch-desc">将抓取到的条目与已追剧的番剧进行匹配，自动下载新集</div>
              </div>
            </div>
            <div class="switch-row">
              <v-switch v-model="feedForm.for_rules" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">下载规则</div>
                <div class="switch-desc">将抓取到的条目与自定义下载规则匹配，命中后自动添加下载</div>
              </div>
            </div>
            <div class="switch-row">
              <v-switch v-model="feedForm.anime_priority" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">动漫优先</div>
                <div class="switch-desc">识别时优先使用动漫专用策略，提高番剧识别准确率</div>
              </div>
            </div>
            <div class="switch-row">
              <v-switch v-model="feedForm.check_emby_exists" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">Emby 检查</div>
                <div class="switch-desc">检测 Emby 媒体库是否已存在该资源，存在则跳过下载</div>
              </div>
            </div>
            <div class="switch-row">
              <v-switch v-model="feedForm.batch_enhance" color="primary" density="compact" hide-details />
              <div>
                <div class="switch-label">副标题合集提取</div>
                <div class="switch-desc">从 RSS 条目副标题中提取合集信息，增强多集识别能力</div>
              </div>
            </div>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showFeedModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSaveFeed">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 订阅源详情弹窗 -->
    <FeedItemsModal v-model:show="showItemsModal" :feeds="feeds" />

    <!-- TMDB 屏蔽列表弹窗 -->
    <TmdbBlocklistModal v-model:show="showTmdbBlocklist" />
  </div>
</template>

<!-- scoped 样式已迁移至 global.css .hover-lift -->
