<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NGrid, NGi, NTag, NEmpty, 
  NPopconfirm, useMessage, NImage, NText, NTooltip, NDivider
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  LiveTvOutlined as TvIcon,
  MovieOutlined as MovieIcon,
  SearchOutlined as SearchIcon,
  HistoryOutlined as HistoryIcon,
  OpenInNewOutlined as ExternalIcon,
  LanguageOutlined as BgmIcon,
  SettingsSuggestOutlined as TemplateIcon,
  FlashOnOutlined as FlashIcon,
  LayersOutlined as LayersIcon,
  AutoAwesomeOutlined as UpgradeIcon
} from '@vicons/material'
import { getButtonStyle } from '../composables/useButtonStyles'
import { pendingSubscription } from '../store/navigationStore'
import SubscriptionEditModal from './SubscriptionEditModal.vue'
import JackettFillModal from './JackettFillModal.vue'
import SubscriptionHistoryModal from './SubscriptionHistoryModal.vue'
import SubscriptionTemplateModal from './SubscriptionTemplateModal.vue'
import BangumiQuickSubscribeModal from './BangumiQuickSubscribeModal.vue'
import PriorityRuleModal from './PriorityRuleModal.vue'

const props = defineProps<{
  clients: any[]
}>()

const message = useMessage()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const subscriptions = ref<any[]>([])
const loading = ref(false)
const showEditModal = ref(false)
const showFillModal = ref(false)
const showHistoryModal = ref(false)
const showTemplateModal = ref(false)
const showPriorityModal = ref(false)
const showQuickSubModal = ref(false)
const currentSub = ref<any>(null)
const isNew = ref(false)
const profileMap = ref<Record<number, any>>({})

const fetchProfiles = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/priority/profiles`)
    if (res.ok) {
      const data = await res.json()
      profileMap.value = data.reduce((acc: any, p: any) => {
        acc[p.id] = p
        return acc
      }, {})
    }
  } catch (e) {}
}

const getUpgradeStatus = (sub: any) => {
  if (!sub.quality_profile_id) return null
  const p = profileMap.value[sub.quality_profile_id]
  if (!p) return null
  return {
    name: p.name,
    allowed: p.upgrade_allowed
  }
}

const fetchSubscriptions = async () => {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/subscriptions`)
    subscriptions.value = await res.json()
  } catch (e) {
    message.error('加载订阅失败')
  } finally {
    loading.value = false
  }
}

const openAdd = () => {
  currentSub.value = null
  isNew.value = true
  showEditModal.value = true
}

const getImg = (path: string) => {
  if (!path) return ''
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
  }
  if (!path.startsWith('http')) {
    return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  }
  return path
}

const openEdit = (sub: any) => {
  currentSub.value = sub
  isNew.value = false
  showEditModal.value = true
}

const goToExternal = (sub: any, type: 'tmdb' | 'bgm') => {
  if (type === 'tmdb') {
    const url = sub.media_type === 'movie' 
      ? `https://www.themoviedb.org/movie/${sub.tmdb_id}`
      : `https://www.themoviedb.org/tv/${sub.tmdb_id}`
    window.open(url, '_blank')
  } else if (type === 'bgm' && sub.bangumi_id) {
    window.open(`https://bgm.tv/subject/${sub.bangumi_id}`, '_blank')
  }
}

const saveSubscription = async (data: any) => {
  try {
    await fetch(`${API_BASE}/api/subscriptions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    message.success('订阅保存成功')
    fetchSubscriptions()
  } catch (e) {
    message.error('保存失败')
  }
}

const deleteSubscription = async (id: number) => {
  try {
    await fetch(`${API_BASE}/api/subscriptions/${id}`, { method: 'DELETE' })
    message.success('订阅已删除')
    fetchSubscriptions()
  } catch (e) {
    message.error('删除失败')
  }
}

const openFill = (sub: any) => {
  currentSub.value = sub
  showFillModal.value = true
}

const openHistory = (sub: any) => {
  currentSub.value = sub
  showHistoryModal.value = true
}

const clearAllSubscriptions = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/subscriptions/clear_all`, { method: 'DELETE' })
    if (res.ok) {
      const data = await res.json()
      message.info(data.message || '已在后台启动清空任务')
      
      // [NEW] 开启进度轮询，直到列表变空
      const pollTimer = setInterval(async () => {
        await fetchSubscriptions()
        if (subscriptions.value.length === 0) {
          clearInterval(pollTimer)
          message.success('所有订阅已清理完毕')
        }
      }, 1500)
      
      // 60秒安全兜底，防止意外无限轮询
      setTimeout(() => clearInterval(pollTimer), 60000)
    }
  } catch (e) {
    message.error('操作失败')
  }
}

