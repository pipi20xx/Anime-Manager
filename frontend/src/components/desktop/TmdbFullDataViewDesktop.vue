<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import AppGlassCard from '../AppGlassCard.vue'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import AppSearchField from '../AppSearchField.vue'
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import {
  NSpace, NButton, NIcon, NGrid, NGi, NImage,
  NEmpty, NSpin, NForm, NFormItem, useDialog,
  NTabs, NTabPane, NCollapse, NCollapseItem
} from 'naive-ui'
import {
  DeleteOutlined as DeleteIcon,
  SearchOutlined as SearchIcon,
  CloudSyncOutlined as SytmdbIcon,
  AddOutlined as AddIcon,
  RefreshOutlined as RefreshIcon,
  StarOutlined as StarIcon,
  CalendarMonthOutlined as DateIcon,
  PersonOutlined as PersonIcon,
  CodeOutlined as CodeIcon
} from '@vicons/material'
import { useTmdbData } from '../../composables/views/useTmdbData'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { STATUS_MAP } from '../../composables/useTmdbDisplayMaps'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

// ===== 映射缓存 (国家/语言/流派) =====
const mappingCache = ref<Record<string, Record<string, string>>>({
  countries: {},
  languages: {},
  genres: {},
  keywords: {}
})
let mappingLoaded = false

const fetchMappingCache = async () => {
  if (mappingLoaded) return
  try {
    const [countries, languages, genres, keywords] = await Promise.all([
      fetch(`${API_BASE}/api/user_mapping/search?type=country`).then(r => r.json()),
      fetch(`${API_BASE}/api/user_mapping/search?type=language`).then(r => r.json()),
      fetch(`${API_BASE}/api/user_mapping/search?type=genre`).then(r => r.json()),
      fetch(`${API_BASE}/api/user_mapping/search?type=keyword`).then(r => r.json())
    ])
    mappingCache.value = {
      countries: Object.fromEntries(countries.map((c: any) => [String(c.id).toUpperCase(), c.name])),
      languages: Object.fromEntries(languages.map((l: any) => [String(l.id).toLowerCase(), l.name])),
      genres: Object.fromEntries(genres.map((g: any) => [String(g.id), g.name])),
      keywords: Object.fromEntries(keywords.map((k: any) => [String(k.id), k.name]))
    }
    mappingLoaded = true
  } catch (e) {
    console.error('获取映射缓存失败', e)
  }
}

// TMDB 别名类型映射
const ALT_TITLE_TYPE_MAP: Record<string, string> = {
  '1': '短标题',
  '2': '现代标题',
  '3': '翻译名',
  '4': '音译名',
  '5': '工作标题',
  '6': '别名'
}

// ===== 翻译辅助函数 =====
const translateStatus = (status: string) => {
  if (!status) return ''
  return STATUS_MAP[status] || status
}

const translateCountry = (code: string) => {
  if (!code) return ''
  return mappingCache.value.countries[code.toUpperCase()] || code
}

const translateLanguage = (code: string) => {
  if (!code) return ''
  return mappingCache.value.languages[code.toLowerCase()] || code
}

const translateAltType = (type: string) => {
  if (!type) return ''
  return ALT_TITLE_TYPE_MAP[type] || type
}

const translateGenreName = (genreId: string | number, fallbackName: string) => {
  const mapped = mappingCache.value.genres[String(genreId)]
  return mapped || fallbackName || String(genreId)
}

const translateKeywordName = (keywordId: string | number, fallbackName: string) => {
  const mapped = mappingCache.value.keywords[String(keywordId)]
  return mapped || fallbackName || String(keywordId)
}

const dialog = useDialog()
const showRefreshModal = ref(false)
const refreshForm = ref({
  olderThanDays: null as number | null,
  year: null as number | null,
  mediaType: null as string | null
})

