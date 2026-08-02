<script setup lang="ts">
/**
 * MetadataTab — 元数据资产
 *
 * 功能: 搜索/分页浏览 TMDB 离线库, 编辑弹窗含完整数据展示, 无限滚动, 全量刷新按钮, SYTMDB 同步
 */
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { dataCenterApi } from '@/api'
import { useNotification, useConfirm, getImg, useMappingCache } from '@/composables'

const { success, error: showError, warning, info } = useNotification()
const { confirm } = useConfirm()
const { mappingCache, fetchMappingCache } = useMappingCache()

// --- 浏览列表 ---
const browserData = ref<any[]>([])
const browserTotal = ref(0)
const browserPage = ref(1)
const browserSearch = ref('')
const browserLoading = ref(false)
const browserHasMore = ref(true)
const BROWSE_PAGE_SIZE = 20

// --- 编辑弹窗 ---
const showEditModal = ref(false)
const isEditing = ref(false)
const editTab = ref('edit')
const editForm = reactive<Record<string, any>>({
  id: '', type: 'tv', title: '', poster_path: '', overview: '', manual: true, full_data: null,
})

// --- 单条刷新 ---
const refreshSingleId = ref<string | null>(null)

// --- SYTMDB 同步弹窗 ---
const showSyncModal = ref(false)
const syncForm = reactive({
  address: localStorage.getItem('sytmdb_address') || '',
  token: localStorage.getItem('sytmdb_token') || '',
})

// --- 全量刷新弹窗 ---
const showRefreshModal = ref(false)
const refreshForm = reactive({
  older_than_days: undefined as number | undefined,
  year: undefined as number | undefined,
  media_type: undefined as string | undefined,
})

watch(showEditModal, (val) => {
  if (val) {
    editTab.value = 'edit'
    fetchMappingCache()
  }
})

const fullData = computed<any>(() => {
  const raw = editForm.full_data
  if (!raw) return null
  if (typeof raw === 'string') { try { return JSON.parse(raw) } catch { return null } }
  return raw
})

const translationList = computed(() => {
  if (!fullData.value) return []
  return (fullData.value.translations?.translations || [])
    .map((tr: any) => ({ country: tr.iso_3166_1 || '', lang: tr.iso_639_1 || '', langName: tr.name || tr.english_name || '', title: tr.data?.title || tr.data?.name || '', overview: tr.data?.overview || '' }))
    .filter((t: any) => t.title)
})

const altTitleList = computed(() => {
  if (!fullData.value) return []
  const alt = fullData.value.alternative_titles
  const list = alt?.titles || alt?.results || []
  return list.map((a: any) => ({ country: a.iso_3166_1 || '', title: a.title || a.name || '', type: a.type || '' })).filter((t: any) => t.title)
})

const castList = computed(() => {
  if (!fullData.value) return []
  return (fullData.value.credits?.cast || []).map((c: any) => ({ id: c.id, name: c.name || '', character: c.character || '', profilePath: c.profile_path || '' }))
})

const keywordList = computed(() => {
  if (!fullData.value) return []
  const kwRaw = fullData.value.keywords || {}
  const list = kwRaw.keywords || kwRaw.results || []
  return list.map((k: any) => ({ id: k.id, name: mappingCache.value.keywords?.[String(k.id)] || k.name || String(k.id) }))
})

// --- 数据获取 ---
async function fetchBrowserData(append = false) {
  if (append && !browserHasMore.value) return
  if (!append) { browserPage.value = 1; browserData.value = []; browserHasMore.value = true }
  browserLoading.value = true
  try {
    const res = await dataCenterApi.browseMeta({ page: browserPage.value, page_size: BROWSE_PAGE_SIZE, search: browserSearch.value || undefined })
    const items = res?.items || []
    browserTotal.value = res?.total || 0
    if (items.length < BROWSE_PAGE_SIZE) browserHasMore.value = false
    if (append) browserData.value.push(...items)
    else browserData.value = items
    browserPage.value++
  } catch (e) { showError('加载离线库失败') }
  finally { browserLoading.value = false }
}

function searchBrowse() { fetchBrowserData(false) }

