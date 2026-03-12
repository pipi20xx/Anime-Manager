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
      <div v-if="exploreData.loading && exploreData.trending.length === 0" style="padding: var(--space-5)">
         <n-skeleton height="400px" style="border-radius: var(--radius-xl); margin-bottom: var(--m-6)" />
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
                    <n-tag v-if="isSubscribed(item)" type="primary" size="small" round :bordered="false" class="subbed-badge" style="margin-right: var(--m-1)">
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
        <div class="section-header" style="margin-top: var(--m-8)">
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
        <div class="section-header" style="margin-top: var(--m-8)">
            <div class="section-title">热门动画电影</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: var(--space-5);">
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
        <div class="section-header" style="margin-top: var(--space-3)">
            <div class="section-title">热门番剧</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: var(--space-5);">
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
.recommend-tab { width: 100%; padding-bottom: var(--space-10); }

/* Carousel */
.main-carousel { height: 450px; border-radius: var(--card-border-radius, 12px); margin-bottom: var(--m-8); box-shadow: var(--shadow-xl); overflow: hidden; }
.carousel-item { position: relative; width: 100%; height: 100%; cursor: pointer; background: var(--bg-primary); }
.carousel-img { width: 100%; height: 100%; object-fit: cover; opacity: var(--opacity-70); transition: transform 10s ease; }
.carousel-item:hover .carousel-img { transform: scale(1.05); opacity: var(--opacity-80); }
.carousel-gradient { 
  position: absolute; inset: 0; 
  background: linear-gradient(to top, var(--app-bg-color) 0%, transparent 60%); 
  pointer-events: none; 
}

.carousel-content { position: absolute; bottom: var(--space-12); left: var(--space-12); right: var(--space-12); z-index: 2; }
.c-tag-line { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--m-3); }
.rating-tag { font-weight: bold; background: var(--color-warning-bg); color: var(--color-warning); backdrop-filter: blur(4px); }
.c-date { color: var(--text-tertiary); font-size: var(--text-md); font-family: monospace; text-shadow: var(--shadow-text-md); }
.c-title { font-size: var(--text-5xl); font-weight: 900; color: var(--text-primary); margin-bottom: var(--m-3); line-height: var(--leading-tight); text-shadow: var(--shadow-text-xl); letter-spacing: var(--tracking-tight); }
.c-overview { font-size: var(--text-lg); color: var(--text-secondary); max-width: 800px; line-height: var(--leading-relaxed); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-shadow: var(--shadow-text-lg); }

/* Calendar */
.calendar-box {
  background: transparent;
  padding: 0; margin-bottom: var(--m-6);
}
.calendar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-5); margin-top: var(--space-4); }

/* Section Common */
.section-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: var(--m-4); padding: 0 var(--m-1); }
.section-title { font-size: var(--text-2xl); font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: var(--space-2); }
.section-more { font-size: var(--text-base); color: var(--text-tertiary); cursor: pointer; transition: color var(--transition-fast); }
.section-more:hover { color: var(--n-primary-color); }

.media-scroller { display: flex; gap: var(--space-5); padding: var(--m-1); }
.media-card { min-width: 150px; width: 150px; cursor: pointer; transition: transform var(--transition-fast); display: flex; flex-direction: column; }
.media-card:hover { transform: translateY(-6px); }
</style>