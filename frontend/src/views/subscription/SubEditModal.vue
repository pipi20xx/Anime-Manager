<script setup lang="ts">
/**
 * SubEditModal — 订阅编辑弹窗
 *
 * 从 SubscriptionView 拆出的独立组件
 */
import { ref, reactive, watch } from 'vue'
import { subscriptionApi, tmdbApi, bangumiApi, clientsApi } from '@/api'
import { useNotification } from '@/composables'

const props = defineProps<{
  show: boolean
  subData: any
  isNew: boolean
  clients: any[]
  templates: any[]
  profiles: any[]
}>()
const emit = defineEmits(['update:show', 'save'])

const { success, error: showError, warning } = useNotification()

const form = reactive({
  id: null as number | null,
  tmdb_id: '',
  media_type: 'tv' as 'tv' | 'movie',
  title: '',
  year: '',
  poster_path: '',
  quality_profile_id: null as number | null,
  filter_res: '',
  filter_team: '',
  filter_source: '',
  filter_codec: '',
  filter_audio: '',
  filter_sub: '',
  filter_effect: '',
  filter_platform: '',
  include_keywords: '',
  exclude_keywords: '',
  target_feeds: [] as string[],
  target_client_id: null as number | null,
  save_path: '',
  category: 'Anime',
  enabled: true,
  auto_fill: true,
  bangumi_id: '',
  season: 1,
  start_episode: 1,
  end_episode: 0,
})

const searchQuery = ref('')
const searchLoading = ref(false)
const searchResults = ref<any[]>([])
const tmdbSeasons = ref<any[]>([])
const bangumiName = ref('')
const availableFeeds = ref<any[]>([])

watch(() => props.show, (val) => {
  if (val) {
    loadModalData()
    if (props.subData) {
      Object.keys(form).forEach(key => {
        if (props.subData[key] !== undefined) (form as any)[key] = props.subData[key]
      })
      if (typeof props.subData.target_feeds === 'string' && props.subData.target_feeds) {
        form.target_feeds = props.subData.target_feeds.split(',').filter(Boolean)
      } else if (!Array.isArray(props.subData.target_feeds)) {
        form.target_feeds = []
      }
      if (form.media_type === 'tv' && form.tmdb_id) fetchTvSeasons(form.tmdb_id)
      if (form.bangumi_id) fetchBangumiInfo(form.bangumi_id)
    } else {
      resetForm()
    }
  }
})

function resetForm() {
  Object.assign(form, {
    id: null, tmdb_id: '', media_type: 'tv', title: '', year: '', poster_path: '',
    quality_profile_id: null, filter_res: '', filter_team: '', filter_source: '',
    filter_codec: '', filter_audio: '', filter_sub: '', filter_effect: '', filter_platform: '',
    include_keywords: '', exclude_keywords: '', target_feeds: [], target_client_id: null,
    save_path: '', category: 'Anime', enabled: true, auto_fill: true, bangumi_id: '',
    season: 1, start_episode: 1, end_episode: 0,
  })
  searchQuery.value = ''
  searchResults.value = []
  tmdbSeasons.value = []
  bangumiName.value = ''
}

async function loadModalData() {
  try {
    const data = await subscriptionApi.getFeeds()
    availableFeeds.value = data || []
  } catch { /* */ }
}

