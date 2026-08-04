<script setup lang="ts">
/**
 * ScheduleTab — 播出时间表
 *
 * 功能:
 * - 获取 Bangumi 每日放送数据
 * - 按日期分组展示
 * - 支持一键快速订阅
 */
import { ref, onMounted } from 'vue'
import { bangumiApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'ScheduleTab' })

const { success, error: showError } = useNotification()
const navStore = useNavigationStore()

interface ScheduleDay {
  date: string
  weekday: { id: number; en: string; cn: string }
  items: any[]
  label?: string
  count?: number
}

const schedule = ref<ScheduleDay[]>([])
const loading = ref(false)
const activeDate = ref('')

onMounted(async () => {
  loading.value = true
  try {
    // 使用 calendar_local（返回含 date 字段的数据，更适合前端展示）
    const data = await bangumiApi.getCalendarLocal()
    schedule.value = data?.data || []
    if (schedule.value.length > 0) {
      const todayItem = schedule.value.find((d: any) => d.is_today)
      activeDate.value = todayItem?.date || schedule.value[0]?.date || ''
    }
  } catch (e) {
    showError('加载放送表失败')
  } finally {
    loading.value = false
  }
})

// 后端已将 Bangumi 图片转换为 /api/system/bgm_img?url=... 格式，直接用 getImg 即可（自动附加 token）
function getPoster(path: string): string {
  if (!path) return ''
  return getImg(path)
}

function openDetail(item: any) {
  navStore.openBangumiDetail(item.id)
}
</script>

<template>
  <div class="schedule-tab pa-4">
    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <v-skeleton-loader type="card" v-for="i in 3" :key="i" class="mb-4" />
    </template>

    <template v-else>
      <!-- 日期导航条 — 双重吸顶：吸附在外层 explore tabs 下方 -->
      <div class="day-nav d-flex ga-1 overflow-x-auto sticky-sub-tabs">
        <v-chip
          v-for="day in schedule"
          :key="day.date"
          :color="activeDate === day.date ? 'primary' : undefined"
          :variant="activeDate === day.date ? 'flat' : 'text'"
          size="small"
          label
          class="flex-shrink-0 cursor-pointer"
          @click="activeDate = day.date"
        >
          {{ day.weekday?.cn || day.date }}
          <span v-if="day.items?.length" class="ml-1 text-caption">({{ day.items.length }})</span>
        </v-chip>
      </div>

      <!-- 番剧卡片网格 -->
      <template v-for="day in schedule" :key="day.date">
        <div v-show="activeDate === day.date || !activeDate" class="day-section">
          <div class="section-title text-subtitle-2 font-weight-bold mb-3">
            {{ day.weekday?.cn || '' }}
            <span v-if="day.label">（{{ day.label }}）</span>
            <span class="text-caption ml-2">{{ day.date }}</span>
          </div>

          <div class="media-card-grid">
            <v-card v-for="item in day.items" :key="item.id" class="glass-card media-card cursor-pointer" @click="openDetail(item)">
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
                <div class="media-card__year">{{ (item.air_date || item.date || day.date || '').slice(0, 4) }}</div>
              </div>
            </v-card>
          </div>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-if="schedule.length === 0" class="text-center pa-8">
        <v-icon size="48" color="primary" class="mb-3">mdi-calendar-blank-outline</v-icon>
        <div class="text-body-1">暂无放送数据</div>
      </div>
    </template>
  </div>
</template>
