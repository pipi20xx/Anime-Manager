<script setup lang="ts">
import { 
  NCarousel, NImage, NTag, NIcon, NScrollbar, NTabs, NTabPane, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as CalendarIcon
} from '@vicons/material'
import TmdbDetailModal from '../../../components/TmdbDetailModal.vue'
import BangumiDetailModal from '../../../components/BangumiDetailModal.vue'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import { useRecommend } from '../../../composables/explore/useRecommend'

const {
  exploreData,
  tmdbDetail,
  bgmDetail,
  currentDayTab,
  isSubscribed,
  getPoster,
  getBackdrop,
  openDetail,
  openBangumi
} = useRecommend()
</script>

<template>
  <div class="recommend-tab">
      <div v-if="exploreData.loading && exploreData.trending.length === 0" style="padding: 20px">
         <n-skeleton height="400px" style="border-radius: 12px; margin-bottom: 24px" />
         <n-skeleton text :repeat="2" />
      </div>

      <template v-else>
        <!-- Trending Carousel -->
        <n-carousel show-arrow autoplay draggable class="main-carousel">
            <div v-for="item in exploreData.trending.slice(0, 8)" :key="item.id" class="carousel-item" @click="openDetail(item, item.media_type || (item.title ? 'movie' : 'tv'))">
            <img :src="getBackdrop(item.backdrop_path) || getPoster(item.poster_path)" class="carousel-img" />
            <div class="carousel-gradient"></div>
            <div class="carousel-content">
                <div class="c-tag-line">
                    <n-tag v-if="isSubscribed(item)" type="primary" size="small" round :bordered="false" class="subbed-badge" style="margin-right: 4px">
                        <template #icon><n-icon><StarIcon/></n-icon></template>
                        已订阅
                    </n-tag>
                    <n-tag type="warning" size="small" round :bordered="false" class="rating-tag">
                        <template #icon><n-icon><StarIcon/></n-icon></template>
                        {{ item.vote_average?.toFixed(1) }}
                    </n-tag>
                    <span class="c-date">{{ item.release_date || item.first_air_date }}</span>
                    <n-tag size="small" :bordered="false" style="background: var(--bg-surface); color: var(--text-primary)">{{ item.media_type === 'movie' ? 'MOVIE' : 'TV' }}</n-tag>
                </div>
                <div class="c-title">{{ item.title || item.name }}</div>
                <div class="c-overview">{{ item.overview }}</div>
            </div>
            </div>
        </n-carousel>

        <!-- Bangumi Calendar -->
        <div class="section-header" style="margin-top: 32px">
            <div class="section-title"><n-icon><CalendarIcon /></n-icon> 每日放送 (Bangumi)</div>
        </div>
        <div class="calendar-box">
            <n-tabs type="line" animated v-model:value="currentDayTab" justify-content="space-evenly">
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

        <!-- Popular Movies -->
        <div class="section-header" style="margin-top: 32px">
            <div class="section-title">热门动画电影</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: 20px;">
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
        <div class="section-header" style="margin-top: 12px">
            <div class="section-title">热门番剧</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: 20px;">
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

    <TmdbDetailModal 
        v-model:show="tmdbDetail.show"
        :tmdb-id="tmdbDetail.id"
        :media-type="tmdbDetail.type"
        :initial-data="tmdbDetail.initial"
    />

    <BangumiDetailModal 
        v-model:show="bgmDetail.show"
        :subject-id="bgmDetail.id"
        :initial-data="bgmDetail.initial"
    />
  </div>
</template>

<style scoped>
.recommend-tab { width: 100%; padding-bottom: 40px; }

/* Carousel */
.main-carousel { height: 450px; border-radius: var(--card-border-radius, 12px); margin-bottom: 32px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); overflow: hidden; }
.carousel-item { position: relative; width: 100%; height: 100%; cursor: pointer; background: var(--bg-primary); }
.carousel-img { width: 100%; height: 100%; object-fit: cover; opacity: 0.7; transition: transform 10s ease; }
.carousel-item:hover .carousel-img { transform: scale(1.05); opacity: 0.8; }
.carousel-gradient { 
  position: absolute; inset: 0; 
  background: linear-gradient(to top, var(--app-bg-color) 0%, transparent 60%); 
  pointer-events: none; 
}

.carousel-content { position: absolute; bottom: 50px; left: 50px; right: 50px; z-index: 2; }
.c-tag-line { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.rating-tag { font-weight: bold; background: var(--color-warning-bg); color: var(--color-warning); backdrop-filter: blur(4px); }
.c-date { color: var(--n-text-color-3); font-size: 14px; font-family: monospace; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
.c-title { font-size: 48px; font-weight: 900; color: var(--n-text-color-1); margin-bottom: 12px; line-height: 1.1; text-shadow: 0 4px 12px rgba(0,0,0,0.8); letter-spacing: -1px; }
.c-overview { font-size: 16px; color: var(--n-text-color-2); max-width: 800px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-shadow: 0 2px 4px rgba(0,0,0,0.8); }

/* Calendar */
.calendar-box { 
  background: transparent; 
  padding: 0; margin-bottom: 24px; 
}
.calendar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 20px; margin-top: 16px; }

/* Section Common */
.section-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; padding: 0 4px; }
.section-title { font-size: 22px; font-weight: 800; color: var(--n-text-color-1); display: flex; align-items: center; gap: 10px; }
.section-more { font-size: 13px; color: var(--n-text-color-3); cursor: pointer; transition: color 0.2s; }
.section-more:hover { color: var(--n-primary-color); }

.media-scroller { display: flex; gap: 20px; padding: 4px; }
.media-card { min-width: 150px; width: 150px; cursor: pointer; transition: transform 0.2s; display: flex; flex-direction: column; }
.media-card:hover { transform: translateY(-6px); }
</style>