function applyTemplate(tmplId: number | null) {
  if (!tmplId) return
  const tmpl = props.templates.find((t: any) => t.id === tmplId)
  if (!tmpl) return
  // 仅覆盖配置类参数，保留标题、ID、海报等核心元数据
  form.filter_res = tmpl.filter_res || ''
  form.filter_team = tmpl.filter_team || ''
  form.filter_source = tmpl.filter_source || ''
  form.filter_codec = tmpl.filter_codec || ''
  form.filter_audio = tmpl.filter_audio || ''
  form.filter_sub = tmpl.filter_sub || ''
  form.filter_effect = tmpl.filter_effect || ''
  form.filter_platform = tmpl.filter_platform || ''
  form.include_keywords = tmpl.include_keywords || ''
  form.exclude_keywords = tmpl.exclude_keywords || ''
  form.target_client_id = tmpl.target_client_id || null
  form.save_path = tmpl.save_path || ''
  form.category = tmpl.category || 'Anime'
  form.auto_fill = tmpl.auto_fill !== false
  if (tmpl.target_feeds) {
    form.target_feeds = String(tmpl.target_feeds).split(',').filter(Boolean)
  } else {
    form.target_feeds = []
  }
  if (tmpl.quality_profile_id) form.quality_profile_id = tmpl.quality_profile_id
  success(`已套用预设: ${tmpl.name}`)
}

async function handleSearch() {
  if (!searchQuery.value) return
  searchLoading.value = true
  try {
    const data = await tmdbApi.search({ query: searchQuery.value, type: form.media_type })
    searchResults.value = data?.results || []
  } catch (e) { showError('搜索失败') }
  finally { searchLoading.value = false }
}

function selectSearchResult(item: any) {
  form.tmdb_id = String(item.id)
  form.title = item.title || item.name
  form.year = item.year || ''
  form.poster_path = item.poster_path || ''
  searchResults.value = []
  if (form.media_type === 'tv') fetchTvSeasons(form.tmdb_id)
}

async function fetchTvSeasons(tmdbId: string) {
  try {
    const data = await tmdbApi.getDetail('tv', tmdbId)
    tmdbSeasons.value = data?.seasons || []
    if (!form.bangumi_id && tmdbSeasons.value.length > 0) {
      const matched = tmdbSeasons.value.find((s: any) => s.season_number === form.season)
      if (matched) form.end_episode = matched.episode_count || 0
    }
  } catch { /* */ }
}

async function fetchBangumiInfo(bgmid: string) {
  if (!bgmid) { bangumiName.value = ''; return }
  try {
    const data = await bangumiApi.getSubject(bgmid)
    bangumiName.value = data?.title || ''
    if (data?.total_episodes > 0 && (form.end_episode === 0 || props.isNew)) {
      form.end_episode = data.total_episodes
    }
  } catch { bangumiName.value = '条目未找到' }
}

function handleSave() {
  if (!form.tmdb_id || !form.title) { warning('请先选择或输入 TMDB ID 和标题'); return }
  const payload = { ...form }
  payload.season = parseInt(String(payload.season)) || 0
  payload.start_episode = parseInt(String(payload.start_episode)) || 0
  payload.end_episode = parseInt(String(payload.end_episode)) || 0
  if (Array.isArray(payload.target_feeds)) {
    (payload as any).target_feeds = payload.target_feeds.join(',')
  }
  emit('save', payload)
}
</script>

<template>
  <v-dialog :model-value="show" max-width="720" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start>mdi-rss</v-icon>
        {{ isNew ? '新建订阅' : '编辑订阅' }}
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <!-- 预设 & 洗版 -->
        <v-select
          v-if="isNew && templates.length > 0"
          :model-value="null"
          label="套用预设"
          :items="templates.map((t: any) => ({ title: t.name, value: t.id }))"
          clearable
          variant="outlined"
          density="compact"
          class="mb-3"
          placeholder="快速选择已保存的订阅预设..."
          @update:model-value="applyTemplate"
        />
        <v-select
          v-if="profiles.length > 0"
          v-model="form.quality_profile_id"
          label="洗版策略"
          :items="profiles.map((p: any) => ({ title: p.name, value: p.id }))"
          clearable
          variant="outlined"
          density="compact"
          class="mb-3"
        />

        <!-- TMDB 搜索 -->
        <div class="mb-3">
          <div class="d-flex ga-2 mb-2">
            <v-text-field v-model="searchQuery" placeholder="搜索 TMDB..." variant="outlined" density="compact" hide-details @keyup.enter="handleSearch" />
            <v-btn variant="tonal" prepend-icon="mdi-magnify" :loading="searchLoading" @click="handleSearch">搜索</v-btn>
          </div>
