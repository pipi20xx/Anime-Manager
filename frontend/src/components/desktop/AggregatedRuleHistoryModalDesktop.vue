<script setup lang="ts">
import { ref, watch, computed, nextTick, onBeforeUnmount } from 'vue'
import AppGlassModal from '../AppGlassModal.vue'
import {
  NTag, NButton, NSpin, NEmpty, NDropdown
} from 'naive-ui'
import { useBackDialog } from '../../composables/useBackDialog'
import { useAggregatedRuleHistory } from '../../composables/modals/useAggregatedRuleHistory'
import { getButtonStyle } from '../../composables/useButtonStyles'
import AppSearchField from '../AppSearchField.vue'
import AppSelectField from '../AppSelectField.vue'

const dialog = useBackDialog()

const props = defineProps<{
  show: boolean
  rules: any[]
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  items,
  total,
  offset,
  hasMore,
  clientOptions,
  selectedRuleIds,
  keyword,
  fetchItems,
  applyFilter,
  handleDownload,
  handleDelete
} = useAggregatedRuleHistory(props)

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

// 规则选项：使用规则名称作为标签
const ruleOptions = computed(() => {
  return (props.rules || []).map(r => ({ label: r.name, value: r.id }))
})

// 下载器下拉选项
const clientDropdownOptions = computed(() => {
  return clientOptions.value.map(c => ({ label: c.label, key: c.value }))
})

const cleanDescription = (desc: string | null | undefined): string | null => {
  if (!desc) return null
  if (!desc.includes('<') && !desc.includes('>')) return desc
  let clean = desc.replace(/<[^>]+>/g, '')
  clean = clean.replace(/\s+/g, ' ').trim()
  return clean || null
}

const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const handleDeleteWithConfirm = (item: any) => {
  dialog.warning({
    title: '确认清除',
    content: '确认清除该条下载记录吗？',
    positiveText: '确认清除',
    negativeText: '取消',
    onPositiveClick: () => handleDelete(item)
  })
}

// IntersectionObserver：底部哨兵进入视口时自动加载下一页
const setupObserver = () => {
  cleanupObserver()
  nextTick(() => {
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading.value && hasMore.value) {
          fetchItems(true)
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
  })
}

const cleanupObserver = () => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchItems(false).then(() => setupObserver())
  } else {
    cleanupObserver()
  }
})

// 列表变化后重新挂载 observer（确保新哨兵被监听）
watch(() => items.value.length, () => {
  if (props.show && hasMore.value) {
    setupObserver()
  }
})

onBeforeUnmount(cleanupObserver)
</script>

