<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { 
  NCard, NSpace, NButton, NIcon, NList, NListItem, NTag, NEmpty, 
  NPopconfirm, useMessage, useDialog, NImage, NText, NDropdown, NDrawer, NDrawerContent
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  LiveTvOutlined as TvIcon,
  MovieOutlined as MovieIcon,
  SearchOutlined as SearchIcon,
  HistoryOutlined as HistoryIcon,
  MoreVertOutlined as MoreIcon,
  MenuOpenOutlined as MenuIcon,
  FlashOnOutlined as FlashIcon,
  LayersOutlined as LayersIcon,
  SettingsSuggestOutlined as TemplateIcon,
  UpgradeOutlined as UpgradeIcon
} from '@vicons/material'
import { pendingSubscription } from '../../store/navigationStore'
import SubscriptionEditModal from './SubscriptionEditModalMobile.vue'
import JackettFillModal from './FeedItemsModalMobile.vue' // Reuse FeedItemsModalMobile for Jackett results if possible or keep original
import SubscriptionHistoryModal from '../SubscriptionHistoryModal.vue'
import SubscriptionTemplateModal from '../SubscriptionTemplateModal.vue'
import BangumiQuickSubscribeModal from '../BangumiQuickSubscribeModal.vue'
import PriorityRuleModal from '../PriorityRuleModal.vue'
import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  clients: any[]
}>()

const message = useMessage()
const dialog = useDialog()
const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

const subscriptions = ref<any[]>([])
const loading = ref(false)
const showEditModal = ref(false)
const showFillModal = ref(false)
const showHistoryModal = ref(false)
const showTemplateModal = ref(false)
const showPriorityModal = ref(false)
const showQuickSubModal = ref(false)
const showActionDrawer = ref(false) // Mobile specific: Drawer for global actions
const currentSub = ref<any>(null)

// Helper to open a modal from the drawer safely without history conflict
const openFromDrawer = (openFn: () => void) => {
  showActionDrawer.value = false
  // Wait for drawer close animation and history.back() to complete
  setTimeout(() => {
    openFn()
  }, 300)
}

const isNew = ref(false)
const profileMap = ref<Record<number, any>>({})

// Apply Back Button support to Modals
useBackClose(showEditModal)
useBackClose(showFillModal)
useBackClose(showHistoryModal)
useBackClose(showTemplateModal)
useBackClose(showPriorityModal)
useBackClose(showQuickSubModal)
useBackClose(showActionDrawer)

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

