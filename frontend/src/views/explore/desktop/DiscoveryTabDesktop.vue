<script setup lang="ts">
import { 
  NTag, NSpace, NIcon, NSpin, NSelect, NButton, NSkeleton, NEmpty, NBackTop
} from 'naive-ui'
import {
  FilterAltOutlined as FilterIcon,
  StarOutlined as StarIcon
} from '@vicons/material'
import TmdbDetailModal from '../../../components/TmdbDetailModal.vue'
import BangumiDetailModal from '../../../components/BangumiDetailModal.vue'
import BangumiCard from '../../../components/BangumiCard.vue'
import TmdbCard from '../../../components/TmdbCard.vue'
import { useDiscovery } from '../../../composables/explore/useDiscovery'

const {
  config,
  filters,
  data,
  tmdbDetail,
  bgmDetail,
  loadTrigger,
  isSubscribed,
  openDetail
} = useDiscovery()
</script>

<template>
  <div class="discovery-tab">
    <div class="filter-bar">
        <div class="filter-row">
            <div class="filter-label">数据源:</div>
            <n-space>
                <n-tag checkable :checked="filters.source === 'tmdb'" @click="filters.source = 'tmdb'" class="filter-tag">TMDB (全球)</n-tag>
                <n-tag checkable :checked="filters.source === 'bangumi'" @click="filters.source = 'bangumi'" class="filter-tag">Bangumi (番剧)</n-tag>
            </n-space>
        </div>

        <div class="filter-row" v-if="filters.source === 'tmdb'">
            <div class="filter-label">类型:</div>
            <n-space>
                <n-tag checkable :checked="filters.media_type === 'tv'" @click="filters.media_type = 'tv'" class="filter-tag">剧集 (TV)</n-tag>
                <n-tag checkable :checked="filters.media_type === 'movie'" @click="filters.media_type = 'movie'" class="filter-tag">剧场版 (Movie)</n-tag>
            </n-space>
        </div>

        <div class="filter-row" v-if="filters.source === 'bangumi'">
            <div class="filter-label">分类:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.subtype === null" @click="filters.subtype = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="t in config.bangumi_types" :key="t.id" checkable :checked="filters.subtype === t.id" @click="filters.subtype = t.id" class="filter-tag">
                    {{ t.name }}
                </n-tag>
            </div>
        </div>

        <div class="filter-row" v-if="filters.source === 'tmdb' && config.languages.length > 0">
            <div class="filter-label">语言:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.language === null" @click="filters.language = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="l in config.languages" :key="l.value" checkable :checked="filters.language === l.value" @click="filters.language = l.value" class="filter-tag">
                    {{ l.label }}
                </n-tag>
            </div>
        </div>

        <div class="filter-row" v-if="filters.source === 'bangumi'">
            <div class="filter-label">地区:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.region === null" @click="filters.region = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="r in config.bangumi_regions" :key="r.id" checkable :checked="filters.region === r.id" @click="filters.region = r.id" class="filter-tag">
                    {{ r.name }}
                </n-tag>
            </div>
        </div>
        
        <div class="filter-row" v-if="filters.source === 'bangumi'">
            <div class="filter-label">来源:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.story_source === null" @click="filters.story_source = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="s in config.bangumi_sources" :key="s.id" checkable :checked="filters.story_source === s.id" @click="filters.story_source = s.id" class="filter-tag">
                    {{ s.name }}
                </n-tag>
            </div>
        </div>

        <div class="filter-row" v-if="filters.source === 'bangumi'">
            <div class="filter-label">受众:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.audience === null" @click="filters.audience = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="a in config.bangumi_audiences" :key="a.id" checkable :checked="filters.audience === a.id" @click="filters.audience = a.id" class="filter-tag">
                    {{ a.name }}
                </n-tag>
            </div>
        </div>

        <div class="filter-row">
            <div class="filter-label">{{ filters.source === 'bangumi' ? '标签' : '流派' }}:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.genre === null" @click="filters.genre = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="g in config.genres" :key="g.id" checkable :checked="filters.genre === String(g.id)" @click="filters.genre = String(g.id)" class="filter-tag">
                    {{ g.name }}
                </n-tag>
            </div>
        </div>
        
        <div class="filter-row">
            <div class="filter-label">年份:</div>
            <div class="filter-container">
                <n-tag checkable :checked="filters.year === null" @click="filters.year = null" class="filter-tag">全部</n-tag>
                <n-tag v-for="y in config.years" :key="y" checkable :checked="filters.year === y" @click="filters.year = y" class="filter-tag">
                    {{ y }}
                </n-tag>
            </div>
        </div>

        <div class="filter-actions">
            <div class="sort-wrapper">
                <n-select v-model:value="filters.sort_by" :options="config.sort_options" size="small" style="width: 200px" />
            </div>
            <n-tag type="primary" :bordered="false" size="small" style="background: rgba(99, 226, 183, 0.15)">
                共 {{ data.items.length }} 条结果
            </n-tag>
        </div>
    </div>

    <div class="content-area">
        <div v-if="data.loading && data.items.length === 0" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else-if="data.items.length === 0" class="empty-state">
             <n-empty description="什么都没找到..." size="large" />
        </div>

        <div v-else class="media-grid">
            <template v-for="item in data.items" :key="item.id">
                <BangumiCard 
                    v-if="filters.source === 'bangumi'" 
                    :item="item" 
                    :is-subscribed="isSubscribed(item)" 
                    @click="openDetail(item)" 
                />
                <TmdbCard 
                    v-else 
                    :item="item" 
                    :is-subscribed="isSubscribed(item)" 
                    @click="openDetail(item)" 
                />
            </template>
        </div>
        
        <div ref="loadTrigger" class="scroll-trigger" style="height: 20px; margin-top: 20px; display: flex; justify-content: center;">
            <n-spin v-if="data.loading && data.items.length > 0" size="small" />
            <span v-if="!data.hasMore && data.items.length > 0" style="color: #666; font-size: 12px;">已经到底啦 ~</span>
        </div>
    </div>

    <TmdbDetailModal v-model:show="tmdbDetail.show" :tmdb-id="tmdbDetail.id" :media-type="tmdbDetail.type" :initial-data="tmdbDetail.initial" />
    <BangumiDetailModal v-model:show="bgmDetail.show" :subject-id="bgmDetail.id" :initial-data="bgmDetail.initial" />
    <n-back-top :right="40" :bottom="40" />
  </div>
</template>

<style scoped>
.discovery-tab { width: 100%; min-height: 80vh; display: flex; flex-direction: column; }
.filter-bar { background: var(--app-surface-card, rgba(255, 255, 255, 0.05)); border-radius: 12px; padding: 16px; margin-bottom: 24px; border: 1px solid rgba(255, 255, 255, 0.08); }
.filter-row { display: flex; align-items: flex-start; margin-bottom: 12px; }
.filter-label { width: 60px; font-weight: bold; color: var(--n-text-color-3); padding-top: 4px; flex-shrink: 0; }
.filter-container { display: flex; gap: 8px; flex-wrap: wrap; }
.filter-tag { cursor: pointer; transition: all 0.2s; }
.filter-tag:hover { color: var(--n-primary-color); }
.filter-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.05); }

.media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 20px; padding-bottom: 10px; }

.loading-state { padding: 50px; display: flex; justify-content: center; }
.empty-state { padding: 50px; }
</style>