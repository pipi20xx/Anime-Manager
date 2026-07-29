<script setup lang="ts">
/**
 * SeasonalTab — 季度番剧表
 *
 * 功能:
 * - 按年份/季度筛选番剧
 * - 卡片网格展示
 * - 支持一键订阅
 */
import { ref, computed, onMounted } from 'vue'
import { bangumiApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'SeasonalTab' })

const { error: showError } = useNotification()
const navStore = useNavigationStore()

type Season = 'winter' | 'spring' | 'summer' | 'fall'
const SEASON_CN: Record<Season, string> = { winter: '冬', spring: '春', summer: '夏', fall: '秋' }
const SEASONS: Season[] = ['winter', 'spring', 'summer', 'fall']

const now = new Date()
const currentYear = now.getFullYear()
const currentMonth = now.getMonth() + 1
const currentSeason: Season = SEASONS[Math.floor((currentMonth - 1) / 3)]

const selectedYear = ref(currentYear)
const selectedSeason = ref<Season>(currentSeason)
const items = ref<any[]>([])
const loading = ref(false)
const count = ref(0)

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
    const res = await bangumiApi.getSeasonal({
      year: selectedYear.value,
      season: selectedSeason.value,
    })
    // 后端返回 { status, data: [...], count } 结构
    items.value = res?.data || []
    count.value = res?.count || items.value.length
  } catch (e) {
    showError('加载季度番剧失败')
  } finally {
    loading.value = false
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
    </div>

    <!-- 季度选择标签 -->
    <div class="d-flex ga-2 mb-4">
      <v-chip
        v-for="s in SEASONS"
        :key="s"
        :color="selectedSeason === s ? 'primary' : undefined"
        :variant="selectedSeason === s ? 'flat' : 'outlined'"
        size="small"
        label
        class="cursor-pointer"
        @click="selectedSeason = s; fetchData()"
      >
        {{ SEASON_CN[s] }}
      </v-chip>
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
        <v-card v-for="item in items" :key="item.id" class="glass-card media-card cursor-pointer" @click="openDetail(item)">
          <div class="media-card__poster">
            <v-img
              v-if="item.image"
              :src="getPoster(item.image)"
              cover
              class="rounded-t-xl"
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
          </div>
          <div class="media-card__info">
            <div class="media-card__title">{{ item.title || item.name_cn || item.name }}</div>
            <div class="media-card__year">{{ (item.air_date || item.date || '').slice(0, 4) }}</div>
          </div>
        </v-card>
      </div>

      <!-- 空状态 -->
      <div v-if="items.length === 0" class="text-center pa-8">
        <v-icon size="48" color="primary" class="mb-3">mdi-calendar-blank-outline</v-icon>
        <div class="text-body-1">该季度暂无番剧数据</div>
      </div>
    </template>
  </div>
</template>