const clearAllSubscriptions = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/subscriptions/clear_all`, { method: 'DELETE' })
    if (res.ok) {
      const data = await res.json()
      message.info(data.message || '已在后台启动清空任务')
      showActionDrawer.value = false
      const pollTimer = setInterval(async () => {
        await fetchSubscriptions()
        if (subscriptions.value.length === 0) {
          clearInterval(pollTimer)
          message.success('所有订阅已清理完毕')
        }
      }, 1500)
      setTimeout(() => clearInterval(pollTimer), 60000)
    }
  } catch (e) {
    message.error('操作失败')
  }
}

// Item Actions Drawer
const showItemActionDrawer = ref(false)
const currentActionSub = ref<any>(null)
useBackClose(showItemActionDrawer)

const itemActions = [
  { key: 'edit', label: '编辑订阅', icon: EditIcon },
  { key: 'fill', label: '搜索补全', icon: SearchIcon },
  { key: 'history', label: '推送记录', icon: HistoryIcon },
  { key: 'tmdb', label: '打开 TMDB', icon: MovieIcon },
]

const openItemActions = (sub: any) => {
  currentActionSub.value = sub
  showItemActionDrawer.value = true
}

const handleItemAction = (key: string) => {
  const sub = currentActionSub.value
  if (!sub) return
  
  showItemActionDrawer.value = false
  setTimeout(() => {
    if (key === 'edit') { currentSub.value = sub; isNew.value = false; showEditModal.value = true; }
    else if (key === 'fill') { currentSub.value = sub; showFillModal.value = true; }
    else if (key === 'history') { currentSub.value = sub; showHistoryModal.value = true; }
    else if (key === 'delete') { 
      dialog.warning({
        title: '删除确认',
        content: `确定要删除订阅「${sub.title}」吗？`,
        action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
          h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => dialog.destroyAll() }, { default: () => '取消' }),
          h(NButton, { ...getButtonStyle('dialogDanger'), onClick: () => { deleteSubscription(sub.id); dialog.destroyAll() } }, { default: () => '删除' })
        ])
      })
    }
    else if (key === 'tmdb') goToExternal(sub, 'tmdb')
    else if (key === 'bgm') goToExternal(sub, 'bgm')
  }, 300)
}

onMounted(() => {
  fetchProfiles()
  fetchSubscriptions()
  if (pendingSubscription.value) {
    // ... logic for pending subscription (same as desktop) ...
     const data = pendingSubscription.value
    pendingSubscription.value = null 
    
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
  <div class="mobile-sub-manager">
    <!-- Top Toolbar -->
    <div class="mobile-toolbar">
      <div class="toolbar-left">
        <n-text strong>我的订阅 ({{ subscriptions.length }})</n-text>
      </div>
      <div class="toolbar-right">
        <n-button v-bind="getButtonStyle('icon')" size="small" @click="showActionDrawer = true">
          <template #icon><n-icon><MenuIcon/></n-icon></template>
        </n-button>
        <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="openAdd" style="margin-left: 8px;">
          <template #icon><n-icon><AddIcon/></n-icon></template>
        </n-button>
      </div>
    </div>

    <!-- List View -->
    <div class="sub-list" v-if="subscriptions.length > 0">
      <div class="sub-item" v-for="sub in subscriptions" :key="sub.id">
        <div class="sub-poster" @click="handleItemAction('edit', sub)">
           <n-image 
            v-if="sub.poster_path" 
            :src="getImg(sub.poster_path)" 
            fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
            object-fit="cover"
            preview-disabled
          />
          <div class="media-badge" :class="sub.media_type">
            {{ sub.media_type === 'movie' ? '电影' : '剧集' }}
          </div>
        </div>
        
        <div class="sub-info" @click="handleItemAction('edit', sub)">
          <div class="sub-main-row">
            <div class="sub-title">{{ sub.title }}</div>
          </div>
          <div class="sub-details">
            <span v-if="sub.media_type === 'tv'">S{{ sub.season }} · E{{ sub.start_episode }}-{{ sub.end_episode || '∞' }}</span>
            <span v-else>{{ sub.year }}</span>
          </div>
          <div class="sub-status">
             <n-tag size="small" :type="sub.enabled ? 'success' : 'error'" round style="zoom: 0.8">
               {{ sub.enabled ? '监控中' : '已暂停' }}
             </n-tag>
             <n-tag v-if="getUpgradeStatus(sub)?.allowed" size="small" type="info" round style="zoom: 0.8; margin-left: 4px;">
               洗版
             </n-tag>
          </div>
        </div>

        <div class="sub-actions-btn">
          <n-button v-bind="getButtonStyle('icon')" size="small" @click.stop="openItemActions(sub)">
            <template #icon><n-icon><MoreIcon/></n-icon></template>
          </n-button>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <n-empty description="暂无订阅" />
      <n-button type="primary" size="small" @click="openAdd" style="margin-top: 12px">
        添加第一个订阅
      </n-button>
    </div>

    <!-- Global Action Drawer -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" height="340" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content title="更多操作" closable>
        <div class="action-list">
          <div class="action-item" @click="openFromDrawer(() => showQuickSubModal = true)">
            <div class="action-icon"><n-icon size="22"><FlashIcon/></n-icon></div>
            <span class="action-label">Bangumi 一键订阅</span>
          </div>
          <div class="action-item" @click="openFromDrawer(() => showPriorityModal = true)">
            <div class="action-icon"><n-icon size="22"><LayersIcon/></n-icon></div>
            <span class="action-label">优先级规则</span>
          </div>
          <div class="action-item" @click="openFromDrawer(() => showTemplateModal = true)">
            <div class="action-icon"><n-icon size="22"><TemplateIcon/></n-icon></div>
            <span class="action-label">订阅预设管理</span>
          </div>
          <div class="action-item danger" @click="clearAllSubscriptions">
            <div class="action-icon"><n-icon size="22"><DeleteIcon/></n-icon></div>
            <span class="action-label">清空所有订阅</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- Item Action Drawer -->
    <n-drawer v-model:show="showItemActionDrawer" placement="bottom" height="380" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content :title="currentActionSub?.title || '订阅操作'" closable>
        <div class="action-list">
          <div v-for="action in itemActions" :key="action.key" class="action-item" @click="handleItemAction(action.key)">
            <div class="action-icon"><n-icon size="22"><component :is="action.icon" /></n-icon></div>
            <span class="action-label">{{ action.label }}</span>
          </div>
          <div v-if="currentActionSub?.bangumi_id" class="action-item" @click="handleItemAction('bgm')">
            <div class="action-icon"><n-icon size="22"><TvIcon /></n-icon></div>
            <span class="action-label">打开 Bangumi</span>
          </div>
          <div class="action-item danger" @click="handleItemAction('delete')">
            <div class="action-icon"><n-icon size="22"><DeleteIcon /></n-icon></div>
            <span class="action-label">删除订阅</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- Modals (Reused) -->
    <SubscriptionTemplateModal v-model:show="showTemplateModal" :clients="clients" />
    <PriorityRuleModal v-model:show="showPriorityModal" />
    <BangumiQuickSubscribeModal v-model:show="showQuickSubModal" @finish="fetchSubscriptions" />
    <SubscriptionEditModal v-model:show="showEditModal" :sub-data="currentSub" :is-new="isNew" :clients="clients" @save="saveSubscription" />
    <JackettFillModal v-model:show="showFillModal" :sub-id="currentSub?.id" :sub-title="currentSub?.title" :api-base="API_BASE" @finish="fetchSubscriptions" />
    <SubscriptionHistoryModal v-model:show="showHistoryModal" :sub="currentSub" :api-base="API_BASE" />
  </div>
</template>

<style scoped>
.mobile-sub-manager {
  padding-bottom: var(--m-spacing-lg);
}
.mobile-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--m-spacing-xs) var(--m-spacing-md) var(--m-spacing-xs);
}
.sub-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-md);
}
.sub-item {
  display: flex;
  background: var(--app-surface-card);
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  height: 110px;
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  box-shadow: var(--shadow-sm);
}
.sub-item:active {
  transform: scale(0.98);
  box-shadow: var(--shadow-md);
}
.sub-poster {
  width: 78px;
  height: 110px;
  flex-shrink: 0;
  position: relative;
}
.sub-poster :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.media-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 6px;
  border-radius: var(--m-radius-sm);
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
.media-badge.movie { background: linear-gradient(135deg, var(--color-error), #ff6b6b); }
.media-badge.tv { background: linear-gradient(135deg, var(--n-primary-color), #4dabf7); }

.sub-info {
  flex: 1;
  padding: var(--m-spacing-sm) var(--m-spacing-md);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
}
.sub-title {
  font-weight: 600;
  font-size: var(--m-text-md);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--text-primary);
}
.sub-details {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}
.sub-actions-btn {
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-left: 1px solid var(--border-light);
  background: var(--app-surface-inner);
}
.sub-actions-btn :deep(.n-button) {
  opacity: 0.7;
  transition: opacity 0.2s ease;
}
.sub-item:active .sub-actions-btn :deep(.n-button) {
  opacity: 1;
}
.empty-state {
  text-align: center;
  padding: 60px var(--m-spacing-lg);
}
.empty-state :deep(.n-empty__icon) {
  font-size: 64px;
}
.empty-state :deep(.n-empty__description) {
  font-size: var(--m-text-md);
  color: var(--text-secondary);
  margin-top: var(--m-spacing-md);
}

/* 操作列表样式 */
.action-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}

.action-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.action-item:active {
  background: var(--bg-surface-hover);
}

.action-item.danger {
  color: var(--color-error);
}

.action-item.danger .action-icon {
  color: var(--color-error);
}

.action-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  color: var(--text-secondary);
}

.action-item.danger .action-icon {
  background: var(--color-error-bg);
}

.action-label {
  font-size: var(--m-text-md);
  font-weight: 500;
}
</style>
