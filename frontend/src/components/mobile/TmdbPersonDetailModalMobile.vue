<script setup lang="ts">
import { ref } from 'vue'
import { 
  NModal, NCard, NImage, NSpace, NTag, NIcon, NScrollbar, NSkeleton, NButton
} from 'naive-ui'
import {
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  LinkOutlined as LinkIcon,
  PersonOutlined as PersonIcon,
  MovieOutlined as MovieIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import { useTmdbPersonDetail } from '../../composables/components/useTmdbPersonDetail'
import { getButtonStyle } from '../../composables/useButtonStyles'
import TmdbDetailModalMobile from './TmdbDetailModalMobile.vue'

const props = defineProps<{
  show: boolean
  personId: string | number
  initialData?: any 
}>()

const emit = defineEmits(['update:show'])

const {
  loading,
  detail,
  credits,
  getProfile,
  getPoster,
  handleClose,
  openExternal,
  openImdb,
  genderText,
  calculateAge,
  renderReady
} = useTmdbPersonDetail(props, emit)

const tmdbDetailShow = ref(false)
const selectedTmdbId = ref<string | number | null>(null)
const selectedMediaType = ref<'movie' | 'tv'>('tv')
const selectedInitialData = ref<any>(null)

const openTmdbDetail = (item: any) => {
  if (!item?.id) return
  selectedTmdbId.value = item.id
  selectedMediaType.value = item.media_type || 'tv'
  selectedInitialData.value = item
  tmdbDetailShow.value = true
}
</script>

<template>
  <n-modal :show="show" @update:show="handleClose" style="width: 100%; height: 100vh; margin: 0; border-radius: 0;" display-directive="show">
    <div class="mobile-detail-page">
      <div v-if="loading && !detail" class="loading-box">
          <n-skeleton height="300px" width="100%" />
      </div>

      <div v-else-if="detail" class="content-wrapper">
        <div class="sticky-header">
           <n-button v-bind="getButtonStyle('iconPrimary')" size="small" @click="handleClose" class="back-btn">
             <template #icon><n-icon><BackIcon /></n-icon></template>
           </n-button>
        </div>

        <n-scrollbar style="flex: 1;">
          <div class="hero-section">
             <div class="gradient-overlay"></div>
             
             <div class="hero-content">
                <div class="profile-wrapper">
                   <n-image :src="getProfile(detail.profile_path)" object-fit="cover" class="hero-profile" />
                </div>
                <div class="hero-info">
                   <div class="hero-title-row">
                      <h1 class="hero-title">{{ detail.name }}</h1>
                      <n-tag v-if="detail.known_for_department" type="info" size="tiny" round>
                         {{ detail.known_for_department }}
                      </n-tag>
                   </div>
                   <div v-if="detail.original_name && detail.original_name !== detail.name" class="hero-original">
                     {{ detail.original_name }}
                   </div>
                   <div class="hero-meta">
                      <n-tag type="warning" size="tiny" round :bordered="false" class="rating-tag">
                         <template #icon><n-icon><StarIcon/></n-icon></template>
                         {{ detail.popularity?.toFixed(1) }}
                      </n-tag>
                      <span class="meta-gender">{{ genderText(detail.gender) }}</span>
                      <span v-if="detail.birthday" class="meta-age">{{ calculateAge(detail.birthday, detail.deathday) }}岁</span>
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
                      <div v-if="detail.birthday" class="info-row">
                         <span class="info-label">生日</span>
                         <span class="info-val">{{ detail.birthday }}</span>
                      </div>
                      <div v-if="detail.deathday" class="info-row">
                         <span class="info-label">逝世</span>
                         <span class="info-val">{{ detail.deathday }}</span>
                      </div>
                      <div v-if="detail.place_of_birth" class="info-row">
                         <span class="info-label">出生地</span>
                         <span class="info-val">{{ detail.place_of_birth }}</span>
                      </div>
                   </div>
                </div>
             </div>
          </div>

          <div class="detail-body">
             <div v-if="detail.also_known_as?.length" class="also-known-section">
                <span class="also-label">别名:</span>
                <span class="also-values">{{ detail.also_known_as.slice(0, 5).join(' / ') }}</span>
             </div>

             <div class="section" v-if="detail.biography">
                <h3>简介</h3>
                <p class="biography">{{ detail.biography }}</p>
             </div>

             <div class="section" v-if="detail.known_for?.length">
                <h3>知名作品</h3>
                <div class="h-scroller">
                   <div v-for="c in detail.known_for" :key="c.id" class="credit-item" @click="openTmdbDetail(c)">
                      <div class="poster">
                         <img :src="getPoster(c.poster_path)" loading="lazy" />
                      </div>
                      <div class="info">
                         <div class="title">{{ c.title || c.name }}</div>
                         <div class="year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
                      </div>
                   </div>
                </div>
             </div>

             <div class="section" v-if="credits.cast?.length">
                <h3>参演作品</h3>
                <div class="h-scroller">
                   <div v-for="c in credits.cast" :key="c.id" class="credit-item" @click="openTmdbDetail(c)">
                      <div class="poster">
                         <img :src="getPoster(c.poster_path)" loading="lazy" />
                      </div>
                      <div class="info">
                         <div class="title">{{ c.title || c.name }}</div>
                         <div class="character" v-if="c.character">{{ c.character }}</div>
                         <div class="year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
                      </div>
                   </div>
                </div>
             </div>

             <div class="section" v-if="credits.crew?.length">
                <h3>制作作品</h3>
                <div class="h-scroller">
                   <div v-for="c in credits.crew" :key="c.id + c.job" class="credit-item" @click="openTmdbDetail(c)">
                      <div class="poster">
                         <img :src="getPoster(c.poster_path)" loading="lazy" />
                      </div>
                      <div class="info">
                         <div class="title">{{ c.title || c.name }}</div>
                         <div class="job" v-if="c.job">{{ c.job }}</div>
                         <div class="year">{{ (c.release_date || c.first_air_date || '').slice(0, 4) }}</div>
                      </div>
                   </div>
                </div>
             </div>
          </div>
          
          <div style="height: var(--m-spacing-2xl);"></div>
        </n-scrollbar>
      </div>
    </div>
  </n-modal>

  <TmdbDetailModalMobile 
    v-model:show="tmdbDetailShow" 
    :tmdb-id="selectedTmdbId || 0" 
    :media-type="selectedMediaType"
    :initial-data="selectedInitialData"
  />
</template>

<style scoped>
.mobile-detail-page { background: var(--app-bg-color); height: 100%; display: flex; flex-direction: column; position: relative; }
.loading-box { padding: var(--m-spacing-3xl); }
.content-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.sticky-header { position: absolute; top: var(--m-spacing-lg); left: var(--m-spacing-lg); z-index: 10; }
.back-btn { background: var(--bg-surface) !important; color: var(--text-primary) !important; border: none; backdrop-filter: blur(4px); }

.hero-section { position: relative; min-height: 280px; display: flex; align-items: flex-end; }
.gradient-overlay { position: absolute; inset: 0; background: linear-gradient(to bottom, transparent 0%, var(--app-bg-color) 100%); }

.hero-content { position: relative; z-index: 2; padding: 0 var(--m-spacing-xl) var(--m-spacing-xl); display: flex; gap: var(--m-spacing-md); align-items: flex-end; width: 100%; }
.profile-wrapper { width: 100px; flex-shrink: 0; border-radius: var(--m-radius-md); overflow: hidden; box-shadow: var(--shadow-lg); border: 1px solid rgba(255,255,255, var(--border-medium-alpha)); }
.hero-profile :deep(img) { width: 100%; display: block; aspect-ratio: 2/3; object-fit: cover; }

.hero-info { flex: 1; min-width: 0; margin-bottom: var(--m-spacing-xs); }
.hero-title-row { display: flex; align-items: center; gap: var(--m-spacing-sm); flex-wrap: wrap; }
.hero-title { margin: 0; font-size: var(--m-text-xl); font-weight: 900; color: var(--text-primary); line-height: 1.2; text-shadow: 0 2px 4px var(--shadow-xheavy); }
.hero-original { font-size: var(--m-text-sm); color: var(--text-tertiary); margin-top: var(--m-spacing-xs); }
.hero-meta { display: flex; align-items: center; gap: var(--m-spacing-sm); margin-top: var(--m-spacing-sm); flex-wrap: wrap; }
.meta-gender, .meta-age { font-size: var(--m-text-xs); color: var(--text-secondary); text-shadow: 0 1px 2px var(--shadow-xheavy); }
.rating-tag { background: var(--color-warning); color: var(--text-primary); font-weight: bold; }

.hero-info-grid { display: flex; flex-wrap: wrap; gap: var(--m-spacing-sm) var(--m-spacing-md); margin-top: var(--m-spacing-md); }
.info-row { display: flex; align-items: center; gap: var(--m-spacing-xs); }
.info-label { font-size: var(--m-text-xs); color: var(--text-tertiary); }
.info-val { font-size: var(--m-text-xs); color: var(--text-primary); font-weight: 500; }
.info-val.link { color: var(--n-primary-color); }

.detail-body { padding: 0 var(--m-spacing-xl); }
.also-known-section { font-size: var(--m-text-xs); color: var(--text-tertiary); margin-bottom: var(--m-spacing-lg); padding: var(--m-spacing-sm); background: var(--bg-surface); border-radius: var(--m-radius-sm); }
.also-label { margin-right: var(--m-spacing-xs); }
.also-values { color: var(--text-secondary); }

.section { margin-bottom: var(--m-spacing-2xl); }
.section h3 { margin: 0 0 var(--m-spacing-sm); font-size: var(--m-text-lg); font-weight: bold; color: var(--text-primary); }
.biography { font-size: var(--m-text-base); line-height: 1.6; color: var(--text-secondary); text-align: justify; white-space: pre-wrap; }

.h-scroller { display: flex; gap: var(--m-spacing-md); overflow-x: auto; padding-bottom: var(--m-spacing-xs); }
.credit-item { width: 90px; flex-shrink: 0; cursor: pointer; }
.credit-item:active { opacity: 0.7; }
.credit-item .poster { width: 90px; aspect-ratio: 2/3; border-radius: var(--m-radius-sm); overflow: hidden; margin-bottom: var(--m-spacing-xs); background: var(--bg-primary); }
.credit-item .poster img { width: 100%; height: 100%; object-fit: cover; }
.credit-item .info { text-align: center; }
.credit-item .title { font-size: var(--m-text-xs); color: var(--text-primary); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.credit-item .character { font-size: 10px; color: var(--n-primary-color); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.credit-item .job { font-size: 10px; color: var(--n-warning-color); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.credit-item .year { font-size: 10px; color: var(--text-tertiary); margin-top: 2px; }
</style>