const {
  browserData,
  browserTotal,
  browserSearch,
  browserLoading,
  browserHasMore,
  showEditModal,
  isEditing,
  editForm,
  fetchBrowserData,
  handleBrowserSearch,
  openCreate,
  openEdit,
  saveMetadata,
  deleteMetadata,
  handleSyncSytmdb,
  handleRefreshAll,
  handleRefreshSingle,
  refreshSingleId
} = useTmdbData()

const handleExecuteRefresh = () => {
  dialog.warning({
    title: '确认全量刷新',
    content: '确定要执行全量刷新吗？此操作将在后台异步进行。',
    positiveText: '确认刷新',
    negativeText: '取消',
    onPositiveClick: () => executeRefresh()
  })
}

const executeRefresh = () => {
  const options: { olderThanDays?: number; year?: number; mediaType?: string } = {}
  if (refreshForm.value.olderThanDays) options.olderThanDays = refreshForm.value.olderThanDays
  if (refreshForm.value.year) options.year = refreshForm.value.year
  if (refreshForm.value.mediaType) options.mediaType = refreshForm.value.mediaType
  handleRefreshAll(options)
  showRefreshModal.value = false
  refreshForm.value = { olderThanDays: null, year: null, mediaType: null }
}

const getImg = (path: string) => {
  if (!path) return ''
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `${API_BASE}/api/system/img?path=/${parts[parts.length - 1]}`
  }
  if (!path.startsWith('http')) return `${API_BASE}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  return path
}

const openUrl = (url: string) => {
  if (url) window.open(url, '_blank')
}

// 编辑弹窗 Tab 控制
const editTab = ref('edit')
watch(showEditModal, (val) => {
  if (val) {
    editTab.value = 'edit'
    fetchMappingCache()
  }
})

// 完整数据 (full_data JSONB)
const fullData = computed<any>(() => {
  const raw = editForm.full_data
  if (!raw) return null
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return null }
  }
  return raw
})

const fullDataJson = computed(() => {
  return fullData.value ? JSON.stringify(fullData.value, null, 2) : ''
})

// 全语言翻译标题 (translations)
const translationList = computed(() => {
  if (!fullData.value) return []
  const translations = fullData.value.translations?.translations || []
  return translations
    .map((tr: any) => ({
      country: tr.iso_3166_1 || '',
      lang: tr.iso_639_1 || '',
      langName: tr.name || tr.english_name || '',
      title: tr.data?.title || tr.data?.name || '',
      overview: tr.data?.overview || ''
    }))
    .filter((t: any) => t.title)
})

// 全语言别名 (alternative_titles)
const altTitleList = computed(() => {
  if (!fullData.value) return []
  const alt = fullData.value.alternative_titles
  const list = alt?.titles || alt?.results || []
  return list
    .map((a: any) => ({
      country: a.iso_3166_1 || '',
      title: a.title || a.name || '',
      type: a.type || ''
    }))
    .filter((t: any) => t.title)
})

// 演员 (credits.cast)
const castList = computed(() => {
  if (!fullData.value) return []
  const cast = fullData.value.credits?.cast || []
  return cast.map((c: any) => ({
    id: c.id,
    name: c.name || '',
    character: c.character || '',
    profilePath: c.profile_path || ''
  }))
})

// 关键词 (keywords)
const keywordList = computed(() => {
  if (!fullData.value) return []
  const kwRaw = fullData.value.keywords || {}
  const list = kwRaw.keywords || kwRaw.results || []
  return list.map((k: any) => ({
    id: k.id,
    name: translateKeywordName(k.id, k.name)
  }))
})

// 无限滚动
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const setupObserver = () => {
  cleanupObserver()
  nextTick(() => {
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !browserLoading.value && browserHasMore.value) {
          fetchBrowserData(true)
        }
      },
      { rootMargin: '300px' }
    )
    observer.observe(el)
  })
}

const cleanupObserver = () => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
}

// 搜索时重新挂载 observer
watch(() => browserData.value.length, () => {
  if (browserHasMore.value) {
    setupObserver()
  }
})

onBeforeUnmount(cleanupObserver)
</script>

<template>
  <div class="tmdb-full-view">
    <!-- 工具栏 -->
    <div class="toolbar-row">
      <AppSearchField v-model:value="browserSearch" placeholder="搜索标题或 TMDB ID..." :loading="browserLoading" @search="handleBrowserSearch" style="width: 300px" />
      <n-space>
        <n-button v-bind="getButtonStyle('warning')" @click="showRefreshModal = true">全量刷新</n-button>
        <n-button v-bind="getButtonStyle('warning')" @click="handleSyncSytmdb">同步 SYTMDB</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="openCreate">手动新增</n-button>
      </n-space>
    </div>

    <!-- 全量刷新弹窗 -->
    <AppGlassModal appearance-key="tmdb-full-data-modal" v-model:show="showRefreshModal" title="全量刷新设置" style="width: 450px">
      <n-form label-placement="left" label-width="120px">
        <n-form-item>
          <AppTextField 
            v-model:value="refreshForm.olderThanDays" 
            label="更新时间筛选"
            placeholder="留空表示不限制"
            type="number"
            :min="1"
          >
            <template #suffix>天前的数据</template>
          </AppTextField>
        </n-form-item>
        <n-form-item>
          <AppTextField 
            v-model:value="refreshForm.year" 
            label="首播年份筛选"
            placeholder="留空表示不限制"
            type="number"
            :min="1900" 
            :max="2100"
          />
        </n-form-item>
        <n-form-item>
          <AppSelectField 
            v-model:value="refreshForm.mediaType"
            label="媒体类型筛选"
            placeholder="留空表示不限制"
            clearable
            :options="[
              { label: '全部类型', value: null },
              { label: '电影', value: 'movie' },
              { label: '剧集', value: 'tv' }
            ]"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showRefreshModal = false">取消</n-button>
          <n-button type="warning" @click="handleExecuteRefresh">开始刷新</n-button>
        </n-space>
      </template>
    </AppGlassModal>

    <!-- 卡片网格 -->
    <div class="cards-container">
      <n-spin :show="browserLoading">
        <n-grid v-if="browserData.length > 0" :x-gap="10" :y-gap="10" cols="3 600:5 900:6 1200:8 1600:9">
          <n-gi v-for="item in browserData" :key="item.tmdb_id">
            <AppGlassCard appearance-key="tmdb-data-card" hoverable class="meta-card" content-style="padding: 0;" :bordered="true">
              <div class="card-content">
                <!-- 海报 -->
                <div class="poster-box" @click="openEdit(item)">
                  <n-image
                    v-if="item.poster_path"
                    :src="getImg(item.poster_path)"
                    fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
                    object-fit="cover"
                    preview-disabled
                    style="width: 100%; height: 100%;"
                  />
                  <div v-else class="poster-placeholder">
                    <n-icon size="40" :component="item.media_type === 'movie' ? SytmdbIcon : SearchIcon" />
                  </div>
                  <div class="type-badge" :class="item.media_type">
                    {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                  </div>
                </div>

                <!-- 信息区 -->
                <div class="info-box">
                  <div class="meta-title" :title="item.title" @click="openEdit(item)">{{ item.title }}</div>
                  <div class="meta-sub">
                    <span class="meta-year">{{ item.first_air_date?.slice(0, 4) || '-' }}</span>
                    <span class="meta-id">ID: {{ item.tmdb_id }}</span>
                  </div>
                  <div class="meta-genres">
                    <n-button
                      v-bind="getButtonStyle('icon')"
                      size="tiny"
                      :loading="refreshSingleId === String(item.tmdb_id)"
                      @click.stop="handleRefreshSingle(item)"
                    >
                      <template #icon><n-icon><RefreshIcon /></n-icon></template>
                    </n-button>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" @click="deleteMetadata(item)">
                      <template #icon><n-icon><DeleteIcon /></n-icon></template>
                    </n-button>
                  </div>
                </div>
              </div>
            </AppGlassCard>
          </n-gi>
        </n-grid>

        <!-- 底部哨兵 + 加载状态 -->
        <div ref="sentinelRef" class="sentinel">
          <div v-if="browserLoading && browserData.length > 0" class="loading-more">
            <n-spin size="small" />
            <span>加载中...</span>
          </div>
          <div v-else-if="!browserHasMore && browserData.length > 0" class="no-more">
            已全部加载（共 {{ browserTotal }} 条）
          </div>
        </div>

        <div v-if="browserData.length === 0 && !browserLoading" class="empty-state">
          <n-empty description="暂无元数据" />
        </div>
      </n-spin>
    </div>

    <!-- 编辑/新增元数据弹窗 -->
    <AppGlassModal appearance-key="tmdb-full-data-modal" v-model:show="showEditModal" style="width: 900px" :title="isEditing ? '修正元数据' : '手动新增元数据'">
      <n-tabs v-model:value="editTab" type="line" animated>
        <!-- Tab 1: 编辑元数据 -->
        <n-tab-pane name="edit" tab="编辑元数据">
          <n-form label-placement="left" label-width="90" style="padding-top: 12px;">
            <n-grid :cols="2" :x-gap="12">
              <n-gi><n-form-item><AppTextField v-model:value="editForm.id" label="TMDB ID" :disabled="isEditing" placeholder="请输入 TMDB ID" /></n-form-item></n-gi>
              <n-gi><n-form-item><AppSelectField v-model:value="editForm.type" label="媒体类型" :options="[{label:'剧集',value:'tv'},{label:'电影',value:'movie'}]" /></n-form-item></n-gi>
            </n-grid>
            <n-form-item><AppTextField v-model:value="editForm.title" label="显示标题" placeholder="请输入显示标题" /></n-form-item>
          </n-form>
        </n-tab-pane>

        <!-- Tab 2: 完整数据 (仅编辑时显示) -->
        <n-tab-pane v-if="isEditing" name="fulldata" tab="完整数据">
          <div class="fd-content">
            <template v-if="fullData">
              <!-- 头部：海报 + 基本信息 -->
              <div class="fd-header">
                <div class="fd-poster-col">
                  <n-image
                    v-if="editForm.poster_path"
                    :src="getImg(editForm.poster_path)"
                    class="fd-poster"
                    object-fit="cover"
                    preview-disabled
                    fallback-src="https://via.placeholder.com/300x450?text=No+Poster"
                  />
                </div>
                <div class="fd-info-col">
                  <h3 class="fd-title">{{ fullData.title || fullData.name || editForm.title }}</h3>
                  <div v-if="fullData.original_title || fullData.original_name" class="fd-original-title">
                    {{ fullData.original_title || fullData.original_name }}
                  </div>
                  <div v-if="fullData.tagline" class="fd-tagline">"{{ fullData.tagline }}"</div>
                  <div class="fd-badges">
                    <span v-if="fullData.vote_average" class="fd-badge fd-badge--warning">
                      <n-icon size="12"><StarIcon /></n-icon>
                      {{ fullData.vote_average.toFixed(1) }}
                    </span>
                    <span v-if="fullData.vote_count" class="fd-badge">{{ fullData.vote_count }} 人评分</span>
                    <span v-if="fullData.release_date || fullData.first_air_date" class="fd-badge">
                      <n-icon size="12"><DateIcon /></n-icon>
                      {{ fullData.release_date || fullData.first_air_date }}
                    </span>
                    <span v-if="fullData.status" class="fd-badge fd-badge--info">{{ translateStatus(fullData.status) }}</span>
                    <span v-if="fullData.adult" class="fd-badge fd-badge--error">R18</span>
                  </div>
                </div>
              </div>

              <!-- 信息网格 -->
              <div class="fd-info-grid">
                <div class="fd-info-item">
                  <span class="fd-info-label">TMDB ID</span>
                  <span class="fd-info-value fd-link" @click="openUrl(`https://www.themoviedb.org/${editForm.type}/${editForm.id}`)">{{ editForm.id }}</span>
                </div>
                <div v-if="fullData.release_date || fullData.first_air_date" class="fd-info-item">
                  <span class="fd-info-label">首播日期</span>
                  <span class="fd-info-value">{{ fullData.release_date || fullData.first_air_date }}</span>
                </div>
                <div v-if="fullData.last_air_date" class="fd-info-item">
                  <span class="fd-info-label">完结日期</span>
                  <span class="fd-info-value">{{ fullData.last_air_date }}</span>
                </div>
                <div v-if="fullData.imdb_id" class="fd-info-item">
                  <span class="fd-info-label">IMDb ID</span>
                  <span class="fd-info-value">{{ fullData.imdb_id }}</span>
                </div>
                <div v-if="fullData.runtime" class="fd-info-item">
                  <span class="fd-info-label">时长</span>
                  <span class="fd-info-value">{{ fullData.runtime }} 分钟</span>
                </div>
                <div v-if="fullData.episode_run_time?.length" class="fd-info-item">
                  <span class="fd-info-label">单集时长</span>
                  <span class="fd-info-value">{{ fullData.episode_run_time[0] }} 分钟</span>
                </div>
                <div v-if="fullData.number_of_seasons" class="fd-info-item">
                  <span class="fd-info-label">季数</span>
                  <span class="fd-info-value">{{ fullData.number_of_seasons }}</span>
                </div>
                <div v-if="fullData.number_of_episodes" class="fd-info-item">
                  <span class="fd-info-label">总集数</span>
                  <span class="fd-info-value">{{ fullData.number_of_episodes }}</span>
                </div>
                <div class="fd-info-item">
                  <span class="fd-info-label">媒体类型</span>
                  <span class="fd-info-value">{{ editForm.type === 'movie' ? '电影' : '剧集' }}</span>
                </div>
                <div v-if="fullData.original_language" class="fd-info-item">
                  <span class="fd-info-label">原始语言</span>
                  <span class="fd-info-value">{{ translateLanguage(fullData.original_language) }}</span>
                </div>
                <div v-if="fullData.homepage" class="fd-info-item">
                  <span class="fd-info-label">官网</span>
                  <span class="fd-info-value fd-link" @click="openUrl(fullData.homepage)">访问</span>
                </div>
              </div>

              <!-- 流派 -->
              <div v-if="fullData.genres?.length" class="fd-section">
                <div class="fd-section-title">流派</div>
                <div class="fd-chips">
                  <span v-for="g in fullData.genres" :key="g.id" class="fd-chip fd-chip--primary">{{ translateGenreName(g.id, g.name) }}</span>
                </div>
              </div>

              <!-- 简介 -->
              <div v-if="fullData.overview" class="fd-section">
                <div class="fd-section-title">简介</div>
                <p class="fd-overview">{{ fullData.overview }}</p>
              </div>

              <!-- 制作公司 -->
              <div v-if="fullData.production_companies?.length" class="fd-section">
                <div class="fd-section-title">制作公司</div>
                <div class="fd-card-list">
                  <div v-for="c in fullData.production_companies" :key="c.id" class="fd-mini-card">
                    <div v-if="c.logo_path" class="fd-mini-logo">
                      <n-image :src="getImg(c.logo_path)" object-fit="contain" preview-disabled />
                    </div>
                    <div class="fd-mini-info">
                      <div class="fd-mini-name">{{ c.name }}</div>
                      <div v-if="c.origin_country" class="fd-mini-sub">{{ translateCountry(c.origin_country) }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 电视网络 -->
              <div v-if="fullData.networks?.length" class="fd-section">
                <div class="fd-section-title">电视网络</div>
                <div class="fd-card-list">
                  <div v-for="nw in fullData.networks" :key="nw.id" class="fd-mini-card">
                    <div v-if="nw.logo_path" class="fd-mini-logo">
                      <n-image :src="getImg(nw.logo_path)" object-fit="contain" preview-disabled />
                    </div>
                    <div class="fd-mini-info">
                      <div class="fd-mini-name">{{ nw.name }}</div>
                      <div v-if="nw.origin_country" class="fd-mini-sub">{{ translateCountry(nw.origin_country) }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 制作国家 -->
              <div v-if="fullData.production_countries?.length" class="fd-section">
                <div class="fd-section-title">制作国家</div>
                <div class="fd-chips">
                  <span v-for="c in fullData.production_countries" :key="c.iso_3166_1" class="fd-chip">{{ translateCountry(c.iso_3166_1) }}</span>
                </div>
              </div>

              <!-- 语言 -->
              <div v-if="fullData.spoken_languages?.length" class="fd-section">
                <div class="fd-section-title">语言</div>
                <div class="fd-chips">
                  <span v-for="l in fullData.spoken_languages" :key="l.iso_639_1" class="fd-chip">{{ translateLanguage(l.iso_639_1) }}</span>
                </div>
              </div>

              <!-- 关键词 -->
              <div v-if="keywordList.length" class="fd-section">
                <div class="fd-section-title">关键词 ({{ keywordList.length }})</div>
                <div class="fd-chips">
                  <span v-for="k in keywordList" :key="k.id" class="fd-chip">{{ k.name }}</span>
                </div>
              </div>

              <!-- 全语言标题 -->
              <div v-if="translationList.length" class="fd-section">
                <div class="fd-section-title">全语言标题 ({{ translationList.length }})</div>
                <div class="fd-trans-list">
                  <div v-for="t in translationList" :key="`${t.country}-${t.lang}`" class="fd-trans-item">
                    <span class="fd-trans-country" :title="t.country">{{ translateCountry(t.country) }}</span>
                    <span v-if="t.lang" class="fd-trans-lang" :title="t.langName">{{ translateLanguage(t.lang) }}</span>
                    <span class="fd-trans-title" :title="t.title">{{ t.title }}</span>
                  </div>
                </div>
              </div>

              <!-- 全语言别名 -->
              <div v-if="altTitleList.length" class="fd-section">
                <div class="fd-section-title">全语言别名 ({{ altTitleList.length }})</div>
                <div class="fd-trans-list">
                  <div v-for="(a, i) in altTitleList" :key="i" class="fd-trans-item">
                    <span class="fd-trans-country" :title="a.country">{{ a.country ? translateCountry(a.country) : '—' }}</span>
                    <span v-if="a.type" class="fd-trans-type" :title="a.type">{{ translateAltType(a.type) }}</span>
                    <span class="fd-trans-title" :title="a.title">{{ a.title }}</span>
                  </div>
                </div>
              </div>

              <!-- 创建者 -->
              <div v-if="fullData.created_by?.length" class="fd-section">
                <div class="fd-section-title">
                  <n-icon><PersonIcon /></n-icon> 创建者
                </div>
                <div class="fd-chips">
                  <span v-for="p in fullData.created_by" :key="p.id" class="fd-chip">{{ p.name }}</span>
                </div>
              </div>

              <!-- 演员 -->
              <div v-if="castList.length" class="fd-section">
                <div class="fd-section-title">
                  <n-icon><PersonIcon /></n-icon> 演员 ({{ castList.length }})
                </div>
                <div class="fd-cast-grid">
                  <div v-for="c in castList" :key="c.id" class="fd-cast-card">
                    <div class="fd-cast-photo">
                      <n-image
                        v-if="c.profilePath"
                        :src="getImg(c.profilePath)"
                        object-fit="cover"
                        preview-disabled
                        style="width: 100%; height: 100%;"
                      />
                      <div v-else class="fd-cast-placeholder">
                        <n-icon size="24"><PersonIcon /></n-icon>
                      </div>
                    </div>
                    <div class="fd-cast-info">
                      <div class="fd-cast-name" :title="c.name">{{ c.name }}</div>
                      <div v-if="c.character" class="fd-cast-character" :title="c.character">{{ c.character }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 季度信息 (TV) -->
              <div v-if="fullData.seasons?.length" class="fd-section">
                <div class="fd-section-title">季度信息</div>
                <div class="fd-seasons-list">
                  <div v-for="s in fullData.seasons" :key="s.id" class="fd-season-item">
                    <div class="fd-season-poster">
                      <n-image
                        v-if="s.poster_path"
                        :src="getImg(s.poster_path)"
                        object-fit="cover"
                        preview-disabled
                        style="width: 100%; height: 100%;"
                      />
                      <div v-else class="fd-season-poster-placeholder">S{{ s.season_number }}</div>
                    </div>
                    <div class="fd-season-info">
                      <div class="fd-season-name">{{ s.name }}</div>
                      <div class="fd-season-meta">
                        <span>{{ s.episode_count }} 集</span>
                        <span v-if="s.air_date">{{ s.air_date }}</span>
                      </div>
                      <div v-if="s.overview" class="fd-season-overview">{{ s.overview }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 原始 JSON -->
              <div class="fd-section">
                <n-collapse>
                  <n-collapse-item title="原始 JSON 数据" name="raw">
                    <template #header-extra>
                      <n-icon size="14"><CodeIcon /></n-icon>
                    </template>
                    <pre class="fd-raw-json">{{ fullDataJson }}</pre>
                  </n-collapse-item>
                </n-collapse>
              </div>
            </template>

            <n-empty v-else description="暂无完整数据，请执行刷新以从 TMDB 获取" style="padding: 60px 0;" />
          </div>
        </n-tab-pane>
      </n-tabs>

      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showEditModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveMetadata">保存并固定</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

/* 卡片容器 */
.cards-container {
  min-height: 200px;
  margin-bottom: 16px;
}

/* 单张卡片 - 边框/圆角/背景由全局外观系统统一管理 */
.meta-card {
  overflow: hidden;
  transition: all var(--transition-normal);
}

.meta-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.card-content {
  display: flex;
  flex-direction: column;
}

/* 海报区 */
.poster-box {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  background: var(--app-surface-inner);
  overflow: hidden;
  cursor: pointer;
}

.poster-box :deep(img) {
  width: 100%;
  height: 100%;
  transition: transform var(--transition-slow);
}

.meta-card:hover .poster-box :deep(img) {
  transform: scale(1.08);
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.type-badge {
  position: absolute;
  top: 5px;
  left: 5px;
  font-size: 9px;
  font-weight: 600;
  padding: 2px 5px;
  border-radius: 4px;
  color: #fff;
  background: var(--bg-overlay);
  backdrop-filter: blur(8px);
}

.type-badge.movie {
  background: rgba(198, 40, 40, 0.85);
}

.type-badge.tv {
  background: rgba(21, 101, 192, 0.85);
}

/* 信息区 */
.info-box {
  padding: 6px 8px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-title {
  font-weight: 700;
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
  cursor: pointer;
}

.meta-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: var(--text-tertiary);
}

.meta-year {
  color: var(--n-primary-color);
  font-weight: 600;
}

.meta-id {
  font-family: monospace;
}

.meta-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  min-height: 18px;
  justify-content: flex-end;
}

.meta-genres :deep(.n-button) {
  margin-left: 0;
}

/* 底部哨兵 */
.sentinel {
  min-height: 1px;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.no-more {
  text-align: center;
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-state {
  padding: 80px 0;
  text-align: center;
}

/* ===== 完整数据展示 ===== */
.fd-content {
  padding-top: 12px;
}

.fd-header {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.fd-poster-col {
  flex-shrink: 0;
}
.fd-poster {
  width: 140px;
  aspect-ratio: 2 / 3;
  border-radius: var(--card-border-radius, 6px);
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  background: var(--bg-primary);
}
.fd-poster :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.fd-info-col {
  flex: 1;
  min-width: 0;
}
.fd-title {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.3;
}
.fd-original-title {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}
.fd-tagline {
  font-size: 13px;
  font-style: italic;
  color: var(--n-primary-color);
  margin-bottom: 8px;
  opacity: 0.8;
}

/* 徽章 (评分/日期/状态等) - 纯 HTML，不使用 n-tag */
.fd-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.fd-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-surface-active);
  border: 1px solid var(--app-border-light);
}
.fd-badge--warning {
  color: var(--color-warning);
  background: var(--color-warning-bg);
  border-color: transparent;
  font-weight: 600;
}
.fd-badge--info {
  color: var(--n-primary-color);
  background: var(--primary-light);
  border-color: transparent;
  font-weight: 600;
}
.fd-badge--error {
  color: #fff;
  background: var(--color-error);
  border-color: transparent;
  font-weight: 600;
}

/* 信息网格 */
.fd-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px 16px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--app-surface-card-mixed);
  border-radius: var(--card-border-radius, 8px);
  border: 1px solid var(--app-border-light);
}
.fd-info-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fd-info-label {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.fd-info-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}
.fd-link {
  color: var(--n-primary-color);
  cursor: pointer;
  text-decoration: underline;
}

.fd-section {
  margin-bottom: 20px;
}
.fd-section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--n-primary-color);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.fd-overview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
  text-align: justify;
}

/* 标签芯片 (流派/国家/语言等) - 纯 HTML，不使用 n-tag */
.fd-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.fd-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-surface-active);
  border: 1px solid var(--app-border-light);
}
.fd-chip--primary {
  color: var(--n-primary-color);
  background: var(--primary-light);
  border-color: transparent;
}

