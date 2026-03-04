<script setup lang="ts">
import { toRef } from 'vue'
import { 
  NInput, NButton, NIcon, NSpin, NEmpty, NDivider, NInputGroup
} from 'naive-ui'
import { SearchOutlined } from '@vicons/material'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import TmdbDetailModal from '../../../components/TmdbDetailModal.vue'
import BangumiDetailModal from '../../../components/BangumiDetailModal.vue'
import { useSearch } from '../../../composables/explore/useSearch'
import { useBackClose } from '../../../composables/useBackClose'

const {
  keyword,
  loading,
  hasSearched,
  results,
  tmdbDetail,
  bgmDetail,
  doSearch,
  openTmdb,
  openBangumi,
  isSubscribed
} = useSearch()

useBackClose(toRef(tmdbDetail, 'show'))
useBackClose(toRef(bgmDetail, 'show'))
</script>

<template>
  <div class="search-tab-mobile">
    <div class="mobile-search-bar">
        <n-input-group>
            <n-input 
                v-model:value="keyword" 
                type="text" 
                placeholder="搜 TMDB / Bangumi..." 
                size="small"
                clearable
                @keydown.enter="doSearch"
            />
            <n-button type="primary" size="small" @click="doSearch" :loading="loading">
                <template #icon><n-icon :component="SearchOutlined" /></template>
            </n-button>
        </n-input-group>
    </div>

    <div class="results-area" v-if="hasSearched">
        <div v-if="loading" class="loading-state">
            <n-spin size="medium" />
        </div>

        <div v-else-if="!results.bangumi.length && !results.tmdb_movie.length && !results.tmdb_tv.length" class="empty-state">
            <n-empty description="未找到结果" />
        </div>

        <div v-else>
            <div v-if="results.bangumi.length > 0" class="section">
                <div class="sec-title">Bangumi</div>
                <div class="mobile-grid">
                    <BangumiCard 
                        v-for="item in results.bangumi" 
                        :key="item.id" 
                        :item="item" 
                        :is-subscribed="isSubscribed(item, 'bangumi')" 
                        @click="openBangumi(item)" 
                    />
                </div>
            </div>

            <div v-if="results.tmdb_movie.length > 0" class="section">
                <div class="sec-title">电影</div>
                <div class="mobile-grid">
                    <TmdbCard 
                        v-for="item in results.tmdb_movie" 
                        :key="item.id" 
                        :item="item" 
                        :is-subscribed="isSubscribed(item, 'tmdb')" 
                        @click="openTmdb(item, 'movie')" 
                    />
                </div>
            </div>

            <div v-if="results.tmdb_tv.length > 0" class="section">
                <div class="sec-title">剧集</div>
                <div class="mobile-grid">
                    <TmdbCard 
                        v-for="item in results.tmdb_tv" 
                        :key="item.id" 
                        :item="item" 
                        :is-subscribed="isSubscribed(item, 'tmdb')" 
                        @click="openTmdb(item, 'tv')" 
                    />
                </div>
            </div>
        </div>
    </div>

    <TmdbDetailModal v-model:show="tmdbDetail.show" :tmdb-id="tmdbDetail.id" :media-type="tmdbDetail.type" :initial-data="tmdbDetail.initial" />
    <BangumiDetailModal v-model:show="bgmDetail.show" :subject-id="bgmDetail.id" :initial-data="bgmDetail.initial" />
  </div>
</template>

<style scoped>
.search-tab-mobile { 
  width: 100%; 
  min-height: 80vh; 
  padding: 12px; 
  box-sizing: border-box;
}
.mobile-search-bar { 
  margin-bottom: 16px; 
  position: sticky; 
  top: 0; 
  z-index: 9; 
  background: var(--app-bg-color); 
  padding: 8px 0; 
  width: 100%;
  box-sizing: border-box;
}
.section { margin-bottom: 24px; }
.sec-title { font-weight: bold; margin-bottom: 8px; font-size: 14px; color: var(--n-text-color-2); }
.mobile-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.loading-state { padding: 40px; text-align: center; }
.empty-state { padding: 40px; }
</style>