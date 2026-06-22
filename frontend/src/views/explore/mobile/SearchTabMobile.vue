<script setup lang="ts">
import { 
  NSpin, NEmpty, NDivider
} from 'naive-ui'
import AppSearchField from '../../../components/AppSearchField.vue'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import { useSearch } from '../../../composables/explore/useSearch'

const {
  keyword,
  loading,
  hasSearched,
  results,
  doSearch,
  openTmdb,
  openBangumi,
  isSubscribed
} = useSearch()
</script>

<template>
  <div class="search-tab-mobile">
    <div class="mobile-search-bar">
        <AppSearchField v-model:value="keyword" placeholder="搜 TMDB / Bangumi..." :loading="loading" @search="doSearch" />
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
  </div>
</template>

<style scoped>
.search-tab-mobile {
  width: 100%;
  min-height: 80vh;
  padding: var(--m-spacing-md);
  box-sizing: border-box;
}
.mobile-search-bar {
  margin-bottom: var(--m-spacing-lg);
  position: sticky;
  top: 0;
  z-index: 9;
  background: var(--app-bg-color);
  padding: var(--m-spacing-sm) 0;
  width: 100%;
  box-sizing: border-box;
}
.section { margin-bottom: var(--m-spacing-xl); }
.sec-title {
  font-weight: 600;
  margin-bottom: var(--m-spacing-md);
  font-size: var(--m-text-md);
  color: var(--text-secondary);
}
.mobile-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-spacing-sm);
}
@media (min-width: 400px) {
  .mobile-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
.loading-state {
  padding: var(--m-spacing-3xl) 0;
  text-align: center;
}
.empty-state {
  padding: var(--m-spacing-3xl) 0;
}
</style>