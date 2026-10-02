<script setup lang="ts">
/**
 * SeasonalTab — 季度番剧表
 *
 * 功能:
 * - 按年份/季度筛选番剧
 * - 卡片网格展示
 * - 支持一键订阅
 */
import { ref, computed, onMounted, watch } from 'vue'
import { bangumiApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'SeasonalTab' })

const { error: showError } = useNotification()
const { confirm } = useConfirm()
const navStore = useNavigationStore()

type Season = 'winter' | 'spring' | 'summer' | 'fall'
const SEASON_CN: Record<Season, string> = { winter: '冬', spring: '春', summer: '夏', fall: '秋' }
const SEASONS: Season[] = ['winter', 'spring', 'summer', 'fall']

const SEASON_KEY = 'explore:seasonal:selection'

const now = new Date()
const currentYear = now.getFullYear()
const currentMonth = now.getMonth() + 1
const currentSeason: Season = SEASONS[Math.floor((currentMonth - 1) / 3)]

// 从 localStorage 恢复上次选择，无则用当前季度
const savedSel = (() => {
  try { return JSON.parse(localStorage.getItem(SEASON_KEY) || '') } catch { return null }
})()
const selectedYear = ref(savedSel?.year ?? currentYear)
const selectedSeason = ref<Season>(savedSel?.season ?? currentSeason)
const items = ref<any[]>([])
const loading = ref(false)
const count = ref(0)

// 用户标记（已整理等），bgm_id -> status
const organizedIds = ref<Set<number>>(new Set())
const HIDE_KEY = 'explore:seasonal:hideOrganized'
const hideOrganized = ref(localStorage.getItem(HIDE_KEY) === '1')

// 展示列表：按需隐藏已整理条目
const displayedItems = computed(() =>
  hideOrganized.value ? items.value.filter(i => !organizedIds.value.has(i.id)) : items.value
)
// 未整理数量（工具栏提示用）
const unorganizedCount = computed(() =>
  items.value.filter(i => !organizedIds.value.has(i.id)).length
)

function onToggleHide(v: boolean) {
  localStorage.setItem(HIDE_KEY, v ? '1' : '0')
}

const yearOptions = computed(() => {
  const years = []
  for (let y = currentYear + 1; y >= currentYear - 5; y--) {
    years.push(y)
  }
  return years
})

function goToPrevSeason() {
  if (selectedSeason.value === 'winter') {
    selectedYear.value--
    selectedSeason.value = 'fall'
  } else {
    selectedSeason.value = SEASONS[SEASONS.indexOf(selectedSeason.value) - 1]
  }
  fetchData()
}

function goToNextSeason() {
  if (selectedSeason.value === 'fall') {
    selectedYear.value++
    selectedSeason.value = 'winter'
  } else {
    selectedSeason.value = SEASONS[SEASONS.indexOf(selectedSeason.value) + 1]
  }
  fetchData()
}

function goToCurrentSeason() {
  selectedYear.value = currentYear
  selectedSeason.value = currentSeason
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    // 季度数据和标记列表并行加载
    const [res, marksRes] = await Promise.all([
      bangumiApi.getSeasonal({
        year: selectedYear.value,
        season: selectedSeason.value,
      }),
      bangumiApi.getMarks().catch(() => null),
    ])
    // 后端返回 { status, data: [...], count } 结构
    items.value = res?.data || []
    count.value = res?.count || items.value.length
    if (marksRes?.success && Array.isArray(marksRes.data)) {
      organizedIds.value = new Set(
        marksRes.data.filter((m: any) => m.status === 'organized').map((m: any) => m.bgm_id)
      )
    }
  } catch (e) {
    showError('加载季度番剧失败')
  } finally {
    loading.value = false
  }
}

async function toggleOrganized(item: any) {
  const id = Number(item.id)
  const isMarked = organizedIds.value.has(id)
  // 取消标记需要二次确认
  if (isMarked) {
    const ok = await confirm({
      title: '取消已整理标记',
      content: `确定要取消《${item.title || item.name_cn || item.name || item.id}》的已整理标记吗？`,
      confirmText: '取消标记',
      confirmColor: 'warning',
    })
    if (!ok) return
  }
  // 本地先更新，接口失败再回滚
  const next = new Set(organizedIds.value)
  if (isMarked) next.delete(id)
  else next.add(id)
  organizedIds.value = next
  try {
    await bangumiApi.setMark(id, isMarked ? null : 'organized')
  } catch (e) {
    const rollback = new Set(organizedIds.value)
    if (isMarked) rollback.add(id)
    else rollback.delete(id)
    organizedIds.value = rollback
    showError(isMarked ? '取消标记失败' : '标记失败')
  }
}

// 后端已将 Bangumi 图片转换为 /api/system/bgm_img?url=... 格式，直接用 getImg 即可（自动附加 token）
function getPoster(path: string): string {
  if (!path) return ''
  return getImg(path)
}