<template>
  <AppGlassModal
    appearance-key="aggregated-rule-history-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 1400px;"
    title="下载记录"
  >
    <!-- 顶部工具栏：搜索 + 筛选 + 操作按钮 -->
    <div class="toolbar">
      <div class="filter-bar">
        <AppSearchField
          :value="keyword"
          placeholder="搜索资源标题或描述..."
          :loading="loading"
          class="filter-item"
          @update:value="val => keyword = val"
          @search="applyFilter"
        />
        <AppSelectField
          :value="selectedRuleIds"
          label="筛选规则"
          placeholder="筛选规则（可多选）"
          :options="ruleOptions"
          multiple
          filterable
          clearable
          :max-tag-count="'responsive'"
          class="filter-item"
          @update:value="val => { selectedRuleIds = val; applyFilter() }"
        />
      </div>
      <div class="action-bar">
        <span class="total-text">共 {{ total }} 条</span>
      </div>
    </div>

    <!-- 卡片列表（自然撑开，走浏览器滚动条） -->
    <div v-if="items.length > 0" class="cards-list">
      <div
        v-for="(item, index) in items"
        :key="item.guid"
        class="rule-card-item"
      >
        <!-- 左侧主内容 -->
        <div class="card-main">
          <div class="card-top-row">
            <div class="card-tags-left">
              <n-tag size="small" round :bordered="false" style="color: #fff; background: #6d4c41; border-radius: 12px;">
                {{ item.rule_name || '-' }}
              </n-tag>
              <n-tag
                size="small"
                round
                :bordered="false"
                :style="item.state === 'Success'
                  ? { color: '#fff', backgroundColor: '#2e7d32', borderRadius: '12px' }
                  : item.state === 'EmbyExists'
                    ? { color: '#fff', backgroundColor: '#0288d1', borderRadius: '12px' }
                    : item.state === 'TmdbBlocked'
                      ? { color: '#fff', backgroundColor: '#6b21a8', borderRadius: '12px' }
                      : { color: '#fff', backgroundColor: '#c62828', borderRadius: '12px' }"
              >
                {{ item.state === 'Success' ? '成功' : item.state === 'EmbyExists' ? '已存在' : item.state === 'TmdbBlocked' ? 'TMDB屏蔽' : '失败' }}
              </n-tag>
            </div>
            <span class="card-index">#{{ index + 1 }}</span>
          </div>

          <div class="card-title">{{ item.title }}</div>

          <div v-if="cleanDescription(item.description)" class="card-desc">
            {{ cleanDescription(item.description) }}
          </div>

          <div class="card-tags">
            <n-tag v-if="item.fail_reason" size="small" round :bordered="false" style="color: #fff; background: #c62828; border-radius: 12px;">
              {{ item.fail_reason }}
            </n-tag>
            <n-tag v-if="item.download_client_id" size="small" round :bordered="false" style="color: #fff; background: #0d47a1; border-radius: 12px;">
              {{ item.download_client_id }}
            </n-tag>
          </div>
        </div>

        <!-- 右侧操作区 -->
        <div class="card-aside">
          <div class="card-time">{{ formatDateTime(item.created_at) }}</div>
          <div class="card-actions">
            <n-button v-bind="getButtonStyle('text')" size="small" style="color: var(--n-error-color);" @click="handleDeleteWithConfirm(item)">
              清除下载记录
            </n-button>
            <n-dropdown
              trigger="click"
              placement="bottom-end"
              :options="clientDropdownOptions"
              :disabled="clientOptions.length === 0 || !item.link"
              @select="(key: string) => handleDownload(item, key)"
            >
              <n-button
                v-bind="getButtonStyle('secondary')"
                size="small"
                :disabled="clientOptions.length === 0 || !item.link"
              >
                {{ !item.link ? '无链接' : (clientOptions.length === 0 ? '无下载器' : '手动下载') }}
              </n-button>
            </n-dropdown>
          </div>
        </div>
      </div>

      <!-- 底部哨兵 + 加载状态 -->
      <div ref="sentinelRef" class="sentinel">
        <div v-if="loading && offset > 0" class="loading-more">
          <n-spin size="small" />
          <span>加载中...</span>
        </div>
        <div v-else-if="!hasMore" class="no-more">
          已全部加载
        </div>
      </div>
    </div>

    <div v-else-if="loading" class="empty-state">
      <n-spin />
    </div>
    <div v-else class="empty-state">
      <n-empty description="暂无数据" />
    </div>
  </AppGlassModal>
</template>

<style scoped>
/* 顶部工具栏 */
.toolbar {
  margin-bottom: 12px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
  margin-bottom: 8px;
}
.filter-item {
  flex: 1;
}
.filter-item :deep(.app-search-field),
.filter-item :deep(.app-search-field__box) {
  height: 100%;
}

.action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.total-text {
  font-size: 12px;
  color: var(--text-muted);
  margin-right: auto;
}

/* 卡片列表 */
.cards-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 单张卡片 */
.rule-card-item {
  display: flex;
  gap: 16px;
  padding: 14px 16px;
  border-radius: var(--card-border-radius, 12px);
  background: var(--app-surface-card-mixed);
  border: var(--app-card-border-width, 1px) var(--app-card-border-style, solid) var(--app-card-border-color, var(--app-border-light));
  transition: all 0.2s ease;
}

.rule-card-item:hover {
  border-color: var(--n-primary-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

/* 左侧主内容 */
.card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-tags-left {
  display: flex;
  gap: 6px;
  align-items: center;
  min-width: 0;
  overflow: hidden;
  flex: 1;
}

.card-index {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  flex-shrink: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
}

.card-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding-right: 48px;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

/* 右侧操作区 */
.card-aside {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  min-width: 180px;
}

.card-time {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* 底部哨兵 */
.sentinel {
  min-height: 1px;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.no-more {
  text-align: center;
  padding: 16px 0;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-state {
  padding: 80px 0;
  text-align: center;
}
</style>
