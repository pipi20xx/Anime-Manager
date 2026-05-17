<script setup lang="ts">
import { 
  NModal, NCard, NImage, NSpace, NTag, NButton, NIcon, NScrollbar, NSkeleton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  AddCircleOutlined as SubIcon,
  PersonOutlined as CastIcon,
  SearchOutlined as SearchIcon,
  ExpandMoreOutlined as ExpandIcon,
  RefreshOutlined as LoadingIcon,
  CheckCircleOutlined
} from '@vicons/material'
import { useTmdbDetail } from '../../composables/components/useTmdbDetail'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  tmdbId: string | number
  mediaType: 'movie' | 'tv' | string
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  detail,
  isSubscribed,
  displayGenres,
  getPoster,
  getBackdrop,
  handleClose,
  openExternal,
  handleSubscribe,
  handleSearch,
  toggleSeason,
  getSeasonInfo,
  getSeasonEpisodes,
  isSeasonLoading,
  isSeasonExpanded,
  getEpisodeEmbyInfo,
  formatFileSize,
  embyStatus,
  isInLibrary,
  getSeasonLibraryStatus
} = useTmdbDetail(props, emit)
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="max-width: 1000px; width: 95%; height: 96vh;">
    <n-card class="tmdb-detail-modal" content-style="padding: 0; display: flex; flex-direction: column; height: 100%;" :bordered="false" size="huge" role="dialog">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="400px" width="100%" />
      </div>

      <div v-else-if="detail" class="detail-container" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <n-scrollbar style="flex: 1;">
          <!-- Header -->
          <div class="header-content">
                  <div class="poster-col">
                      <n-image :src="getPoster(detail.poster_path)" class="main-poster" object-fit="cover" />
                  </div>
                  <div class="info-col">
                      <div class="title-row">
                          <h1 class="title">{{ detail.title || detail.name }}</h1>
                          <n-tag v-if="isInLibrary" type="success" size="small" round>
                              <template #icon><n-icon><CheckCircleOutlined /></n-icon></template>
                              已入库
                          </n-tag>
                      </div>
                      <div class="original-title">{{ detail.original_title || detail.original_name }}</div>
                      <div v-if="detail.tagline" class="tagline">"{{ detail.tagline }}"</div>
                      
                      <n-space class="meta-tags" align="center">
                          <n-tag type="warning" round size="small">
                              <template #icon><n-icon><StarIcon /></n-icon></template>
                              {{ detail.vote_average?.toFixed(1) }}
                          </n-tag>
                          <n-tag :bordered="false" size="small" style="background: var(--app-surface-inner)">
                              <template #icon><n-icon><DateIcon /></n-icon></template>
                              {{ detail.release_date || detail.first_air_date }}
                          </n-tag>
                          <n-tag v-if="detail.number_of_seasons" type="info" size="small" round>
                              {{ detail.number_of_seasons }} 季
                          </n-tag>
                      </n-space>

                      <div class="actions">
                          <n-button v-bind="getButtonStyle('primary')" size="small" @click="handleSubscribe" :disabled="isSubscribed">
                              {{ isSubscribed ? '已在订阅中' : '订阅/追番' }}
                          </n-button>
                          <n-button v-bind="getButtonStyle('primary')" size="small" @click="handleSearch">
                              搜资源
                          </n-button>
                          <n-button v-bind="getButtonStyle('icon')" size="small" @click="openExternal">
                              <template #icon><n-icon><LinkIcon /></n-icon></template>
                          </n-button>
                      </div>
                  </div>
              </div>

          <!-- Body -->
          <div class="body-content">
              <div v-if="displayGenres.length > 0" class="genres-row">
                  <n-space>
                      <n-tag v-for="g in displayGenres" :key="g" type="primary" size="tiny" :bordered="false" round>
                          {{ g }}
                      </n-tag>
                  </n-space>
              </div>

              <div class="overview-section">
                  <h3>简介</h3>
                  <p class="overview-text">{{ detail.overview || '暂无简介' }}</p>
              </div>

              <div v-if="detail.cast?.length" class="cast-section">
                  <h3><n-icon><CastIcon /></n-icon> 演职员</h3>
                  <n-scrollbar x-scrollable>
                      <div class="cast-scroller">
                          <div v-for="c in detail.cast" :key="c.actor + c.character" class="cast-card">
                              <div class="cast-avatar">
                                  <n-image :src="getPoster(c.image)" object-fit="cover" preview-disabled />
                              </div>
                              <div class="cast-names">
                                  <div class="actor-name" :title="c.actor">{{ c.actor }}</div>
                              </div>
                          </div>
                      </div>
                  </n-scrollbar>
              </div>

              <div v-if="detail.seasons?.length" class="seasons-section">
                  <h3>季度信息</h3>
                  <div class="seasons-list">
                      <div v-for="s in detail.seasons" :key="s.id" class="season-item">
                          <div class="season-card" @click="toggleSeason(s.season_number)">
                              <div class="s-poster">
                                  <n-image :src="getPoster(s.poster_path)" object-fit="cover" preview-disabled />
                              </div>
                              <div class="s-info">
                                  <div class="s-name-row">
                                      <span class="s-name">{{ s.name }}</span>
                                      <n-tag v-if="getSeasonLibraryStatus(s.season_number)?.exists" type="success" size="tiny" round>
                                          已入库
                                      </n-tag>
                                  </div>
                                  <div class="s-ep">{{ s.episode_count }} 集</div>
                              </div>
                              <div class="s-expand-icon">
                                  <n-icon v-if="isSeasonLoading(s.season_number)" class="loading-spin">
                                      <LoadingIcon />
                                  </n-icon>
                                  <n-icon v-else :class="{ 'expanded': isSeasonExpanded(s.season_number) }">
                                      <ExpandIcon />
                                  </n-icon>
                              </div>
                          </div>
                          <div v-if="isSeasonExpanded(s.season_number)" class="episodes-panel">
                              <div v-if="getSeasonInfo(s.season_number)?.overview" class="season-overview">
                                  {{ getSeasonInfo(s.season_number).overview }}
                              </div>
                              <div v-for="ep in getSeasonEpisodes(s.season_number)" :key="ep.episode" class="episode-item">
                                  <div class="ep-still" v-if="ep.still_path">
                                      <n-image :src="getPoster(ep.still_path)" object-fit="cover" preview-disabled />
                                  </div>
                                  <div class="ep-still ep-still-placeholder" v-else>
                                      <span>E{{ ep.episode }}</span>
                                  </div>
                                  <div class="ep-content">
                                      <div class="ep-header">
                                          <div class="ep-title">
                                              <span class="ep-num-badge">E{{ ep.episode }}</span>
                                              <span class="ep-name">{{ ep.name || '未命名' }}</span>
                                              <span v-if="ep.episode_type === 'finale'" class="ep-type ep-type-finale">本季大结局</span>
                                              <span v-else-if="ep.episode_type === 'mid_season'" class="ep-type ep-type-mid">季中结局</span>
                                              <span v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.exists" class="ep-type ep-type-emby">已入库</span>
                                          </div>
                                          <div class="ep-meta">
                                              <span v-if="ep.vote_average" class="ep-rating">
                                                  <n-icon size="12"><StarIcon /></n-icon>
                                                  {{ ep.vote_average.toFixed(1) }}
                                              </span>
                                              <span v-if="ep.runtime" class="ep-runtime">{{ ep.runtime }}分钟</span>
                                              <span v-if="ep.air_date" class="ep-date">{{ ep.air_date }}</span>
                                          </div>
                                      </div>
                                      <div v-if="ep.overview" class="ep-overview">{{ ep.overview }}</div>
                                      <div v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.files?.length" class="ep-emby-info">
                                          <div v-for="(file, idx) in getEpisodeEmbyInfo(s.season_number, ep.episode).files" :key="idx" class="emby-file-item">
                                              <span class="emby-filename">{{ file.name }}</span>
                                              <span v-if="file.size" class="emby-size"> · {{ formatFileSize(file.size) }}</span>
                                          </div>
                                      </div>
                                  </div>
                              </div>
                              <div v-if="getSeasonEpisodes(s.season_number).length === 0 && !isSeasonLoading(s.season_number)" class="no-episodes">
                                  暂无集信息
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
        </n-scrollbar>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
