<script setup lang="ts">
import {
  NIcon, NScrollbar, NTabs, NTabPane, NSkeleton
} from 'naive-ui'
import {
  CalendarDaysIcon,
  ClockIcon as ScheduleIcon
} from '@heroicons/vue/24/outline'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import { useRecommend } from '../../../composables/explore/useRecommend'

const {
  exploreData,
  currentDayTab,
  currentScheduleTab,
  isSubscribed,
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
  <div class="recommend-tab">
        <!-- Bangumi Calendar -->
        <div class="section-header" style="margin-top: var(--m-8)">
            <div class="section-title"><n-icon><CalendarIcon /></n-icon> 每日放送 (Bangumi)</div>
        </div>
        <div class="calendar-box">
            <div v-if="exploreData.calendar.length === 0" class="section-loading">
                <n-skeleton v-for="i in 6" :key="i" class="skeleton-card" />
            </div>
            <n-tabs v-else type="line" v-model:value="currentDayTab" justify-content="space-evenly" display-directive="if">
                <n-tab-pane v-for="day in exploreData.calendar" :key="day.weekday.en" :name="day.weekday.en" :tab="day.weekday.cn">
                    <div class="calendar-grid">
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
        <div class="section-header" style="margin-top: var(--m-8)">
            <div class="section-title"><n-icon><ScheduleIcon /></n-icon> 播出时间表</div>
        </div>
        <div class="calendar-box">
            <div v-if="exploreData.schedule.length === 0" class="section-loading">
                <n-skeleton v-for="i in 6" :key="i" class="skeleton-card" />
            </div>
            <n-tabs v-else type="line" v-model:value="currentScheduleTab" justify-content="space-evenly" display-directive="if">
                <n-tab-pane v-for="day in exploreData.schedule" :key="day.date" :name="day.date" :tab="scheduleTabLabel(day)">
                    <div class="calendar-grid">
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
        <div class="section-header" style="margin-top: var(--m-8)">
            <div class="section-title">TMDB 热门动画电影</div>
        </div>
        <div v-if="exploreData.movies.length === 0" class="section-loading-h">
            <n-skeleton v-for="i in 6" :key="i" class="skeleton-card-h" />
        </div>
        <n-scrollbar v-else x-scrollable style="padding-bottom: var(--space-5);">
            <div class="media-scroller">
                <TmdbCard 
                    v-for="m in exploreData.movies.slice(0, 12)" 
                    :key="m.id" 
                    :item="m" 
                    :is-subscribed="isSubscribed(m)" 
                    class="media-card"
                    @click="openDetail(m, 'movie')" 
                />
            </div>
        </n-scrollbar>

        <!-- Popular TV -->
        <div class="section-header" style="margin-top: var(--space-3)">
            <div class="section-title">TMDB 热门动画</div>
        </div>
        <div v-if="exploreData.tv.length === 0" class="section-loading-h">
            <n-skeleton v-for="i in 6" :key="i" class="skeleton-card-h" />
        </div>
        <n-scrollbar v-else x-scrollable style="padding-bottom: var(--space-5);">
            <div class="media-scroller">
                <TmdbCard 
                    v-for="t in exploreData.tv.slice(0, 12)" 
                    :key="t.id" 
                    :item="t" 
                    :is-subscribed="isSubscribed(t)" 
                    class="media-card"
                    @click="openDetail(t, 'tv')" 
                />
            </div>
        </n-scrollbar>
  </div>
</template>

<style scoped>
.recommend-tab { width: 100%; padding-bottom: var(--space-10); }

/* Calendar */
.calendar-box {
  background: transparent;
  padding: 0; margin-bottom: var(--m-6);
}

/* 强制禁用 n-tab-pane 过渡：非激活项直接 display:none，激活项无 transform */
.calendar-box :deep(.n-tab-pane) {
  transition: none !important;
  transform: none !important;
}
.calendar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-5); margin-top: var(--space-4); animation: tab-fade-in 0.15s ease; }

/* Section Loading 占位 */
.section-loading { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-5); margin-top: var(--space-4); }
.skeleton-card { height: 210px; border-radius: var(--radius-xl); }
.section-loading-h { display: flex; gap: var(--space-5); padding: var(--m-1); }
.skeleton-card-h { min-width: 150px; width: 150px; height: 225px; border-radius: var(--radius-xl); }

/* Section Common */
.section-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: var(--m-4); padding: 0 var(--m-1); }
.section-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: var(--space-2); }
.section-more { font-size: var(--text-base); color: var(--text-tertiary); cursor: pointer; transition: color var(--transition-fast); }
.section-more:hover { color: var(--n-primary-color); }

.media-scroller { display: flex; gap: var(--space-5); padding: var(--m-1); }
.media-card { min-width: 150px; width: 150px; cursor: pointer; transition: transform var(--transition-fast); display: flex; flex-direction: column; }
.media-card:hover { transform: translateY(-6px); }

@keyframes tab-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>