function openCreate() {
  isEditing.value = false
  Object.assign(editForm, { id: '', type: 'tv', title: '', poster_path: '', overview: '', manual: true, full_data: null })
  showEditModal.value = true
}

function openEdit(item: any) {
  isEditing.value = true
  Object.assign(editForm, { ...item, id: item.tmdb_id, type: item.media_type, poster_path: item.poster_path || '', overview: item.overview || '', manual: true })
  showEditModal.value = true
}

async function saveMetadata() {
  if (!editForm.id || !editForm.title) { warning('ID 和标题为必填项'); return }
  try {
    await dataCenterApi.saveMetadata(editForm)
    success('保存成功'); showEditModal.value = false; fetchBrowserData()
  } catch (e) { showError('保存失败') }
}

async function deleteMetadata(item: any) {
  const type = item.media_type || item.type
  const id = item.tmdb_id || item.id
  const ok = await confirm({ title: '确认删除', content: `确定要移除「${item.title}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try { await dataCenterApi.deleteMetadata(type, String(id)); success('已移除'); fetchBrowserData() }
  catch (e) { showError('删除失败') }
}

async function refreshSingle(item: any) {
  const tmdbId = item.tmdb_id || item.id
  const mediaType = item.media_type || item.type
  if (!tmdbId || !mediaType) return
  const ok = await confirm({ title: '确认刷新', content: `确定要从 TMDB 云端刷新「${item.title}」的元数据吗？刷新后除固定标题外，所有数据将被最新值覆盖。` })
  if (!ok) return
  refreshSingleId.value = String(tmdbId)
  try {
    const res = await dataCenterApi.refreshAll({ tmdb_id: String(tmdbId), media_type: mediaType })
    success(res?.message || '刷新任务已启动'); fetchBrowserData()
  } catch (e) { showError('刷新失败') } finally { refreshSingleId.value = null }
}

async function handleSyncSytmdb() {
  info('同步任务已启动，请查看实时日志了解进度')
  try { await dataCenterApi.syncSytmdb({}) } catch (e: any) { showError(e?.message || '启动同步失败') }
}

async function runSyncSytmdb() {
  if (!syncForm.address) { warning('请输入 SYTMDB 地址'); return }
  localStorage.setItem('sytmdb_address', syncForm.address)
  localStorage.setItem('sytmdb_token', syncForm.token)
  showSyncModal.value = false
  info('同步任务已启动，请查看实时日志了解进度')
  try { await dataCenterApi.syncSytmdb({ address: syncForm.address, token: syncForm.token }) } catch (e: any) { showError(e?.message || '启动同步失败') }
}

function handleExecuteRefresh() {
  const body: any = {}
  if (refreshForm.older_than_days) body.older_than_days = refreshForm.older_than_days
  if (refreshForm.year) body.year = refreshForm.year
  if (refreshForm.media_type) body.media_type = refreshForm.media_type
  dataCenterApi.refreshAll(body).then((res: any) => {
    success(res?.message || '全量刷新任务已启动')
  }).catch(() => showError('触发刷新失败'))
  showRefreshModal.value = false
  Object.assign(refreshForm, { older_than_days: undefined, year: undefined, media_type: undefined })
}

// --- 无限滚动 ---
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function setupObserver() {
  cleanupObserver()
  nextTick(() => {
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !browserLoading.value && browserHasMore.value) fetchBrowserData(true)
    }, { rootMargin: '300px' })
    observer.observe(el)
  })
}
function cleanupObserver() { if (observer) { observer.disconnect(); observer = null } }
watch(() => browserData.value.length, () => { if (browserHasMore.value) setupObserver() })

onMounted(() => {
  fetchBrowserData()
  fetchMappingCache()
})

onUnmounted(() => {
  cleanupObserver()
})
</script>

<template>
  <!-- 工具栏 -->
  <div class="d-flex ga-2 mb-4 flex-wrap align-center">
    <v-text-field
      v-model="browserSearch"
      label="搜索标题或 TMDB ID..."
      density="compact" variant="outlined" prepend-inner-icon="mdi-magnify"
      clearable hide-details class="flex-grow-1" style="min-width: 200px"
      @keyup.enter="searchBrowse" @click:clear="browserSearch = ''; searchBrowse()"
    />
    <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="showRefreshModal = true">全量刷新</v-btn>
    <v-btn variant="tonal" prepend-icon="mdi-sync-circle" @click="showSyncModal = true">同步 SYTMDB</v-btn>
    <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreate">手动新增</v-btn>
  </div>

  <!-- 卡片网格 -->
  <v-skeleton-loader v-if="browserLoading && browserData.length === 0" type="card@6" />

  <div v-else-if="browserData.length > 0" class="media-card-grid">
    <v-card
      v-for="item in browserData"
      :key="item.tmdb_id + item.media_type"
      class="glass-card media-card cursor-pointer"
      @click="openEdit(item)"
    >
      <div class="media-card__poster">
        <v-img
          v-if="item.poster_path"
          :src="getImg(item.poster_path)"
          cover
          class="rounded-t-xl"
        >
          <template #placeholder>
            <v-skeleton-loader type="image" />
          </template>
        </v-img>
        <div v-else class="media-card__poster-placeholder">
          <v-icon size="36" :color="item.media_type === 'movie' ? 'error' : 'primary'">
            {{ item.media_type === 'movie' ? 'mdi-movie-open-outline' : 'mdi-television-classic' }}
          </v-icon>
        </div>
        <span class="media-card__type" :class="item.media_type === 'movie' ? 'media-card__type--tmdb-movie' : 'media-card__type--tmdb-tv'">
          {{ item.media_type === 'movie' ? '电影' : '剧集' }}
        </span>
      </div>
      <div class="media-card__info">
        <div class="media-card__title" :title="item.title || item.name">{{ item.title || item.name || '-' }}</div>
        <div class="media-card__year">{{ item.first_air_date?.slice(0, 4) || item.year || '-' }}</div>
      </div>
      <div class="dc-meta-actions">
        <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-refresh" :loading="refreshSingleId === String(item.tmdb_id)" @click.stop="refreshSingle(item)">刷新</v-btn>
        <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteMetadata(item)">删除</v-btn>
      </div>
    </v-card>
  </div>

  <div v-else class="text-center pa-8">
    <v-icon size="64" color="primary" class="mb-4">mdi-database-off-outline</v-icon>
    <div class="text-h6 font-weight-medium">暂无元数据</div>
    <div class="text-body-2 text-medium-emphasis mt-2">使用"全量刷新"从 TMDB 云端同步数据</div>
  </div>

  <!-- 无限滚动哨兵 -->
  <div ref="sentinelRef" class="dc-sentinel">
    <div v-if="browserLoading && browserData.length > 0" class="text-center pa-4">
      <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
    </div>
    <div v-else-if="!browserHasMore && browserData.length > 0" class="text-center pa-4 text-caption text-medium-emphasis">
      已全部加载（共 {{ browserTotal }} 条）
    </div>
  </div>

  <!-- 全量刷新弹窗 -->
  <v-dialog v-model="showRefreshModal" max-width="500">
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start color="primary">mdi-sync</v-icon>全量刷新设置
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showRefreshModal = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field v-model="refreshForm.older_than_days" label="更新时间筛选" type="number" placeholder="留空表示不限制" variant="outlined" density="compact" class="mb-3" hint="天前的数据" persistent-hint />
        <v-text-field v-model="refreshForm.year" label="首播年份筛选" type="number" placeholder="留空表示不限制" variant="outlined" density="compact" class="mb-3" />
        <v-select v-model="refreshForm.media_type" label="媒体类型筛选" :items="[{ title: '全部', value: undefined }, { title: '电影', value: 'movie' }, { title: '剧集', value: 'tv' }]" variant="outlined" density="compact" clearable class="mb-3" />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showRefreshModal = false">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-refresh" @click="handleExecuteRefresh">开始刷新</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- SYTMDB 同步弹窗 -->
  <v-dialog v-model="showSyncModal" max-width="500">
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start color="primary">mdi-sync-circle</v-icon>SYTMDB 同步
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showSyncModal = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-3">从 SYTMDB 服务同步手动修正过的元数据快照。任务在后台执行，请通过实时日志查看进度。</div>
        <v-text-field v-model="syncForm.address" label="SYTMDB 地址 (IP:Port)" variant="outlined" density="compact" class="mb-3" placeholder="如: 192.168.1.100:8121" />
        <v-text-field v-model="syncForm.token" label="API Token (可选)" variant="outlined" density="compact" class="mb-3" />
        <div class="text-caption text-medium-emphasis">如留空将使用系统设置中配置的 SYTMDB 地址。</div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn variant="tonal" prepend-icon="mdi-cog-sync-outline" @click="() => { handleSyncSytmdb(); showSyncModal = false }">使用系统配置同步</v-btn>
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showSyncModal = false">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-sync" @click="runSyncSytmdb">同步</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 编辑/新增元数据弹窗 -->
  <v-dialog v-model="showEditModal" max-width="900" scrollable>
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start color="primary">mdi-pencil-outline</v-icon>
{{ isEditing ? '修正元数据' : '手动新增元数据' }}
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showEditModal = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-tabs v-model="editTab" density="compact" class="mb-4">
          <v-tab value="edit">编辑元数据</v-tab>
          <v-tab v-if="isEditing" value="fulldata">完整数据</v-tab>
        </v-tabs>

        <v-window v-model="editTab">
          <!-- 编辑 -->
          <v-window-item value="edit">
            <v-row dense>
              <v-col cols="12" sm="6"><v-text-field v-model="editForm.id" label="TMDB ID" variant="outlined" density="compact" :disabled="isEditing" class="mb-3" /></v-col>
              <v-col cols="12" sm="6"><v-select v-model="editForm.type" label="媒体类型" :items="[{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]" variant="outlined" density="compact" class="mb-3" /></v-col>
            </v-row>
            <v-text-field v-model="editForm.title" label="显示标题" variant="outlined" density="compact" class="mb-3" />
          </v-window-item>

          <!-- 完整数据展示 -->
          <v-window-item value="fulldata">
            <template v-if="fullData">
              <!-- 头部：海报 + 基本信息 -->
              <div class="d-flex ga-4 mb-5">
                <div style="flex-shrink:0">
                  <v-img v-if="editForm.poster_path" :src="getImg(editForm.poster_path)" width="140" height="210" cover style="border-radius:12px" />
                </div>
                <div class="flex-grow-1">
                  <h3 class="text-h6 font-weight-bold mb-1">{{ fullData.title || fullData.name || editForm.title }}</h3>
                  <div v-if="fullData.original_title || fullData.original_name" class="text-caption text-medium-emphasis mb-2">{{ fullData.original_title || fullData.original_name }}</div>
                  <div v-if="fullData.tagline" class="text-body-2 text-primary mb-2" style="font-style:italic">"{{ fullData.tagline }}"</div>
                  <div class="d-flex ga-2 flex-wrap">
                    <v-chip v-if="fullData.vote_average" size="small" variant="tonal" color="info">★ {{ fullData.vote_average.toFixed(1) }}</v-chip>
                    <v-chip v-if="fullData.vote_count" size="small" variant="tonal">{{ fullData.vote_count }} 人评分</v-chip>
                    <v-chip v-if="fullData.release_date || fullData.first_air_date" size="small" variant="tonal">{{ fullData.release_date || fullData.first_air_date }}</v-chip>
                    <v-chip v-if="fullData.status" size="small" variant="tonal" color="info">{{ fullData.status }}</v-chip>
                    <v-chip v-if="fullData.adult" size="small" variant="tonal" color="error">R18</v-chip>
                  </div>
                </div>
              </div>

              <!-- 信息网格 -->
              <div class="dc-info-grid mb-5">
                <div class="dc-info-item"><span class="dc-info-label">TMDB ID</span><span class="dc-info-value">{{ editForm.id }}</span></div>
                <div v-if="fullData.release_date || fullData.first_air_date" class="dc-info-item"><span class="dc-info-label">首播日期</span><span class="dc-info-value">{{ fullData.release_date || fullData.first_air_date }}</span></div>
                <div v-if="fullData.last_air_date" class="dc-info-item"><span class="dc-info-label">完结日期</span><span class="dc-info-value">{{ fullData.last_air_date }}</span></div>
                <div v-if="fullData.imdb_id" class="dc-info-item"><span class="dc-info-label">IMDb ID</span><span class="dc-info-value">{{ fullData.imdb_id }}</span></div>
                <div v-if="fullData.runtime" class="dc-info-item"><span class="dc-info-label">时长</span><span class="dc-info-value">{{ fullData.runtime }} 分钟</span></div>
                <div v-if="fullData.episode_run_time?.length" class="dc-info-item"><span class="dc-info-label">单集时长</span><span class="dc-info-value">{{ fullData.episode_run_time[0] }} 分钟</span></div>
                <div v-if="fullData.number_of_seasons" class="dc-info-item"><span class="dc-info-label">季数</span><span class="dc-info-value">{{ fullData.number_of_seasons }}</span></div>
                <div v-if="fullData.number_of_episodes" class="dc-info-item"><span class="dc-info-label">总集数</span><span class="dc-info-value">{{ fullData.number_of_episodes }}</span></div>
                <div class="dc-info-item"><span class="dc-info-label">类型</span><span class="dc-info-value">{{ editForm.type === 'movie' ? '电影' : '剧集' }}</span></div>
                <div v-if="fullData.original_language" class="dc-info-item"><span class="dc-info-label">原始语言</span><span class="dc-info-value">{{ mappingCache.languages[fullData.original_language] || fullData.original_language }}</span></div>
              </div>

              <!-- 流派 -->
              <div v-if="fullData.genres?.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">流派</div>
                <div class="d-flex ga-1 flex-wrap">
                  <v-chip v-for="g in fullData.genres" :key="g.id" size="small" variant="tonal" color="primary">{{ mappingCache.genres[String(g.id)] || g.name || g.id }}</v-chip>
                </div>
              </div>

              <!-- 简介 -->
              <div v-if="fullData.overview" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">简介</div>
                <div class="text-body-2">{{ fullData.overview }}</div>
              </div>

              <!-- 制作公司 -->
              <div v-if="fullData.production_companies?.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">制作公司</div>
                <div class="d-flex ga-3 flex-wrap">
                  <div v-for="c in fullData.production_companies" :key="c.id" class="d-flex align-center ga-2 pa-2 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.05);border:1px solid rgba(var(--v-theme-on-surface),0.1)">
                    <v-img v-if="c.logo_path" :src="getImg(c.logo_path)" width="32" height="32" contain />
                    <div><div class="text-body-2 font-weight-medium">{{ c.name }}</div><div v-if="c.origin_country" class="text-caption text-medium-emphasis">{{ mappingCache.countries[c.origin_country.toUpperCase()] || c.origin_country }}</div></div>
                  </div>
                </div>
              </div>

              <!-- 电视网络 -->
              <div v-if="fullData.networks?.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">电视网络</div>
                <div class="d-flex ga-3 flex-wrap">
                  <div v-for="nw in fullData.networks" :key="nw.id" class="d-flex align-center ga-2 pa-2 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.05);border:1px solid rgba(var(--v-theme-on-surface),0.1)">
                    <v-img v-if="nw.logo_path" :src="getImg(nw.logo_path)" width="32" height="32" contain />
                    <div><div class="text-body-2 font-weight-medium">{{ nw.name }}</div></div>
                  </div>
                </div>
              </div>

              <!-- 关键词 -->
              <div v-if="keywordList.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">关键词 ({{ keywordList.length }})</div>
                <div class="d-flex ga-1 flex-wrap"><v-chip v-for="k in keywordList" :key="k.id" size="small" variant="tonal" color="info">{{ k.name }}</v-chip></div>
              </div>

              <!-- 全语言标题 -->
              <div v-if="translationList.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">全语言标题 ({{ translationList.length }})</div>
                <div class="d-flex flex-column ga-1">
                  <div v-for="t in translationList" :key="`${t.country}-${t.lang}`" class="d-flex align-center ga-3 pa-2 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.05)">
                    <v-chip size="x-small" variant="tonal" color="primary">{{ mappingCache.countries[t.country.toUpperCase()] || t.country }}</v-chip>
                    <span v-if="t.lang" class="text-caption text-medium-emphasis" style="width:80px">{{ mappingCache.languages[t.lang.toLowerCase()] || t.lang }}</span>
                    <span class="text-body-2 font-weight-medium">{{ t.title }}</span>
                  </div>
                </div>
              </div>

              <!-- 全语言别名 -->
              <div v-if="altTitleList.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">全语言别名 ({{ altTitleList.length }})</div>
                <div class="d-flex flex-column ga-1">
                  <div v-for="(a, i) in altTitleList" :key="i" class="d-flex align-center ga-3 pa-2 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.05)">
                    <v-chip size="x-small" variant="tonal" color="primary">{{ mappingCache.countries[a.country.toUpperCase()] || a.country || '—' }}</v-chip>
                    <span v-if="a.type" class="text-caption text-medium-emphasis">{{ a.type }}</span>
                    <span class="text-body-2 font-weight-medium">{{ a.title }}</span>
                  </div>
                </div>
              </div>

              <!-- 演员 -->
              <div v-if="castList.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">演员 ({{ castList.length }})</div>
                <div class="d-flex ga-2 flex-wrap">
                  <div v-for="c in castList.slice(0, 20)" :key="c.id" class="text-center" style="width:80px">
                    <v-avatar size="60" rounded="lg">
                      <v-img v-if="c.profilePath" :src="getImg(c.profilePath)" cover />
                      <v-icon v-else size="36" color="grey">mdi-account</v-icon>
                    </v-avatar>
                    <div class="text-caption font-weight-medium mt-1 text-truncate">{{ c.name }}</div>
                    <div v-if="c.character" class="text-caption text-medium-emphasis text-truncate">{{ c.character }}</div>
                  </div>
                </div>
              </div>

              <!-- 季度信息 -->
              <div v-if="fullData.seasons?.length" class="mb-4">
                <div class="text-subtitle-2 font-weight-bold text-primary mb-2">季度信息</div>
                <div class="d-flex flex-column ga-2">
                  <div v-for="s in fullData.seasons" :key="s.id" class="d-flex ga-3 pa-2 rounded-lg" style="background:rgba(var(--v-theme-on-surface),0.05)">
                    <v-img v-if="s.poster_path" :src="getImg(s.poster_path)" width="40" height="60" cover style="border-radius:4px;flex-shrink:0" />
                    <div v-else class="d-flex align-center justify-center" style="width:40px;height:60px;background:rgba(var(--v-theme-on-surface),0.08);border-radius:4px;flex-shrink:0"><span class="text-caption font-weight-bold">S{{ s.season_number }}</span></div>
                    <div>
                      <div class="text-body-2 font-weight-medium">{{ s.name }}</div>
                      <div class="text-caption text-medium-emphasis">{{ s.episode_count }} 集<span v-if="s.air_date"> · {{ s.air_date }}</span></div>
                      <div v-if="s.overview" class="text-caption text-medium-emphasis mt-1" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">{{ s.overview }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <v-empty-state v-else title="暂无完整数据" text="请执行刷新以从 TMDB 获取" />
            </template>
          </v-window-item>
        </v-window>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showEditModal = false">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveMetadata">保存并固定</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 海报占位符 */
.media-card__poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

/* 卡片底部操作按钮 */
.dc-meta-actions {
  display: flex;
  gap: 4px;
  padding: 0 8px 8px;
  justify-content: center;
}

/* 无限滚动哨兵 */
.dc-sentinel { min-height: 1px; }

/* 信息网格 */
.dc-info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px 16px; padding: 16px; background: rgba(var(--v-theme-on-surface),0.04); border-radius: 12px; border: 1px solid rgba(var(--v-theme-on-surface),0.08); }
.dc-info-item { display: flex; align-items: center; gap: 6px; }
.dc-info-label { font-size: 12px; color: rgba(var(--v-theme-on-surface),0.5); white-space: nowrap; }
.dc-info-value { font-size: 13px; font-weight: 500; }
</style>