.tmdb-detail-modal { background: var(--app-bg-color); overflow: hidden; border-radius: var(--card-border-radius, 12px); }
.loading-box { padding: 40px; }

.backdrop-box { position: relative; min-height: 220px; }
.backdrop-img { position: absolute; inset: 0; background-size: cover; background-position: center; opacity: var(--opacity-tertiary); filter: blur(30px); transform: scale(1.2); }
.backdrop-gradient { position: absolute; inset: 0; background: linear-gradient(to top, var(--app-bg-color) 0%, transparent 100%); }

.header-content { position: relative; z-index: 2; padding: 30px 32px; display: flex; gap: 20px; width: 100%; }
.main-poster { 
  width: 110px; aspect-ratio: 3/4; 
  border-radius: var(--card-border-radius, 6px); 
  box-shadow: 0 8px 24px var(--shadow-heavy); 
  border: 1px solid var(--app-border-light); 
  overflow: hidden; background: var(--bg-primary); 
}
.main-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }

.info-col { flex-grow: 1; text-shadow: 0 2px 4px var(--shadow-xheavy); }
.title-row { display: flex; align-items: center; gap: 12px; }
.title { margin: 0; font-size: 26px; font-weight: 900; color: var(--text-primary); line-height: 1.2; }
.original-title { font-size: 13px; color: var(--text-tertiary); margin-bottom: 4px; }
.tagline { font-size: 14px; font-style: italic; color: var(--n-primary-color); margin-bottom: 12px; opacity: var(--opacity-primary); }
.meta-tags { margin-bottom: 15px; }
.actions { display: flex; gap: 10px; }