function openDetail(item: any) {
  navStore.openBangumiDetail(item.id)
}

onMounted(() => {
  fetchData()
})

// 持久化季度选择 + 切换时刷新数据
watch([selectedYear, selectedSeason], () => {
  localStorage.setItem(SEASON_KEY, JSON.stringify({
    year: selectedYear.value,
    season: selectedSeason.value,
  }))
  fetchData()
})
</script>

<template>
  <div class="seasonal-tab pa-4">
    <!-- 控制栏 -->
    <div class="d-flex align-center ga-3 mb-4 flex-wrap">
      <v-btn icon="mdi-chevron-left" size="small" variant="tonal" @click="goToPrevSeason" />
      <v-select
        v-model="selectedYear"
        :items="yearOptions"
        label="年份"
        density="compact"
        hide-details
        style="max-width: 120px"
        @update:model-value="fetchData"
      />
      <span v-if="!loading" class="text-caption text-medium-emphasis">{{ count }} 部</span>
      <v-btn icon="mdi-chevron-right" size="small" variant="tonal" @click="goToNextSeason" />
      <v-btn size="small" variant="tonal" @click="goToCurrentSeason">本季</v-btn>
      <v-switch
        v-model="hideOrganized"
        label="隐藏已整理"
        density="compact"
        hide-details
        color="primary"
        class="ml-2"
        @update:model-value="v => onToggleHide(v as boolean)"
      />
      <span class="text-caption text-medium-emphasis">未整理 {{ unorganizedCount }} 部</span>
    </div>

    <!-- 季度选择标签 -->
    <div class="d-flex ga-2 mb-4">
      <v-tabs v-model="selectedSeason" density="compact">
        <v-tab v-for="s in SEASONS" :key="s" :value="s">
          {{ SEASON_CN[s] }}
        </v-tab>
      </v-tabs>
    </div>

    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <div class="media-card-grid">
        <v-skeleton-loader v-for="i in 12" :key="i" type="card" />
      </div>
    </template>

    <!-- 卡片网格 -->
    <template v-else>
      <div class="media-card-grid">
        <v-card
          v-for="item in displayedItems"
          :key="item.id"
          class="glass-card media-card cursor-pointer"
          :class="{ 'media-card--organized': organizedIds.has(Number(item.id)) }"
          @click="openDetail(item)"
        >
          <div class="media-card__poster">
            <v-img
              v-if="item.image"
              :src="getPoster(item.image)"
              cover
            >
              <template #placeholder>
                <v-skeleton-loader type="image" />
              </template>
            </v-img>
            <span v-if="item.platform" class="media-card__type media-card__type--bgm">{{ item.platform }}</span>
            <span v-if="item.rating" class="media-card__rating">⭐ {{ Number(item.rating).toFixed(1) }}</span>
            <!-- 播出时间徽章 -->
            <span v-if="item.broadcast_time === 'END'" class="media-card__broadcast media-card__broadcast--end">END</span>
            <span v-else-if="item.broadcast_time" class="media-card__broadcast">
              <v-icon size="10" style="color: inherit">mdi-clock-outline</v-icon>
              {{ item.broadcast_time }}
            </span>
            <!-- 已整理角标 + 标记切换按钮 -->
            <v-icon
              v-if="organizedIds.has(Number(item.id))"
              class="media-card__organized-badge"
              size="18"
              color="success"
              icon="mdi-check-circle"
            />
            <v-btn
              :icon="organizedIds.has(Number(item.id)) ? 'mdi-check-circle' : 'mdi-checkbox-blank-circle-outline'"
              :color="organizedIds.has(Number(item.id)) ? 'success' : undefined"
              size="x-small"
              variant="flat"
              elevation="2"
              class="media-card__mark-btn"
              :title="organizedIds.has(Number(item.id)) ? '取消已整理标记' : '标记为已整理'"
              @click.stop="toggleOrganized(item)"
            />
          </div>
          <div class="media-card__info">
            <div class="media-card__title">{{ item.title || item.name_cn || item.name }}</div>
            <div class="media-card__year">{{ (item.air_date || item.date || '').slice(0, 4) }}</div>
          </div>
        </v-card>
      </div>

      <!-- 空状态 -->
      <div v-if="displayedItems.length === 0" class="text-center pa-8">
        <v-icon size="48" color="primary" class="mb-3">mdi-calendar-blank-outline</v-icon>
        <div class="text-body-1">{{ hideOrganized && items.length > 0 ? '该季度已全部整理完成' : '该季度暂无番剧数据' }}</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.media-card__organized-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.6));
}
.media-card__mark-btn {
  position: absolute;
  right: 6px;
  bottom: 6px;
  opacity: 0;
  transition: opacity 0.15s ease;
}
.media-card:hover .media-card__mark-btn,
.media-card__mark-btn:focus-visible {
  opacity: 1;
}
/* 触屏设备无 hover，已标记的按钮保持可见 */
.media-card--organized .media-card__mark-btn {
  opacity: 1;
}
</style>