onMounted(() => {
  fetchProfiles()
  fetchSubscriptions()
  if (pendingSubscription.value) {
    const data = pendingSubscription.value
    pendingSubscription.value = null // Clear it
    
    if (data.type === 'tmdb') {
      currentSub.value = {
        tmdb_id: String(data.tmdbId),
        media_type: data.mediaType,
        title: data.title,
        year: data.year || '',
        bangumi_id: data.bangumiId ? String(data.bangumiId) : '',
        season: data.season || 1,
        start_episode: 1,
        end_episode: data.totalEpisodes || 0,
        poster_path: data.poster_path || '',
        _search_query: data.title || String(data.tmdbId),
        _auto_search: !data.tmdbId
      }
    } else {
      currentSub.value = {
        title: data.title,
        bangumi_id: data.bangumiId ? String(data.bangumiId) : '',
        _search_query: data.title,
        _auto_search: true
      }
    }
    isNew.value = true
    showEditModal.value = true
  }
})
</script>

<template>
  <div class="subscription-manager">
    <div class="action-bar">
      <n-space>
        <n-popconfirm @positive-click="clearAllSubscriptions" positive-text="确定清空" negative-text="取消">
          <template #trigger>
            <n-button v-bind="getButtonStyle('danger')">
              清空所有订阅
            </n-button>
          </template>
          该操作将彻底移除所有订阅任务，确定要继续吗？
        </n-popconfirm>
        <n-button v-bind="getButtonStyle('warning')" @click="showQuickSubModal = true">
          Bangumi一键订阅
        </n-button>
        <n-button v-bind="getButtonStyle('secondary')" @click="showPriorityModal = true">
          优先级规则
        </n-button>
        <n-button v-bind="getButtonStyle('secondary')" @click="showTemplateModal = true">
          订阅预设管理
        </n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="openAdd">
          添加新订阅
        </n-button>
      </n-space>
    </div>

    <n-grid :x-gap="16" :y-gap="16" cols="2 600:4 1000:6 1600:8" v-if="subscriptions.length > 0">
      <n-gi v-for="sub in subscriptions" :key="sub.id">
        <n-card hoverable class="sub-card" content-style="padding: 0;">
          <div class="card-content">
            <div class="poster-box" @click="openEdit(sub)">
              <n-image 
                v-if="sub.poster_path" 
                :src="getImg(sub.poster_path)" 
                fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
                object-fit="cover"
                style="width: 100%; height: 100%;"
                preview-disabled
              />
              <div class="media-type-tag">
                <n-icon size="14" :component="sub.media_type === 'movie' ? MovieIcon : TvIcon" />
              </div>
              <div class="upgrade-tag" v-if="getUpgradeStatus(sub)">
                <n-tooltip trigger="hover">
                  <template #trigger>
                     <n-icon size="14" :color="getUpgradeStatus(sub)?.allowed ? '#63e2b7' : '#999'">
                       <UpgradeIcon/>
                     </n-icon>
                  </template>
                  策略: {{ getUpgradeStatus(sub)?.name }}<br>
                  洗版: {{ getUpgradeStatus(sub)?.allowed ? '开启' : '关闭' }}
                </n-tooltip>
              </div>
              <div class="status-indicator" :class="{ 'is-enabled': sub.enabled }"></div>
              <div class="card-overlay">
                <n-icon size="24"><EditIcon /></n-icon>
                <span>编辑订阅</span>
              </div>
            </div>
            <div class="info-box" @click="openEdit(sub)">
              <div class="sub-title" :title="sub.title">{{ sub.title }}</div>
              <div class="sub-meta">
                <span class="meta-range" v-if="sub.media_type === 'tv'">
                  S{{ sub.season === 0 ? 'All' : sub.season }} · E{{ sub.start_episode === 0 ? '1' : sub.start_episode }}{{ sub.end_episode > 0 ? '-' + sub.end_episode : '+' }}
                </span>
                <span class="meta-year" v-else>{{ sub.year || 'Movie' }}</span>
              </div>
              <div class="sub-actions">
                <n-space :size="4">
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('icon')" size="tiny" @click.stop="openFill(sub)">
                        <template #icon><n-icon size="14"><SearchIcon/></n-icon></template>
                      </n-button>
                    </template>
                    搜寻补全缺失集数
                  </n-tooltip>
                  
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('icon')" size="tiny" @click.stop="openHistory(sub)">
                        <template #icon><n-icon size="14"><HistoryIcon/></n-icon></template>
                      </n-button>
                    </template>
                    查看推送记录
                  </n-tooltip>

                  <n-divider vertical />

                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('icon')" size="tiny" @click.stop="goToExternal(sub, 'tmdb')" style="padding: 0; overflow: hidden;">
                        <template #icon>
                          <img src="https://www.themoviedb.org/favicon.ico" style="width: 16px; height: 16px; transform: scale(1.2);" />
                        </template>
                      </n-button>
                    </template>
                    在 TMDB 中查看
                  </n-tooltip>

                  <n-tooltip trigger="hover" v-if="sub.bangumi_id">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('icon')" size="tiny" @click.stop="goToExternal(sub, 'bgm')" style="padding: 0; overflow: hidden;">
                        <template #icon>
                          <img src="https://bgm.tv/img/favicon.ico" style="width: 14px; height: 14px; border-radius: 2px;" />
                        </template>
                      </n-button>
                    </template>
                    在 Bangumi 中查看
                  </n-tooltip>
                </n-space>

                <n-space :size="4">
                  <n-button v-bind="getButtonStyle('iconPrimary')" size="tiny" @click.stop="openEdit(sub)">
                     <template #icon><n-icon size="14"><EditIcon/></n-icon></template>
                  </n-button>
                  <n-popconfirm @positive-click="deleteSubscription(sub.id)" positive-text="确定" negative-text="取消">
                    <template #trigger>
                      <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" @click.stop>
                        <template #icon><n-icon size="14"><DeleteIcon/></n-icon></template>
                      </n-button>
                    </template>
                    确定删除？
                  </n-popconfirm>
                </n-space>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>
    </n-grid>
    <div v-else class="empty-state">
      <n-empty description="你还没有添加任何订阅，点击上方按钮开始追剧吧" />
    </div>

    <SubscriptionTemplateModal
      v-model:show="showTemplateModal"
      :clients="clients"
    />

    <PriorityRuleModal
      v-model:show="showPriorityModal"
    />

    <BangumiQuickSubscribeModal
      v-model:show="showQuickSubModal"
      @finish="fetchSubscriptions"
    />

    <SubscriptionEditModal
      v-model:show="showEditModal"
      :sub-data="currentSub"
      :is-new="isNew"
      :clients="clients"
      @save="saveSubscription"
    />

    <JackettFillModal
      v-model:show="showFillModal"
      :sub-id="currentSub?.id"
      :sub-title="currentSub?.title"
      :api-base="API_BASE"
      @finish="fetchSubscriptions"
    />

    <SubscriptionHistoryModal
      v-model:show="showHistoryModal"
      :sub="currentSub"
      :api-base="API_BASE"
    />
  </div>
