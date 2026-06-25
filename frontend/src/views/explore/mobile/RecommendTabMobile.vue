<script setup lang="ts">
import {
  NTag, NIcon, NScrollbar, NTabs, NTabPane, NSkeleton
} from 'naive-ui'
import {
  CalendarMonthOutlined as CalendarIcon,
  ScheduleOutlined as ScheduleIcon
} from '@vicons/material'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import { useRecommend } from '../../../composables/explore/useRecommend'

const {
  exploreData,
  currentDayTab,
  currentScheduleTab,
  isSubscribed,
  getPoster,
  openDetail,
  openBangumi
} = useRecommend()

const scheduleTabLabel = (day: any) => {
  const weekday = day.weekday_cn || ''
  const label = day.label ? `（${day.label}）` : ''
  const date = day.date ? day.date.slice(5).replace('-', '/') : ''
  const count = day.count ?? 0
  return `${weekday}${label} ${date} · ${count}`
}
</script>

<template>
  <div class="recommend-tab-mobile">
      <div v-if="exploreData.loading && exploreData.trending.length === 0" style="padding: var(--space-3)">
         <n-skeleton height="200px" style="border-radius: var(--radius-lg); margin-bottom: var(--m-4)" />
         <n-skeleton text :repeat="2" />
      </div>

      <template v-else>
        <!-- Bangumi Calendar -->
        <div class="section-header">
            <div class="section-title"><n-icon><CalendarIcon /></n-icon> 每日放送</div>
        </div>
        <div class="calendar-box">
            <n-tabs type="line" animated v-model:value="currentDayTab" pane-style="padding: 0">
                <n-tab-pane v-for="day in exploreData.calendar" :key="day.weekday.en" :name="day.weekday.en" :tab="day.weekday.cn">
                    <div class="mobile-grid">
                        <BangumiCard
                            v-for="bgm in day.items"
                            :key="bgm.id"
                            :item="bgm"
                            :is-subscribed="isSubscribed(bgm, 'bangumi')"
                            @click="openBangumi(bgm)"
                        />
                    </div>
                </n-tab-pane>
            </n-tabs>
        </div>

        <!-- 播出时间表（基于 bangumi_data_item 本地数据） -->
        <div class="section-header">
            <div class="section-title"><n-icon><ScheduleIcon /></n-icon> 播出时间表</div>
        </div>
        <div class="calendar-box">
            <n-tabs type="line" animated v-model:value="currentScheduleTab" pane-style="padding: 0">
                <n-tab-pane v-for="day in exploreData.schedule" :key="day.date" :name="day.date" :tab="scheduleTabLabel(day)">
                    <div class="mobile-grid">
                        <BangumiCard
                            v-for="bgm in day.items"
                            :key="bgm.id"
                            :item="bgm"
                            :is-subscribed="isSubscribed(bgm, 'bangumi')"
                            @click="openBangumi(bgm)"
                        />
                    </div>
                </n-tab-pane>
            </n-tabs>
        </div>

        <!-- Popular Movies -->
        <div class="section-header">
            <div class="section-title">TMDB 热门动画电影</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: var(--space-3);">
            <div class="media-scroller">
                <TmdbCard 
                    v-for="m in exploreData.movies" 
                    :key="m.id" 
                    :item="m" 
                    :is-subscribed="isSubscribed(m)" 
                    class="media-card"
                    @click="openDetail(m, 'movie')" 
                />
            </div>
        </n-scrollbar>

        <!-- Popular TV -->
        <div class="section-header">
            <div class="section-title">TMDB 热门动画</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: var(--space-3);">
            <div class="media-scroller">
                <TmdbCard 
                    v-for="t in exploreData.tv" 
                    :key="t.id" 
                    :item="t" 
                    :is-subscribed="isSubscribed(t)" 
                    class="media-card"
                    @click="openDetail(t, 'tv')" 
                />
            </div>
        </n-scrollbar>
      </template>
  </div>
</template>

<style scoped>
.recommend-tab-mobile { 
  width: 100%; 
  padding: var(--space-3); 
  padding-bottom: var(--space-10); 
  box-sizing: border-box;
}

/* Calendar */
.calendar-box { margin-bottom: var(--m-5); }
.mobile-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-spacing-sm);
  margin-top: var(--space-3);
}
@media (min-width: 400px) {
  .mobile-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

/* Section */
.section-header { margin-bottom: var(--space-3); margin-top: var(--space-3); }
.section-title { font-size: var(--text-md); font-weight: bold; display: flex; align-items: center; gap: var(--space-1); }

.media-scroller { display: flex; gap: var(--space-3); width: max-content; }
.media-card { width: 110px; min-width: 110px; }
</style>