.body-content { padding: 30px 32px 32px 32px; }
.genres-row { margin-bottom: 16px; }
.overview-section { margin-bottom: 20px; }
.overview-section h3 { margin: 0 0 8px 0; color: var(--n-primary-color); font-size: 15px; }
.overview-text { color: var(--text-secondary); line-height: 1.6; font-size: 13px; text-align: justify; }

.cast-section { margin-bottom: 24px; }
.cast-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; display: flex; align-items: center; gap: 6px; }
.cast-scroller { display: flex; gap: 16px; padding-bottom: 8px; }
.cast-card { min-width: 80px; width: 80px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.cast-avatar { 
  width: 56px; height: 56px; 
  border-radius: 50%; overflow: hidden; 
  border: 1px solid var(--app-border-light); 
  margin-bottom: 6px; background: var(--app-surface-inner); 
}
.cast-avatar :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.actor-name { font-size: 10px; color: var(--text-tertiary); width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.seasons-section h3 { margin: 0 0 12px 0; color: var(--n-primary-color); font-size: 15px; }
.seasons-list { display: flex; flex-direction: column; gap: 12px; }
.season-item { border: 1px solid var(--app-border-light); border-radius: var(--card-border-radius, 8px); overflow: hidden; }
.season-card { 
  display: flex; align-items: center; gap: 12px; padding: 12px; 
  cursor: pointer; transition: background 0.2s;
}
.season-card:hover { background: var(--app-surface-inner); }
.s-poster { width: 50px; aspect-ratio: 2/3; border-radius: var(--button-border-radius, 4px); overflow: hidden; background: var(--bg-primary); flex-shrink: 0; }
.s-poster :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.s-info { flex: 1; min-width: 0; }
.s-name-row { display: flex; align-items: center; gap: 8px; }
.s-name { font-size: 13px; font-weight: bold; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-ep { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }
.s-expand-icon { color: var(--text-tertiary); transition: transform 0.3s; }
.s-expand-icon .expanded { transform: rotate(180deg); }
.loading-spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.episodes-panel { 
  background: var(--app-surface-inner); 
  border-top: 1px solid var(--app-border-light); 
  padding: 12px; 
  max-height: 400px; 
  overflow-y: auto; 
}
.season-overview { 
  font-size: 12px; color: var(--text-secondary); line-height: 1.6; 
  padding: 10px 12px; margin-bottom: 12px; 
  background: var(--app-bg-color); border-radius: 6px; 
  border-left: 3px solid var(--n-primary-color);
}
.episode-item { 
  display: flex; gap: 12px; 
  padding: 10px; border-radius: 6px; 
  transition: background 0.2s; 
  margin-bottom: 8px;
}
.episode-item:last-child { margin-bottom: 0; }
.episode-item:hover { background: var(--app-bg-color); }
.ep-still { 
  width: 160px; aspect-ratio: 16/9; 
  border-radius: 4px; overflow: hidden; 
  flex-shrink: 0; background: var(--bg-primary); 
}
.ep-still :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.ep-still-placeholder { 
  display: flex; align-items: center; justify-content: center; 
  color: var(--text-tertiary); font-size: 18px; font-weight: bold; 
  background: var(--app-surface-inner); 
}
.ep-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.ep-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.ep-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ep-num-badge { 
  font-size: 10px; font-weight: bold; color: var(--n-primary-color); 
  padding: 2px 6px; background: var(--n-primary-color-supply); 
  border-radius: 4px; flex-shrink: 0; 
}
.ep-name { font-size: 13px; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ep-type { font-size: 9px; font-weight: bold; padding: 2px 6px; border-radius: 3px; flex-shrink: 0; }
.ep-type-finale { background: linear-gradient(135deg, #ff6b6b, #ee5a5a); color: #fff; }
.ep-type-mid { background: linear-gradient(135deg, #ffa94d, #ff922b); color: #fff; }
.ep-type-emby { background: linear-gradient(135deg, #51cf66, #40c057); color: #fff; }
.ep-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.ep-rating { display: flex; align-items: center; gap: 2px; font-size: 11px; color: var(--color-warning); }
.ep-runtime { font-size: 11px; color: var(--text-tertiary); }
.ep-date { font-size: 11px; color: var(--text-tertiary); }
.ep-overview { 
  font-size: 12px; color: var(--text-secondary); line-height: 1.5; 
}
.ep-emby-info { 
  font-size: 11px; color: var(--text-tertiary); 
  padding: 6px 8px; margin-top: 4px; 
  background: var(--app-surface-inner); border-radius: 4px; 
  border-left: 2px solid #51cf66;
}
.emby-file-item { padding: 4px 0; border-bottom: 1px dashed var(--app-border-light); }
.emby-file-item:last-child { border-bottom: none; padding-bottom: 0; }
.emby-file-item:first-child { padding-top: 0; }
.emby-filename { word-break: break-all; }
.emby-size { color: var(--text-secondary); font-weight: 500; }
.no-episodes { text-align: center; color: var(--text-tertiary); font-size: 12px; padding: 20px; }
</style>