</template>

<style scoped>
.action-bar { margin-bottom: 24px; display: flex; justify-content: flex-end; }
.sub-card { overflow: hidden; border: 1px solid var(--app-border-light) !important; background: var(--app-surface-card) !important; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); border-radius: var(--card-border-radius, 8px) !important; }
.sub-card:hover { transform: translateY(-6px); box-shadow: var(--shadow-xl); border-color: var(--n-primary-color) !important; }
.card-content { display: flex; flex-direction: column; }
.poster-box { position: relative; width: 100%; aspect-ratio: 2 / 3; background: var(--app-surface-inner); overflow: hidden; border-radius: var(--card-border-radius, 8px); cursor: pointer; }
.poster-box :deep(img) { width: 100%; height: 100%; border-radius: var(--card-border-radius, 8px); transition: transform 0.5s ease; }
.sub-card:hover .poster-box :deep(img) { transform: scale(1.1); }
.card-overlay { position: absolute; inset: 0; background: var(--bg-overlay); display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s ease; color: var(--text-primary); gap: 8px; }
.card-overlay span { font-size: 12px; font-weight: bold; }
.sub-card:hover .card-overlay { opacity: 1; }
.media-type-tag { position: absolute; top: 8px; right: 8px; background: var(--bg-overlay); backdrop-filter: blur(8px); color: var(--text-primary); padding: 4px; border-radius: var(--button-border-radius, 6px); display: flex; align-items: center; z-index: 2; }
.upgrade-tag { position: absolute; top: 8px; right: 40px; background: var(--bg-overlay); backdrop-filter: blur(8px); padding: 4px; border-radius: var(--button-border-radius, 6px); display: flex; align-items: center; z-index: 2; }
.status-indicator { position: absolute; top: 8px; left: 8px; width: 8px; height: 8px; border-radius: 50%; background: var(--n-error-color); box-shadow: 0 0 8px color-mix(in srgb, var(--n-error-color), transparent 50%); z-index: 2; }
.status-indicator.is-enabled { background: var(--n-primary-color); box-shadow: 0 0 8px color-mix(in srgb, var(--n-primary-color), transparent 50%); }
.info-box { padding: 12px; }
.sub-title { font-weight: 700; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; color: var(--n-text-color-1); cursor: pointer; }
.sub-meta { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--n-text-color-3); margin-bottom: 8px; }
.meta-range { color: var(--n-primary-color); font-weight: 600; }
.sub-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--app-border-light); }
.empty-state { padding: 80px 0; }
</style>