/* 全语言标题/别名列表 */
.fd-trans-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fd-trans-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--app-surface-card-mixed);
  border-radius: var(--card-border-radius, 6px);
  border: 1px solid var(--app-border-light);
  font-size: 13px;
}
.fd-trans-country {
  flex-shrink: 0;
  min-width: 32px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--n-primary-color);
  background: var(--primary-light);
  padding: 1px 6px;
  border-radius: 4px;
}
.fd-trans-lang {
  flex-shrink: 0;
  width: 90px;
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fd-trans-type {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-surface-active);
  padding: 1px 6px;
  border-radius: 4px;
}
.fd-trans-title {
  flex: 1;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 演员网格 */
.fd-cast-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 10px;
}
.fd-cast-card {
  display: flex;
  flex-direction: column;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  overflow: hidden;
}
.fd-cast-photo {
  width: 100%;
  aspect-ratio: 2 / 3;
  background: var(--bg-primary);
  overflow: hidden;
}
.fd-cast-photo :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.fd-cast-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}
.fd-cast-info {
  padding: 6px 8px;
  text-align: center;
}
.fd-cast-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fd-cast-character {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 公司/网络卡片 */
.fd-card-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.fd-mini-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  min-width: 160px;
}
.fd-mini-logo {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: 4px;
  overflow: hidden;
}
.fd-mini-logo :deep(img) {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.fd-mini-info {
  flex: 1;
  min-width: 0;
}
.fd-mini-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fd-mini-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* 季度信息 */
.fd-seasons-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fd-season-item {
  display: flex;
  gap: 12px;
  padding: 10px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
}
.fd-season-poster {
  width: 50px;
  aspect-ratio: 2 / 3;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: var(--bg-primary);
}
.fd-season-poster :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.fd-season-poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  color: var(--text-muted);
}
.fd-season-info {
  flex: 1;
  min-width: 0;
}
.fd-season-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.fd-season-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.fd-season-overview {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 原始 JSON */
.fd-raw-json {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-secondary);
  background: var(--app-surface-inner);
  padding: 12px;
  border-radius: var(--code-radius, 6px);
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  font-family: monospace;
  margin: 0;
}
</style>
