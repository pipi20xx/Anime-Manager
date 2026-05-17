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
  ArrowBackOutlined as BackIcon,
  ExpandMoreOutlined as ExpandIcon,
  RefreshOutlined as LoadingIcon
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
  openImdb,
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
  getSeasonLibraryStatus,
  recommendations,
  handleRecClick
} = useTmdbDetail(props, emit)
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="width: 100%; height: 100vh; margin: 0; border-radius: 0;">
    <div class="mobile-detail-page">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="300px" width="100%" />
      </div>

      <div v-else-if="detail" class="content-wrapper">
        <!-- Sticky Header for Back Button -->
        <div class="sticky-header">
           <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="handleClose" class="back-btn">
             <template #icon><n-icon><BackIcon /></n-icon></template>
           </n-button>
        </div>

        <n-scrollbar style="flex: 1;">
          <!-- Top Cover Section -->
          <div class="hero-section">
             <div class="backdrop-layer" :style="{ backgroundImage: `url(${getBackdrop(detail.backdrop_path)})` }"></div>
             <div class="gradient-overlay"></div>
             
             <div class="hero-content">
                <div class="poster-wrapper">
                   <n-image :src="getPoster(detail.poster_path)" object-fit="cover" class="hero-poster" />
                </div>
                <div class="hero-info">
                   <div class="hero-title-row">
                      <h1 class="hero-title">{{ detail.title || detail.name }}</h1>
                      <n-tag v-if="isInLibrary" type="success" size="tiny" round>
                         已入库
                      </n-tag>
                   </div>
                   <div class="hero-meta">
                      <n-tag type="warning" size="tiny" round :bordered="false" class="rating-tag">
                         <template #icon><n-icon><StarIcon/></n-icon></template>
                         {{ detail.vote_average?.toFixed(1) }}
                      </n-tag>
                      <span class="meta-date">{{ detail.release_date || detail.first_air_date }}</span>
                      <span v-if="detail.number_of_seasons" class="meta-seasons">{{ detail.number_of_seasons }}季</span>
                      <span v-if="detail.number_of_episodes" class="meta-episodes">{{ detail.number_of_episodes }}集</span>
                   </div>
                   <div class="hero-info-grid">
                      <div class="info-row" @click="openExternal">
                         <span class="info-label">TMDB ID</span>
                         <span class="info-val link">{{ detail.id }}</span>
                      </div>
                      <div v-if="detail.imdb_id" class="info-row" @click="openImdb(detail.imdb_id)">
                         <span class="info-label">IMDb ID</span>
                         <span class="info-val link">{{ detail.imdb_id }}</span>
                      </div>
                      <div v-if="detail.status" class="info-row">
                         <span class="info-label">状态</span>
                         <span class="info-val">{{ detail.status }}</span>
                      </div>
                      <div v-if="detail.origin_country?.length" class="info-row">
                         <span class="info-label">地区</span>
                         <span class="info-val">{{ detail.origin_country.join(', ') }}</span>
                      </div>
                      <div v-if="detail.original_language" class="info-row">
                         <span class="info-label">语言</span>
                         <span class="info-val">{{ detail.original_language.toUpperCase() }}</span>
                      </div>
                   </div>
                </div>
             </div>
          </div>

          <!-- Actions Bar -->
          <div class="actions-bar">
             <n-button block type="primary" :secondary="isSubscribed" @click="handleSubscribe">
                <template #icon><n-icon><SubIcon/></n-icon></template>
                {{ isSubscribed ? '已订阅' : '订阅' }}
             </n-button>
             <n-button block style="margin-top: var(--m-spacing-md);" v-bind="getButtonStyle('secondary')" @click="handleSearch">
                <template #icon><n-icon><SearchIcon/></n-icon></template> 搜资源
             </n-button>
          </div>

          <!-- Body Content -->
          <div class="detail-body">
             <div class="genres-scroll" v-if="displayGenres.length">
                <n-tag v-for="g in displayGenres" :key="g" size="small" round :bordered="false" class="genre-tag">{{ g }}</n-tag>
             </div>

             <div class="section">
                <h3>简介</h3>
                <p class="overview">{{ detail.overview || '暂无简介' }}</p>
             </div>

             <div class="section" v-if="detail.cast?.length">
                <h3>演职员</h3>
                <div class="h-scroller">
                   <div v-for="c in detail.cast" :key="c.actor + c.character" class="cast-item">
                      <div class="avatar">
                         <img :src="getPoster(c.image)" loading="lazy" />
                      </div>
                      <div class="name">{{ c.actor }}</div>
                      <div class="char">{{ c.character }}</div>
                   </div>
                </div>
             </div>

             <div class="section" v-if="detail.seasons?.length">
                <h3>季度</h3>
                <div class="seasons-list">
                   <div v-for="s in detail.seasons" :key="s.id" class="season-block">
                      <div class="season-header" @click="toggleSeason(s.season_number)">
                         <div class="season-poster">
                            <img :src="getPoster(s.poster_path)" loading="lazy" />
                         </div>
                         <div class="season-info">
                            <div class="s-name-row">
                               <span class="s-name">{{ s.name }}</span>
                               <n-tag v-if="getSeasonLibraryStatus(s.season_number)?.exists" type="success" size="tiny" round>
                                  已入库
                               </n-tag>
                            </div>
                            <div class="s-ep">{{ s.episode_count }} 集</div>
                         </div>
                         <div class="expand-icon">
                            <n-icon v-if="isSeasonLoading(s.season_number)" class="loading-spin">
                               <LoadingIcon />
                            </n-icon>
                            <n-icon v-else :class="{ 'expanded': isSeasonExpanded(s.season_number) }">
                               <ExpandIcon />
                            </n-icon>
                         </div>
                      </div>
                      <div v-if="isSeasonExpanded(s.season_number)" class="episodes-list">
                         <div v-if="getSeasonInfo(s.season_number)?.overview" class="season-overview">
                            {{ getSeasonInfo(s.season_number).overview }}
                         </div>
                         <div v-for="ep in getSeasonEpisodes(s.season_number)" :key="ep.episode" class="ep-item">
                            <div class="ep-still" v-if="ep.still_path">
                               <img :src="getPoster(ep.still_path)" loading="lazy" />
                            </div>
                            <div class="ep-still ep-still-placeholder" v-else>
                               <span>E{{ ep.episode }}</span>
                            </div>
                            <div class="ep-content">
                               <div class="ep-header">
                                  <span class="ep-num-badge">E{{ ep.episode }}</span>
                                  <span class="ep-name">{{ ep.name || '未命名' }}</span>
                                  <span v-if="ep.episode_type === 'finale'" class="ep-type ep-type-finale">大结局</span>
                                  <span v-else-if="ep.episode_type === 'mid_season'" class="ep-type ep-type-mid">季中</span>
                                  <span v-if="getEpisodeEmbyInfo(s.season_number, ep.episode)?.exists" class="ep-type ep-type-emby">已入库</span>
                               </div>
                               <div class="ep-meta">
                                  <span v-if="ep.vote_average" class="ep-rating">
                                     <n-icon size="10"><StarIcon /></n-icon>
                                     {{ ep.vote_average.toFixed(1) }}
                                  </span>
                                  <span v-if="ep.runtime">{{ ep.runtime }}分钟</span>
                                  <span v-if="ep.air_date">{{ ep.air_date }}</span>
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
                         <div v-if="getSeasonEpisodes(s.season_number).length === 0 && !isSeasonLoading(s.season_number)" class="no-eps">
                            暂无集信息
                         </div>
                      </div>
                   </div>
                </div>
             </div>

             <div v-if="recommendations.length" class="section">
                <h3>相关推荐</h3>
                <div class="rec-scroll">
                   <div v-for="rec in recommendations" :key="rec.id" class="rec-card" @click="handleRecClick(rec)">
                      <div class="rec-poster">
                         <img :src="getPoster(rec.poster_path)" loading="lazy" />
                      </div>
                      <div class="rec-title">{{ rec.title || rec.name }}</div>
                      <div class="rec-meta">
                         <span v-if="rec.vote_average" class="rec-rating">⭐ {{ rec.vote_average.toFixed(1) }}</span>
                         <span class="rec-year">{{ (rec.release_date || rec.first_air_date || '').slice(0, 4) }}</span>
                      </div>
                   </div>
                </div>
             </div>
          </div>
          
          <div style="height: var(--m-spacing-2xl);"></div> <!-- Bottom spacer -->
        </n-scrollbar>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.mobile-detail-page { background: var(--app-bg-color); height: 100%; display: flex; flex-direction: column; position: relative; }