<div v-if="searchResults.length > 0" class="sub-search-results">
<div v-for="item in searchResults" :key="item.id" class="sub-search-result-item" @click="selectSearchResult(item)">
              <span class="font-weight-medium">{{ item.title || item.name }}</span>
              <span class="text-caption text-medium-emphasis ml-2">({{ item.year || '-' }}) ID:{{ item.id }}</span>
            </div>
          </div>
        </div>

        <v-row dense>
          <v-col cols="12" sm="6"><v-text-field v-model="form.tmdb_id" label="TMDB ID" variant="outlined" density="compact" /></v-col>
          <v-col cols="12" sm="6">
            <v-select v-model="form.media_type" label="媒体类型" :items="[{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]" variant="outlined" density="compact" />
          </v-col>
        </v-row>

        <v-text-field v-model="form.bangumi_id" label="Bangumi ID" variant="outlined" density="compact" class="mb-2">
          <template #details><div v-if="bangumiName" class="text-primary text-caption font-weight-bold mt-1">📺 {{ bangumiName }}</div></template>
        </v-text-field>
        <v-text-field v-model="form.title" label="标题" variant="outlined" density="compact" class="mb-2" />

        <!-- 筛选条件 -->
        <div class="text-subtitle-2 font-weight-medium mb-2 mt-3">资源筛选</div>
        <v-row dense>
          <v-col cols="6"><v-text-field v-model="form.filter_res" label="分辨率" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_team" label="制作组" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_source" label="介质来源" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_codec" label="视频编码" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_audio" label="音频编码" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_sub" label="字幕语言" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_effect" label="视频特效" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.filter_platform" label="发布平台" variant="outlined" density="compact" /></v-col>
        </v-row>

        <v-row dense class="mt-2">
          <v-col cols="6"><v-text-field v-model="form.include_keywords" label="必须包含" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.exclude_keywords" label="排除关键词" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.save_path" label="下载目录" variant="outlined" density="compact" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.category" label="分类/标签" variant="outlined" density="compact" /></v-col>
        </v-row>

        <v-row dense>
          <v-col cols="6">
            <v-select v-model="form.target_client_id" label="下载客户端" :items="clients.map((c: any) => ({ title: c.name, value: c.id }))" clearable variant="outlined" density="compact" />
          </v-col>
          <v-col cols="6">
            <v-select v-model="form.target_feeds" label="监控订阅源" :items="availableFeeds.map((f: any) => ({ title: f.title || f.url, value: String(f.id) }))" multiple chips clearable variant="outlined" density="compact" placeholder="留空则监控所有" />
          </v-col>
        </v-row>

        <!-- 剧集信息 -->
        <template v-if="form.media_type === 'tv'">
          <div class="text-subtitle-2 font-weight-medium mb-2 mt-3">剧集信息</div>
          <v-row dense>
            <v-col cols="4">
              <v-select v-model="form.season" label="订阅季度" :items="[{ title: '全部季度', value: 0 }, ...tmdbSeasons.map((s: any) => ({ title: `第${s.season_number}季(${s.episode_count}集)`, value: s.season_number }))]" variant="outlined" density="compact" />
            </v-col>
            <v-col cols="4"><v-text-field v-model="form.start_episode" label="起始集数" type="number" variant="outlined" density="compact" /></v-col>
            <v-col cols="4"><v-text-field v-model="form.end_episode" label="结束集数" type="number" variant="outlined" density="compact" /></v-col>
          </v-row>
        </template>

        <v-row dense class="mt-3">
          <v-col cols="6"><v-switch v-model="form.enabled" label="启用订阅" color="primary" density="compact" hide-details /></v-col>
          <v-col cols="6"><v-switch v-model="form.auto_fill" label="定时补全" color="primary" density="compact" hide-details /></v-col>
        </v-row>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSave">保存订阅</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>


