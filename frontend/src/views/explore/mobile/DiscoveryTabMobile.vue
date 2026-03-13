<script setup lang="ts">
import { ref, toRef } from 'vue'
import { 
  NTag, NSpace, NIcon, NSpin, NSelect, NButton, NSkeleton, NEmpty, NBackTop, NDrawer, NDrawerContent, NDivider
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
import { useBackClose } from '../../../composables/useBackClose'
import { getButtonStyle } from '../../../composables/useButtonStyles'

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

const showFilterDrawer = ref(false)

useBackClose(showFilterDrawer)
useBackClose(toRef(tmdbDetail, 'show'))
useBackClose(toRef(bgmDetail, 'show'))
</script>

<template>
  <div class="discovery-tab-mobile">
    <!-- Top Control Bar -->
    <div class="mobile-filter-bar">
        <div class="filter-row-top">
            <n-select 
                v-model:value="filters.source" 
                :options="[{label:'数据源: Bangumi', value:'bangumi'}, {label:'数据源: TMDB', value:'tmdb'}]" 
                size="medium" 
                style="flex: 1" 
            />
            <n-button v-bind="getButtonStyle('icon')" @click="showFilterDrawer = true" size="medium" style="margin-left: 12px">
                <template #icon><n-icon><FilterIcon /></n-icon></template>
            </n-button>
        </div>
        <div class="filter-row-bottom">
            <n-select 
                v-model:value="filters.sort_by" 
                :options="config.sort_options" 
                size="medium" 
                placeholder="排序方式"
                style="width: 100%" 
            />
        </div>
    </div>

    <!-- Content Grid -->
    <div class="content-area">
        <div v-if="data.loading && data.items.length === 0" class="loading-state">
            <n-spin size="medium" />
        </div>
        
        <div v-else-if="data.items.length === 0" class="empty-state">
             <n-empty description="空空如也" />
        </div>

        <div v-else class="mobile-grid">
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
        
        <div ref="loadTrigger" class="scroll-trigger" style="height: 40px; margin-top: 12px; display: flex; justify-content: center; align-items: center;">
            <n-spin v-if="data.loading && data.items.length > 0" size="small" />
            <span v-if="!data.hasMore && data.items.length > 0" style="color: var(--text-muted); font-size: 12px;">到底啦</span>
        </div>
    </div>

    <!-- Filter Drawer -->
    <n-drawer v-model:show="showFilterDrawer" placement="right" width="85%">
        <n-drawer-content title="筛选条件">
            <n-space vertical size="large">
                <!-- TMDB Type -->
                <div v-if="filters.source === 'tmdb'">
                    <div class="f-label">类型</div>
                    <n-space>
                        <n-tag checkable :checked="filters.media_type === 'tv'" @click="filters.media_type = 'tv'">剧集</n-tag>
                        <n-tag checkable :checked="filters.media_type === 'movie'" @click="filters.media_type = 'movie'">电影</n-tag>
                    </n-space>
                </div>

                <!-- Bangumi Subtype -->
                <div v-if="filters.source === 'bangumi'">
                    <div class="f-label">分类</div>
                    <n-space size="small">
                        <n-tag checkable :checked="filters.subtype === null" @click="filters.subtype = null">全部</n-tag>
                        <n-tag v-for="t in config.bangumi_types" :key="t.id" checkable :checked="filters.subtype === t.id" @click="filters.subtype = t.id">{{ t.name }}</n-tag>
                    </n-space>
                </div>

                <!-- Year -->
                <div>
                    <div class="f-label">年份</div>
                    <n-space size="small">
                        <n-tag checkable :checked="filters.year === null" @click="filters.year = null">全部</n-tag>
                        <n-tag v-for="y in config.years" :key="y" checkable :checked="filters.year === y" @click="filters.year = y">{{ y }}</n-tag>
                    </n-space>
                </div>

                <!-- Genre/Tag -->
                <div>
                    <div class="f-label">{{ filters.source === 'bangumi' ? '标签' : '流派' }}</div>
                    <n-space size="small">
                        <n-tag checkable :checked="filters.genre === null" @click="filters.genre = null">全部</n-tag>
                        <n-tag v-for="g in config.genres" :key="g.id" checkable :checked="filters.genre === String(g.id)" @click="filters.genre = String(g.id)">{{ g.name }}</n-tag>
                    </n-space>
                </div>

                <!-- Bangumi Extras -->
                <template v-if="filters.source === 'bangumi'">
                    <n-divider />
                    <div>
                        <div class="f-label">地区</div>
                        <n-space size="small">
                            <n-tag checkable :checked="filters.region === null" @click="filters.region = null">全部</n-tag>
                            <n-tag v-for="r in config.bangumi_regions" :key="r.id" checkable :checked="filters.region === r.id" @click="filters.region = r.id">{{ r.name }}</n-tag>
                        </n-space>
                    </div>
                    <div>
                        <div class="f-label">来源</div>
                        <n-space size="small">
                            <n-tag checkable :checked="filters.story_source === null" @click="filters.story_source = null">全部</n-tag>
                            <n-tag v-for="s in config.bangumi_sources" :key="s.id" checkable :checked="filters.story_source === s.id" @click="filters.story_source = s.id">{{ s.name }}</n-tag>
                        </n-space>
                    </div>
                </template>
            </n-space>
        </n-drawer-content>
    </n-drawer>

    <TmdbDetailModal v-model:show="tmdbDetail.show" :tmdb-id="tmdbDetail.id" :media-type="tmdbDetail.type" :initial-data="tmdbDetail.initial" />
    <BangumiDetailModal v-model:show="bgmDetail.show" :subject-id="bgmDetail.id" :initial-data="bgmDetail.initial" />
    <n-back-top :right="20" :bottom="80" />
  </div>
</template>

<style scoped>
.discovery-tab-mobile {
  width: 100%;
  padding: var(--m-spacing-md);
  box-sizing: border-box;
}
.mobile-filter-bar {
  display: flex;
  flex-direction: column;
  margin-bottom: var(--m-spacing-lg);
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--app-bg-color);
  padding: var(--m-spacing-md) 0;
  width: 100%;
  box-sizing: border-box;
}
.filter-row-top { display: flex; align-items: center; width: 100%; }
.filter-row-bottom { margin-top: var(--m-spacing-sm); width: 100%; }

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

.f-label {
  font-size: var(--m-text-sm);
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: var(--m-spacing-sm);
}
</style>
