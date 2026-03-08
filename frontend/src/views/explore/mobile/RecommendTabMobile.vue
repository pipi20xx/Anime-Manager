<script setup lang="ts">
import { toRef } from 'vue'
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
import { useBackClose } from '../../../composables/useBackClose'

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

useBackClose(toRef(tmdbDetail, 'show'))
useBackClose(toRef(bgmDetail, 'show'))
</script>

<template>
  <div class="recommend-tab-mobile">
      <div v-if="exploreData.loading && exploreData.trending.length === 0" style="padding: 12px">
         <n-skeleton height="200px" style="border-radius: 8px; margin-bottom: 16px" />
         <n-skeleton text :repeat="2" />
      </div>

      <template v-else>
        <!-- Trending Carousel -->
        <n-carousel show-arrow autoplay draggable class="mobile-carousel">
            <div v-for="item in exploreData.trending.slice(0, 5)" :key="item.id" class="carousel-item" @click="openDetail(item, item.media_type || (item.title ? 'movie' : 'tv'))">
            <img :src="getBackdrop(item.backdrop_path) || getPoster(item.poster_path)" class="carousel-img" />
            <div class="carousel-gradient"></div>
            <div class="carousel-content">
                <div class="c-tag-line">
                    <n-tag v-if="isSubscribed(item)" type="primary" size="tiny" round :bordered="false" class="subbed-badge" style="margin-right: 4px">
                        已订
                    </n-tag>
                    <n-tag type="warning" size="tiny" round :bordered="false" class="rating-tag">
                        {{ item.vote_average?.toFixed(1) }}
                    </n-tag>
                </div>
                <div class="c-title">{{ item.title || item.name }}</div>
            </div>
            </div>
        </n-carousel>

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

        <!-- Popular Movies -->
        <div class="section-header">
            <div class="section-title">热门电影</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: 12px;">
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
            <div class="section-title">热门番剧</div>
        </div>
        <n-scrollbar x-scrollable style="padding-bottom: 12px;">
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
.recommend-tab-mobile { 
  width: 100%; 
  padding: 12px; 
  padding-bottom: 40px; 
  box-sizing: border-box;
}

/* Carousel */
.mobile-carousel { 
  height: 200px; 
  border-radius: 8px; 
  margin-bottom: 20px; 
  overflow: hidden; 
  box-shadow: 0 4px 12px rgba(0,0,0,0.3); 
  width: 100%;
}
.carousel-item { position: relative; width: 100%; height: 100%; }
.carousel-img { width: 100%; height: 100%; object-fit: cover; }
.carousel-gradient { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 60%); }
.carousel-content { position: absolute; bottom: 12px; left: 12px; right: 12px; z-index: 2; }
.c-tag-line { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.rating-tag { font-weight: bold; background: var(--color-warning); color: #000; }
.c-title { font-size: 18px; font-weight: bold; color: var(--text-primary); line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Calendar */
.calendar-box { margin-bottom: 20px; }
.mobile-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }

/* Section */
.section-header { margin-bottom: 12px; margin-top: 12px; }
.section-title { font-size: 16px; font-weight: bold; display: flex; align-items: center; gap: 6px; }

.media-scroller { display: flex; gap: 12px; width: max-content; }
.media-card { width: 110px; min-width: 110px; }
</style>