.loading-box { padding: var(--m-spacing-3xl); }
.content-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.sticky-header { position: absolute; top: var(--m-spacing-lg); left: var(--m-spacing-lg); z-index: 10; }
.back-btn { background: var(--bg-surface) !important; color: var(--text-primary) !important; border: none; backdrop-filter: blur(4px); }

.hero-section { position: relative; height: 320px; display: flex; align-items: flex-end; }
.backdrop-layer { position: absolute; inset: 0; background-size: cover; background-position: center; opacity: var(--opacity-tertiary); }
.gradient-overlay { position: absolute; inset: 0; background: linear-gradient(to bottom, transparent 0%, var(--app-bg-color) 100%); }

.hero-content { position: relative; z-index: 2; padding: 0 var(--m-spacing-xl) var(--m-spacing-xl); display: flex; gap: var(--m-spacing-md); align-items: flex-end; width: 100%; }
.poster-wrapper { width: 100px; flex-shrink: 0; border-radius: var(--m-radius-md); overflow: hidden; box-shadow: var(--shadow-lg); border: 1px solid rgba(255,255,255, var(--border-medium-alpha)); }
.hero-poster :deep(img) { width: 100%; display: block; aspect-ratio: 2/3; object-fit: cover; }

.hero-info { flex: 1; min-width: 0; margin-bottom: var(--m-spacing-xs); }
.hero-title-row { display: flex; align-items: center; gap: var(--m-spacing-sm); flex-wrap: wrap; }
.hero-title { margin: 0; font-size: var(--m-text-2xl); font-weight: 900; color: var(--text-primary); line-height: 1.2; text-shadow: 0 2px 4px var(--shadow-xheavy); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.hero-meta { display: flex; align-items: center; gap: var(--m-spacing-sm); margin-top: var(--m-spacing-sm); flex-wrap: wrap; }
.meta-date { font-size: var(--m-text-sm); color: var(--text-secondary); text-shadow: 0 1px 2px var(--shadow-xheavy); }
.meta-seasons, .meta-episodes { font-size: var(--m-text-xs); color: var(--text-tertiary); text-shadow: 0 1px 2px var(--shadow-xheavy); }
.rating-tag { background: var(--color-warning); color: var(--text-primary); font-weight: bold; }

.hero-info-grid { display: flex; flex-wrap: wrap; gap: var(--m-spacing-sm) var(--m-spacing-md); margin-top: var(--m-spacing-md); }
.info-row { display: flex; align-items: center; gap: var(--m-spacing-xs); }
.info-label { font-size: var(--m-text-xs); color: var(--text-tertiary); }
.info-val { font-size: var(--m-text-xs); color: var(--text-primary); font-weight: 500; }
.info-val.link { color: var(--n-primary-color); }

.actions-bar { padding: 0 var(--m-spacing-xl) var(--m-spacing-xl); }

.detail-body { padding: 0 var(--m-spacing-xl); }
.genres-scroll { display: flex; gap: var(--m-spacing-sm); overflow-x: auto; padding-bottom: var(--m-spacing-md); margin-bottom: var(--m-spacing-sm); }
.genre-tag { background: var(--bg-surface); color: var(--text-secondary); }

.section { margin-bottom: var(--m-spacing-2xl); }
.section h3 { margin: 0 0 var(--m-spacing-sm); font-size: var(--m-text-lg); font-weight: bold; color: var(--text-primary); }
.overview { font-size: var(--m-text-base); line-height: 1.6; color: var(--text-secondary); text-align: justify; }

.h-scroller { display: flex; gap: var(--m-spacing-md); overflow-x: auto; padding-bottom: var(--m-spacing-xs); }
.cast-item { width: 70px; flex-shrink: 0; text-align: center; }
.cast-item .avatar { width: 60px; height: 60px; border-radius: var(--m-radius-full); overflow: hidden; margin: 0 auto var(--m-spacing-xs); background: var(--bg-primary); }
.cast-item .avatar img { width: 100%; height: 100%; object-fit: cover; }
.cast-item .name { font-size: var(--m-text-xs); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.cast-item .char { font-size: var(--m-text-xs); color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.seasons-list { display: flex; flex-direction: column; gap: var(--m-spacing-md); }
.season-block { border: 1px solid var(--app-border-light); border-radius: var(--m-radius-md); overflow: hidden; }
.season-header { display: flex; align-items: center; gap: var(--m-spacing-md); padding: var(--m-spacing-md); cursor: pointer; background: var(--bg-surface); }
.season-poster { width: 45px; aspect-ratio: 2/3; border-radius: var(--m-radius-sm); overflow: hidden; flex-shrink: 0; background: var(--bg-primary); }
.season-poster img { width: 100%; height: 100%; object-fit: cover; }
.season-info { flex: 1; min-width: 0; }
.season-info .s-name-row { display: flex; align-items: center; gap: var(--m-spacing-sm); }
.season-info .s-name { font-size: var(--m-text-sm); font-weight: bold; color: var(--text-primary); }
.season-info .s-ep { font-size: var(--m-text-xs); color: var(--text-tertiary); }
.expand-icon { color: var(--text-tertiary); transition: transform 0.3s; }
.expand-icon .expanded { transform: rotate(180deg); }
.loading-spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.episodes-list { background: var(--app-bg-color); border-top: 1px solid var(--app-border-light); padding: var(--m-spacing-sm); max-height: 350px; overflow-y: auto; }
.season-overview { 
  font-size: var(--m-text-xs); color: var(--text-secondary); line-height: 1.5; 
  padding: var(--m-spacing-sm); margin-bottom: var(--m-spacing-sm); 
  background: var(--bg-surface); border-radius: var(--m-radius-xs); 
  border-left: 2px solid var(--n-primary-color);
}
.ep-item { display: flex; gap: var(--m-spacing-sm); padding: var(--m-spacing-sm); border-radius: var(--m-radius-sm); margin-bottom: var(--m-spacing-xs); }
.ep-item:last-child { margin-bottom: 0; }
.ep-item:active { background: var(--bg-surface); }
.ep-still { width: 100px; aspect-ratio: 16/9; border-radius: var(--m-radius-xs); overflow: hidden; flex-shrink: 0; background: var(--bg-primary); }
.ep-still img { width: 100%; height: 100%; object-fit: cover; }
.ep-still-placeholder { display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); font-size: var(--m-text-sm); font-weight: bold; background: var(--bg-surface); }
.ep-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.ep-header { display: flex; align-items: center; gap: 6px; }
.ep-num-badge { font-size: 9px; font-weight: bold; color: var(--n-primary-color); padding: 1px 4px; background: var(--n-primary-color-supply); border-radius: 2px; flex-shrink: 0; }
.ep-name { font-size: var(--m-text-sm); font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ep-type { font-size: 8px; font-weight: bold; padding: 1px 4px; border-radius: 2px; flex-shrink: 0; }
.ep-type-finale { background: linear-gradient(135deg, #ff6b6b, #ee5a5a); color: #fff; }
.ep-type-mid { background: linear-gradient(135deg, #ffa94d, #ff922b); color: #fff; }
.ep-type-emby { background: linear-gradient(135deg, #51cf66, #40c057); color: #fff; }
.ep-meta { display: flex; align-items: center; gap: 6px; font-size: var(--m-text-xs); color: var(--text-tertiary); }
.ep-rating { display: flex; align-items: center; gap: 2px; color: var(--color-warning); }
.ep-overview { font-size: var(--m-text-xs); color: var(--text-secondary); line-height: 1.4; }
.ep-emby-info { 
  font-size: var(--m-text-xs); color: var(--text-tertiary); 
  padding: var(--m-spacing-xs); margin-top: 4px; 
  background: var(--bg-surface); border-radius: var(--m-radius-xs); 
  border-left: 2px solid #51cf66;
}
.emby-file-item { padding: 3px 0; border-bottom: 1px dashed var(--app-border-light); }
.emby-file-item:last-child { border-bottom: none; padding-bottom: 0; }
.emby-file-item:first-child { padding-top: 0; }
.emby-filename { word-break: break-all; }
.emby-size { color: var(--text-secondary); font-weight: 500; }
.no-eps { text-align: center; color: var(--text-tertiary); font-size: var(--m-text-sm); padding: var(--m-spacing-xl); }

.rec-scroll { display: flex; gap: var(--m-spacing-md); overflow-x: auto; padding-bottom: var(--m-spacing-xs); }
.rec-card { width: 100px; flex-shrink: 0; }
.rec-poster { width: 100px; aspect-ratio: 2/3; border-radius: var(--m-radius-sm); overflow: hidden; background: var(--bg-primary); }
.rec-poster img { width: 100%; height: 100%; object-fit: cover; }
.rec-title { font-size: var(--m-text-xs); font-weight: 600; color: var(--text-primary); margin-top: var(--m-spacing-xs); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rec-meta { display: flex; align-items: center; gap: var(--m-spacing-xs); margin-top: 2px; }
.rec-rating { font-size: 10px; color: var(--color-warning); }
.rec-year { font-size: 10px; color: var(--text-tertiary); }
</style>
