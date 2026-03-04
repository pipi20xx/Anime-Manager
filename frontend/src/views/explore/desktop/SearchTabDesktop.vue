<script setup lang="ts">
import { 
  NInput, NButton, NIcon, NSpin, NEmpty, NDivider
} from 'naive-ui'
import { SearchOutlined } from '@vicons/material'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import TmdbDetailModal from '../../../components/TmdbDetailModal.vue'
import BangumiDetailModal from '../../../components/BangumiDetailModal.vue'
import { useSearch } from '../../../composables/explore/useSearch'

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
</script>

<template>
  <div class="search-tab">
    <div class="search-bar">
        <n-input 
            v-model:value="keyword" 
            type="text" 
            placeholder="输入名称搜索 TMDB 和 Bangumi..." 
            size="large"
            clearable
            @keydown.enter="doSearch"
        >
            <template #prefix>
                <n-icon :component="SearchOutlined" />
            </template>
        </n-input>
        <n-button type="primary" size="large" @click="doSearch" :loading="loading">
            搜索
        </n-button>
    </div>

    <div class="results-area" v-if="hasSearched">
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>

        <div v-else-if="!results.bangumi.length && !results.tmdb_movie.length && !results.tmdb_tv.length" class="empty-state">
            <n-empty description="未找到相关结果" size="large" />
        </div>

        <div v-else>
            <div v-if="results.bangumi.length > 0" class="section">
                <n-divider title-placement="left">Bangumi (番剧)</n-divider>
                <div class="media-grid">
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
                <n-divider title-placement="left">TMDB (电影)</n-divider>
                <div class="media-grid">
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
                <n-divider title-placement="left">TMDB (剧集)</n-divider>
                <div class="media-grid">
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
.search-tab { width: 100%; min-height: 80vh; padding: 0 4px; }
.search-bar { display: flex; gap: 12px; margin-bottom: 32px; max-width: 800px; margin-left: auto; margin-right: auto; }
.section { margin-bottom: 40px; }
.media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 20px; }
.loading-state { padding: 80px; display: flex; justify-content: center; }
.empty-state { padding: 80px; }
</style>