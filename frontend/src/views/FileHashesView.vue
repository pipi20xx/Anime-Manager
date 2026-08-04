<script setup lang="ts">
/**
 * FileHashesView — 文件哈希记录
 *
 * 独立页面，对标后端 /api/file_hashes:
 * - q 关键词搜索 (文件名/标题/ED2K/SHA1/路径)
 * - 多字段筛选 (tmdb_id/media_type/season/team)
 * - 排序 (calculated_at/file_size/original_filename/title)
 * - 哈希详情查看 (全部字段展示)
 * - 计算单文件哈希 (含全部识别信息)
 * - 无限滚动加载
 */
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { fileHashApi } from '@/api'
import { useNotification, useConfirm, useClipboard } from '@/composables'

defineOptions({ name: 'FileHashesView' })

const { success, error: showError, warning, info: showInfo } = useNotification()
const { confirm } = useConfirm()
const { copy: copyToClipboard } = useClipboard()

// --- 列表数据 ---
const hashList = ref<any[]>([])
const hashTotal = ref(0)
const loading = ref(false)
const offset = ref(0)
const limit = ref(50)

// --- 搜索与筛选 ---
const searchQuery = ref('')
const filterMediaType = ref<string | undefined>(undefined)
const filterTmdbId = ref('')
const filterSeason = ref<number | undefined>(undefined)
const filterTeam = ref('')
const sortBy = ref('calculated_at')
const sortOrder = ref('desc')

// --- 详情弹窗 ---
const showDetailModal = ref(false)
const detailItem = ref<any>(null)
const detailLoading = ref(false)

// --- 计算弹窗 ---
const showCalculateModal = ref(false)
const calculateLoading = ref(false)
const calculateForm = ref({
  file_path: '',
  tmdb_id: '',
  title: '',
  media_type: 'tv',
  season: undefined as number | undefined,
  episode: '',
  resolution: '',
  team: '',
  video_encode: '',
  audio_encode: '',
  video_effect: '',
  source: '',
  subtitle: '',
  platform: '',
  year: '',
  secondary_category: '',
  origin_country: '',
})

// --- 高级筛选 ---
const showAdvancedFilter = ref(false)

// ========== ED2K 模板渲染 ==========
const ED2K_TEMPLATE_KEY_TV = 'file_hashes_ed2k_template_tv'
const ED2K_TEMPLATE_KEY_MOVIE = 'file_hashes_ed2k_template_movie'

const defaultEd2kTemplates = {
  tv: '{original_filename}.{ext}',
  movie: '{original_filename}.{ext}',
}

const ed2kTemplatePresets = {
  tv: [
    { label: '原始文件名', icon: 'mdi-file-document-outline', desc: '保持原文件名', template: '{original_filename}.{ext}' },
    { label: '标题+季集+制作组', icon: 'mdi-view-list-outline', desc: '标题年份+季集+制作组', template: '{title} ({year}) - S{season_02}E{episode_02} - {team}' },
    { label: '标题+季集', icon: 'mdi-format-list-bulleted', desc: '标题年份+季集', template: '{title} ({year}) - S{season_02}E{episode_02}' },
  ],
  movie: [
    { label: '原始文件名', icon: 'mdi-file-document-outline', desc: '保持原文件名', template: '{original_filename}.{ext}' },
    { label: '标题+年份+制作组', icon: 'mdi-view-list-outline', desc: '标题年份+制作组', template: '{title} ({year}) - {team}' },
    { label: '标题+年份', icon: 'mdi-format-list-bulleted', desc: '标题年份', template: '{title} ({year})' },
  ],
}

const ed2kVariableGroups = [
  {
    title: '识别信息',
    vars: {
      '{title}': '标题',
      '{year}': '年份',
      '{season}': '季号',
      '{season_02}': '季号补零 (01)',
      '{episode}': '集数',
      '{episode_02}': '集数补零 (01)',
      '{resolution}': '分辨率',
      '{team}': '制作组 (别名 {group})',
      '{source}': '介质来源',
      '{video_encode}': '视频编码',
      '{audio_encode}': '音频编码',
      '{video_effect}': '视频特效',
      '{subtitle}': '字幕',
      '{platform}': '发布平台',
      '{release_date}': '发布日期 (别名 {date})',
      '{tmdb_id}': 'TMDB ID',
      '{secondary_category}': '二级分类',
      '{origin_country}': '原产地',
    },
  },
  {
    title: '文件信息',
    vars: {
      '{original_filename}': '原始文件名 (不含后缀, 别名 {name})',
      '{ext}': '文件后缀 (如 mkv)',
    },
  },
]

const ed2kTemplates = ref({
  tv: localStorage.getItem(ED2K_TEMPLATE_KEY_TV) || defaultEd2kTemplates.tv,
  movie: localStorage.getItem(ED2K_TEMPLATE_KEY_MOVIE) || defaultEd2kTemplates.movie,
})

const showTemplateSettings = ref(false)
const activeTemplateTab = ref<'tv' | 'movie'>('tv')
const templateDraft = ref({ tv: '', movie: '' })

function isMovieRecord(record: any): boolean {
  const raw = (record.media_type || '').toLowerCase()
  return raw === 'movie' || raw === '电影'
}

function getTemplateForRecord(record: any): string {
  return isMovieRecord(record) ? ed2kTemplates.value.movie : ed2kTemplates.value.tv
}

function extractExt(filename: string): string {
  const idx = filename.lastIndexOf('.')
  if (idx < 0 || idx === filename.length - 1) return ''
  return filename.slice(idx + 1)
}

function renderEd2kFilename(record: any, template: string): string {
  const season02 = (record.season !== null && record.season !== undefined)
    ? String(record.season).padStart(2, '0')
    : ''
  const episode02 = (() => {
    const ep = record.episode
    if (!ep) return ''
    if (String(ep).includes('-')) return String(ep)
    const n = Number(ep)
    return Number.isNaN(n) ? String(ep) : String(n).padStart(2, '0')
  })()

  const ext = extractExt(record.original_filename || '')

  const vars: Record<string, string> = {
    '{title}': record.title || '',
    '{year}': record.year || '',
    '{season}': (record.season !== null && record.season !== undefined) ? String(record.season) : '',
    '{season_02}': season02,
    '{episode}': record.episode || '',
    '{episode_02}': episode02,
    '{resolution}': record.resolution || '',
    '{team}': record.team || '',
    '{group}': record.team || '',
    '{source}': record.source || '',
    '{video_encode}': record.video_encode || '',
    '{audio_encode}': record.audio_encode || '',
    '{video_effect}': record.video_effect || '',
    '{subtitle}': record.subtitle || '',
    '{platform}': record.platform || '',
    '{release_date}': record.release_date || '',
    '{date}': record.release_date || '',
    '{tmdb_id}': record.tmdb_id || '',
    '{secondary_category}': record.secondary_category || '',
    '{origin_country}': record.origin_country || '',
    '{ext}': ext,
    '{original_filename}': (record.original_filename || '').replace(/\.[^.]+$/, ''),
    '{name}': (record.original_filename || '').replace(/\.[^.]+$/, ''),
  }

  let result = template
  for (const [key, val] of Object.entries(vars)) {
    result = result.replaceAll(key, val)
  }

  result = result.replace(/\(\s*\)/g, '').replace(/\[\s*\]/g, '')
  result = result.replace(/\s{2,}/g, ' ').trim()
  result = result.replace(/^[-\s]+|[-\s]+$/g, '')

  if (!template.includes('{ext}') && ext) {
    result = `${result}.${ext}`
  }

  return result || record.original_filename || ''
}

function rebuildEd2kLink(ed2kLink: string, newFilename: string): string {
  if (!ed2kLink) return ed2kLink
  const parts = ed2kLink.split('|')
  if (parts.length >= 5 && parts[0] === 'ed2k://' && parts[1] === 'file') {
    parts[2] = newFilename
    return parts.join('|')
  }
  return ed2kLink
}

function renderEd2kLink(record: any): string {
  if (!record.ed2k_link) return ''
  const newFilename = renderEd2kFilename(record, getTemplateForRecord(record))
  return rebuildEd2kLink(record.ed2k_link, newFilename)
}

function copyEd2kWithTemplate(record: any) {
  const link = renderEd2kLink(record)
  if (!link) { warning('该记录没有 ED2K 链接'); return }
  copyToClipboard(link, 'ED2K 链接已复制')
}

function openTemplateSettings() {
  templateDraft.value = {
    tv: ed2kTemplates.value.tv,
    movie: ed2kTemplates.value.movie,
  }
  showTemplateSettings.value = true
}

function handleSaveTemplate() {
  ed2kTemplates.value = {
    tv: templateDraft.value.tv.trim() || defaultEd2kTemplates.tv,
    movie: templateDraft.value.movie.trim() || defaultEd2kTemplates.movie,
  }
  localStorage.setItem(ED2K_TEMPLATE_KEY_TV, ed2kTemplates.value.tv)
  localStorage.setItem(ED2K_TEMPLATE_KEY_MOVIE, ed2kTemplates.value.movie)
  success('ED2K 命名模板已保存')
  showTemplateSettings.value = false
}

function handleResetTemplate() {
  templateDraft.value[activeTemplateTab.value] = defaultEd2kTemplates[activeTemplateTab.value]
}

function applyPreset(template: string) {
  templateDraft.value[activeTemplateTab.value] = template
}

const previewRecord = computed(() => {
  const wantMovie = activeTemplateTab.value === 'movie'
  const matched = hashList.value.find((r: any) => isMovieRecord(r) === wantMovie && r.ed2k_link)
  return matched || detailItem.value || hashList.value[0] || null
})

const previewFilename = computed(() => {
  if (!previewRecord.value) return '（暂无数据可预览）'
  return renderEd2kFilename(previewRecord.value, templateDraft.value[activeTemplateTab.value])
})

const previewEd2kLink = computed(() => {
  if (!previewRecord.value || !previewRecord.value.ed2k_link) return '（暂无数据可预览）'
  const fn = renderEd2kFilename(previewRecord.value, templateDraft.value[activeTemplateTab.value])
  return rebuildEd2kLink(previewRecord.value.ed2k_link, fn)
})

// ========== 导出 / 复制全部 ==========
const exporting = ref(false)

function downloadText(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function timestamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

function filterDescription(): string {
  const parts: string[] = []
  if (searchQuery.value) parts.push(`关键词="${searchQuery.value}"`)
  if (filterTmdbId.value) parts.push(`TMDB ID=${filterTmdbId.value}`)
  if (filterMediaType.value) parts.push(`类型=${filterMediaType.value}`)
  if (filterSeason.value !== undefined) parts.push(`季号=${filterSeason.value}`)
  if (filterTeam.value) parts.push(`制作组=${filterTeam.value}`)
  return parts.length ? parts.join(', ') : '无（全部记录）'
}

async function fetchAllFiltered(): Promise<any[]> {
  const PAGE = 500
  const all: any[] = []
  let off = 0
  const MAX = 100000
  while (off < MAX) {
    const data = await fileHashApi.getList({
      q: searchQuery.value || undefined,
      media_type: filterMediaType.value,
      tmdb_id: filterTmdbId.value || undefined,
      season: filterSeason.value,
      team: filterTeam.value || undefined,
      limit: PAGE,
      offset: off,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    const res = data as any
    const batch = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
    all.push(...batch)
    off += batch.length
    if (batch.length < PAGE || all.length >= (res?.total || 0)) break
  }
  return all
}

async function exportEd2kLinks() {
  if (hashTotal.value === 0) { warning('当前没有可导出的数据'); return }
  exporting.value = true
  try {
    const all = await fetchAllFiltered()
    const lines = all.map(r => renderEd2kLink(r)).filter(Boolean)
    const header = `# 文件哈希 ED2K 链接导出\n# 导出时间: ${new Date().toLocaleString()}\n# 筛选条件: ${filterDescription()}\n# 共 ${lines.length} 条 (剧集模板: ${ed2kTemplates.value.tv} | 电影模板: ${ed2kTemplates.value.movie})\n\n`
    downloadText(header + lines.join('\n') + '\n', `ed2k_links_${timestamp()}.txt`)
    success(`已导出 ${lines.length} 条 ED2K 链接`)
  } catch (e) {
    showError('导出失败，请重试')
  } finally {
    exporting.value = false
  }
}

async function copyAllEd2kLinks() {
  if (hashTotal.value === 0) { warning('当前没有可复制的数据'); return }
  exporting.value = true
  try {
    const all = await fetchAllFiltered()
    const lines = all.map(r => renderEd2kLink(r)).filter(Boolean)
    if (lines.length === 0) { warning('没有有效的 ED2K 链接'); return }
    await copyToClipboard(lines.join('\n'), `已复制 ${lines.length} 条 ED2K 链接`)
  } catch (e) {
    showError('复制失败，请尝试导出 txt')
  } finally {
    exporting.value = false
  }
}

async function exportFullInfo() {
  if (hashTotal.value === 0) { warning('当前没有可导出的数据'); return }
  exporting.value = true
  try {
    const all = await fetchAllFiltered()
    const header = `# 文件哈希记录完整导出\n# 导出时间: ${new Date().toLocaleString()}\n# 筛选条件: ${filterDescription()}\n# 共 ${all.length} 条\n\n`
    const body = all.map((r, i) => {
      const se = (r.season !== null && r.season !== undefined) ? `S${String(r.season).padStart(2, '0')}` : ''
      const ep = r.episode ? `E${r.episode}` : ''
      return [
        `[${i + 1}] ${r.title || r.original_filename} ${r.year ? `(${r.year})` : ''} ${[se, ep].filter(Boolean).join(' ')}`.trim(),
        `    原始文件名: ${r.original_filename}`,
        `    大小: ${formatFileSize(r.file_size)}`,
        `    类型: ${r.media_type || '-'}`,
        r.resolution ? `    分辨率: ${r.resolution}` : null,
        r.team ? `    制作组: ${r.team}` : null,
        r.tmdb_id ? `    TMDB ID: ${r.tmdb_id}` : null,
        `    渲染ED2K: ${renderEd2kLink(r)}`,
        `    原始ED2K: ${r.ed2k_link}`,
        '',
      ].filter(Boolean).join('\n')
    }).join('\n')
    downloadText(header + body, `file_hashes_${timestamp()}.txt`)
    success(`已导出 ${all.length} 条完整记录`)
  } catch (e) {
    showError('导出失败，请重试')
  } finally {
    exporting.value = false
  }
}

const hasMore = computed(() => hashList.value.length < hashTotal.value)

// --- 无限滚动 ---
const scrollTarget = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

function setupObserver(el: HTMLElement) {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value) {
      loadMore()
    }
  }, { threshold: 0, rootMargin: '200px' })
  observer.observe(el)
}

watch(scrollTarget, (el) => {
  if (el) setupObserver(el)
})

watch(loading, async (isLoading) => {
  if (!isLoading && hasMore.value && scrollTarget.value) {
    await nextTick()
    const rect = scrollTarget.value.getBoundingClientRect()
    if (rect.top < window.innerHeight + 200) {
      loadMore()
    }
  }
})

// --- 搜索防抖 ---
let searchDebounce: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    searchHashes()
  }, 400)
})

async function fetchHashList(append = false) {
  loading.value = true
  try {
    const data = await fileHashApi.getList({
      q: searchQuery.value || undefined,
      media_type: filterMediaType.value,
      tmdb_id: filterTmdbId.value || undefined,
      season: filterSeason.value,
      team: filterTeam.value || undefined,
      limit: limit.value,
      offset: offset.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    const res = data as any
    hashTotal.value = res?.total || 0
    const items = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
    if (append) {
      hashList.value = [...hashList.value, ...items]
    } else {
      hashList.value = items
    }
  } catch (e) {
    showError('加载哈希记录失败')
  } finally {
    loading.value = false
  }
}

function searchHashes() {
  offset.value = 0
  fetchHashList(false)
}

function loadMore() {
  offset.value += limit.value
  fetchHashList(true)
}

async function openDetail(item: any) {
  detailItem.value = item
  showDetailModal.value = true
  if (item.id) {
    detailLoading.value = true
    try {
      const data = await fileHashApi.getDetail(item.id)
      detailItem.value = (data as any)?.data || data || item
    } catch (e) {
      // 使用列表数据
    } finally {
      detailLoading.value = false
    }
  }
}

function openCalculateModal() {
  calculateForm.value = {
    file_path: '', tmdb_id: '', title: '', media_type: 'tv',
    season: undefined, episode: '', resolution: '', team: '',
    video_encode: '', audio_encode: '', video_effect: '', source: '',
    subtitle: '', platform: '', year: '', secondary_category: '', origin_country: '',
  }
  showCalculateModal.value = true
}

async function submitCalculate() {
  if (!calculateForm.value.file_path) { warning('请输入文件路径'); return }
  calculateLoading.value = true
  try {
    const body: any = { file_path: calculateForm.value.file_path }
    const optionalFields = ['tmdb_id', 'title', 'media_type', 'season', 'episode',
      'resolution', 'team', 'video_encode', 'audio_encode', 'video_effect',
      'source', 'subtitle', 'platform', 'year', 'secondary_category', 'origin_country']
    for (const f of optionalFields) {
      if (calculateForm.value[f as keyof typeof calculateForm.value]) {
        body[f] = calculateForm.value[f as keyof typeof calculateForm.value]
      }
    }
    const data = await fileHashApi.calculate(body)
    const res = data as any
    success(res?.message || res?.data?.message || '哈希计算完成')
    showCalculateModal.value = false
    searchHashes()
  } catch (e: any) {
    showError(e?.response?.data?.detail || '计算失败')
  } finally {
    calculateLoading.value = false
  }
}

// --- 格式化 ---
function formatMediaType(type: string): string {
  if (type === 'tv') return '剧集'
  if (type === 'movie') return '电影'
  return type || '-'
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}

function truncateHash(hash: string | undefined, len = 20): string {
  if (!hash) return '-'
  return hash.length > len ? hash.substring(0, len) + '...' : hash
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr
  }
}

// --- 重置筛选 ---
function resetFilters() {
  filterMediaType.value = undefined
  filterTmdbId.value = ''
  filterTeam.value = ''
  filterSeason.value = undefined
  sortBy.value = 'calculated_at'
  sortOrder.value = 'desc'
  searchHashes()
}

onMounted(() => {
  fetchHashList()
})

onUnmounted(() => {
  if (observer) observer.disconnect()
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between flex-wrap ga-3">
      <div>
        <h1 class="page-title text-h5 font-weight-bold">文件哈希记录</h1>
        <div class="page-subtitle text-body-2 text-medium-emphasis mt-1">共 {{ hashTotal }} 条 · SHA1 与 ED2K 哈希管理</div>
      </div>
      <div class="page-actions d-flex ga-2">
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn variant="tonal" color="info" prepend-icon="mdi-download-outline" :loading="exporting" v-bind="menuProps">导出</v-btn>
          </template>
          <v-list density="compact" min-width="200">
            <v-list-item prepend-icon="mdi-link-variant" title="导出 ED2K 链接 (txt)" @click="exportEd2kLinks" />
            <v-list-item prepend-icon="mdi-content-copy" title="复制全部 ED2K 链接" @click="copyAllEd2kLinks" />
            <v-divider />
            <v-list-item prepend-icon="mdi-file-document-outline" title="导出完整信息 (txt)" @click="exportFullInfo" />
          </v-list>
        </v-menu>
        <v-btn variant="tonal" color="info" prepend-icon="mdi-cog-outline" @click="openTemplateSettings">高级设置</v-btn>
      </div>
    </div>

    <!-- 搜索与筛选 -->
    <div class="list-toolbar">
      <div class="list-toolbar__filters d-flex align-center">
        <v-text-field
          v-model="searchQuery"
          placeholder="搜索文件名、标题、哈希、路径..."
          density="compact"
          variant="outlined"
          prepend-inner-icon="mdi-magnify"
          clearable
          hide-details
          class="search-field"
          @click:clear="searchQuery = ''; searchHashes()"
        />
        <v-btn
          variant="tonal"
          color="info"
          size="small"
          :prepend-icon="showAdvancedFilter ? 'mdi-filter-remove-outline' : 'mdi-filter-outline'"
          @click="showAdvancedFilter = !showAdvancedFilter"
        >
          {{ showAdvancedFilter ? '收起筛选' : '高级筛选' }}
        </v-btn>
      </div>
    </div>

    <!-- 高级筛选 -->
    <v-expand-transition>
      <div v-if="showAdvancedFilter" class="mb-4">
        <v-card class="glass-card pa-4">
          <v-row dense>
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="filterMediaType"
                label="媒体类型"
                :items="[
                  { title: '全部', value: undefined },
                  { title: '剧集', value: 'tv' },
                  { title: '电影', value: 'movie' },
                ]"
                density="compact"
                variant="outlined"
                hide-details
                clearable
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterTmdbId" label="TMDB ID" density="compact" variant="outlined" hide-details clearable />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterTeam" label="制作组" density="compact" variant="outlined" hide-details clearable />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterSeason" label="季号" type="number" density="compact" variant="outlined" hide-details clearable />
            </v-col>
          </v-row>
          <v-row dense class="mt-2">
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="sortBy"
                label="排序字段"
                :items="[
                  { title: '计算时间', value: 'calculated_at' },
                  { title: '文件大小', value: 'file_size' },
                  { title: '文件名', value: 'original_filename' },
                  { title: '标题', value: 'title' },
                ]"
                density="compact"
                variant="outlined"
                hide-details
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="sortOrder"
                label="排序方向"
                :items="[
                  { title: '降序 (最新优先)', value: 'desc' },
                  { title: '升序 (最早优先)', value: 'asc' },
                ]"
                density="compact"
                variant="outlined"
                hide-details
              />
            </v-col>
          </v-row>
          <div class="d-flex justify-end mt-3 ga-2">
            <v-btn variant="tonal" size="small" prepend-icon="mdi-refresh" @click="resetFilters">重置</v-btn>
            <v-btn color="primary" variant="flat" size="small" @click="searchHashes">应用筛选</v-btn>
          </div>
        </v-card>
      </div>
    </v-expand-transition>

    <!-- 列表 -->
    <v-skeleton-loader v-if="loading && hashList.length === 0" type="card@6" />

    <template v-else-if="hashList.length > 0">
      <div class="vertical-list">
        <v-card
          v-for="item in hashList"
          :key="item.id"
          class="glass-card hover-lift"
          @click="openDetail(item)"
        >
          <div class="detail-card">
            <!-- 左侧主内容 -->
            <div class="detail-card__main">
              <!-- 第一行：标签 -->
              <div class="detail-card__top-row">
                <div class="detail-card__tags-left">
                  <!-- 媒体类型 -->
                  <v-chip v-if="item.media_type" size="x-small" variant="flat" class="meta-tag meta-tag--type">
                    {{ formatMediaType(item.media_type) }}
                  </v-chip>
                  <!-- 季集 -->
                  <v-chip v-if="item.season" size="x-small" variant="flat" class="meta-tag meta-tag--season">
                    S{{ String(item.season).padStart(2, '0') }}{{ item.episode ? 'E' + String(item.episode).padStart(2, '0') : '' }}
                  </v-chip>
                  <!-- 分辨率 -->
                  <v-chip v-if="item.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">
                    {{ item.resolution }}
                  </v-chip>
                  <!-- 制作组 -->
                  <v-chip v-if="item.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">
                    {{ item.team }}
                  </v-chip>
                  <!-- 视频编码 -->
                  <v-chip v-if="item.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">
                    {{ item.video_encode }}
                  </v-chip>
                  <!-- 介质来源 -->
                  <v-chip v-if="item.source" size="x-small" variant="flat" class="meta-tag meta-tag--source">
                    {{ item.source }}
                  </v-chip>
                  <!-- 文件大小 -->
                  <v-chip v-if="item.file_size" size="x-small" variant="flat" class="meta-tag meta-tag--size">
                    {{ formatFileSize(item.file_size) }}
                  </v-chip>
                  <!-- 二级分类 -->
                  <v-chip v-if="item.secondary_category" size="x-small" variant="flat" class="meta-tag meta-tag--subscribed">
                    {{ item.secondary_category }}
                  </v-chip>
                </div>
              </div>

              <!-- 标题 -->
              <div class="detail-card__title">
                {{ item.title || item.original_filename || '-' }}
              </div>

              <!-- 文件名 (有标题时显示原始文件名) -->
              <div v-if="item.original_filename && item.title" class="detail-card__desc">
                {{ item.original_filename }}
              </div>

              <!-- 哈希值行 -->
              <div class="meta-tags">
                <v-chip v-if="item.sha1" size="x-small" variant="flat" class="meta-tag meta-tag--size" :title="item.sha1">
                  <v-icon size="10" class="mr-1">mdi-fingerprint</v-icon>
                  <span style="font-family: monospace;">SHA1: {{ truncateHash(item.sha1) }}</span>
                </v-chip>
                <v-chip v-if="item.ed2k" size="x-small" variant="flat" class="meta-tag meta-tag--encode" :title="item.ed2k">
                  <v-icon size="10" class="mr-1">mdi-link-variant</v-icon>
                  <span style="font-family: monospace;">ED2K: {{ truncateHash(item.ed2k) }}</span>
                </v-chip>
                <v-btn v-if="item.ed2k_link" size="x-small" variant="tonal" color="info" prepend-icon="mdi-content-copy" @click.stop="copyEd2kWithTemplate(item)" title="复制 ED2K 链接（按模板渲染）">复制ED2K</v-btn>
              </div>

              <!-- 源路径 -->
              <div v-if="item.source_path" class="detail-card__desc" style="font-family: monospace; padding-right: 0;" :title="item.source_path">
                <v-icon size="12" class="mr-1">mdi-folder-outline</v-icon>{{ item.source_path }}
              </div>
            </div>

            <!-- 右侧操作区 -->
            <div class="detail-card__aside">
              <!-- TMDB ID -->
              <a
                v-if="item.tmdb_id"
                class="meta-tag meta-tag--tmdb"
                :href="`https://www.themoviedb.org/${item.media_type || 'tv'}/${item.tmdb_id}`"
                target="_blank"
                @click.stop
              >
                TMDB: {{ item.tmdb_id }}
              </a>
              <span v-else class="detail-card__time" style="opacity: 0.3;">—</span>
              <div class="detail-card__time">{{ formatDate(item.calculated_at) }}</div>
            </div>
          </div>
        </v-card>
      </div>

      <!-- 无限滚动触发器 -->
      <div ref="scrollTarget" class="text-center pa-4">
        <v-progress-circular v-if="loading" indeterminate size="24" />
        <div v-else-if="!hasMore" class="text-caption text-medium-emphasis">
          <v-divider class="mb-3" />
          到底了，共 {{ hashList.length }} 条记录
        </div>
        <div v-else class="text-caption text-medium-emphasis d-flex align-center justify-center ga-2">
          <v-icon size="16">mdi-chevron-double-down</v-icon>
          向下滚动加载更多
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <v-icon size="64" color="primary" class="mb-4">mdi-fingerprint</v-icon>
      <div class="text-h6 font-weight-medium">暂无哈希记录</div>
      <div class="text-body-2 text-medium-emphasis mt-2">在整理任务中开启"哈希计算"后，记录会出现在这里</div>
    </div>

    <!-- 哈希详情弹窗 -->
    <v-dialog v-model="showDetailModal" max-width="720" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-fingerprint</v-icon>
          哈希详情
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showDetailModal = false" />
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4" style="max-height: 70vh; overflow-y: auto;">
          <v-skeleton-loader v-if="detailLoading" type="list-item@6" />

          <template v-else-if="detailItem">
            <!-- 基本信息 -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-information-outline</v-icon>
              基本信息
            </div>
            <div class="kv-row"><span class="kv-label">标题</span><span class="kv-value font-weight-medium">{{ detailItem.title || '-' }}</span></div>
            <div class="kv-row"><span class="kv-label">文件名</span><span class="kv-value font-weight-medium">{{ detailItem.original_filename || '-' }}</span></div>
            <div class="kv-row"><span class="kv-label">媒体类型</span><span class="kv-value font-weight-medium">{{ formatMediaType(detailItem.media_type) }}</span></div>
            <div class="kv-row"><span class="kv-label">文件大小</span><span class="kv-value font-weight-medium">{{ formatFileSize(detailItem.file_size) }}</span></div>
            <div class="kv-row" v-if="detailItem.tmdb_id"><span class="kv-label">TMDB ID</span><span class="kv-value font-weight-medium">{{ detailItem.tmdb_id }}</span></div>
            <div class="kv-row" v-if="detailItem.season"><span class="kv-label">季集</span><span class="kv-value font-weight-medium">S{{ detailItem.season }}E{{ detailItem.episode || '-' }}</span></div>
            <div class="kv-row" v-if="detailItem.year"><span class="kv-label">年份</span><span class="kv-value font-weight-medium">{{ detailItem.year }}</span></div>

            <v-divider class="my-3" />

            <!-- 识别信息 -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-tag-multiple-outline</v-icon>
              识别信息
            </div>
            <div class="meta-tags mb-2">
              <v-chip v-if="detailItem.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">{{ detailItem.team }}</v-chip>
              <v-chip v-if="detailItem.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">{{ detailItem.resolution }}</v-chip>
              <v-chip v-if="detailItem.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ detailItem.video_encode }}</v-chip>
              <v-chip v-if="detailItem.audio_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ detailItem.audio_encode }}</v-chip>
              <v-chip v-if="detailItem.video_effect" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ detailItem.video_effect }}</v-chip>
              <v-chip v-if="detailItem.source" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ detailItem.source }}</v-chip>
              <v-chip v-if="detailItem.subtitle" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ detailItem.subtitle }}</v-chip>
              <v-chip v-if="detailItem.platform" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ detailItem.platform }}</v-chip>
              <v-chip v-if="detailItem.secondary_category" size="x-small" variant="flat" class="meta-tag meta-tag--subscribed">{{ detailItem.secondary_category }}</v-chip>
              <v-chip v-if="detailItem.origin_country" size="x-small" variant="flat" class="meta-tag meta-tag--country">{{ detailItem.origin_country }}</v-chip>
            </div>
            <div class="kv-row" v-if="detailItem.release_date"><span class="kv-label">发布日期</span><span class="kv-value font-weight-medium">{{ detailItem.release_date }}</span></div>

            <v-divider class="my-3" />

            <!-- 哈希值 -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-fingerprint</v-icon>
              哈希值
            </div>
            <div class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">SHA1</div>
              <div class="hash-full-value" style="user-select:all">{{ detailItem.sha1 || '-' }}</div>
            </div>
            <div class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">ED2K</div>
              <div class="hash-full-value" style="user-select:all">{{ detailItem.ed2k || '-' }}</div>
            </div>
            <div v-if="detailItem.ed2k_link" class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">ED2K 链接</div>
              <div class="hash-full-value" style="word-break: break-all; user-select:all">{{ detailItem.ed2k_link }}</div>
            </div>

            <v-divider class="my-3" />

            <!-- 路径信息 -->
            <div class="section-title mb-2">
              <v-icon size="16" color="primary">mdi-folder-outline</v-icon>
              路径信息
            </div>
            <div class="kv-row"><span class="kv-label">源路径</span><span class="kv-value kv-value--mono">{{ detailItem.source_path || '-' }}</span></div>
            <div class="kv-row" v-if="detailItem.target_path"><span class="kv-label">目标路径</span><span class="kv-value kv-value--mono">{{ detailItem.target_path }}</span></div>
            <div class="kv-row"><span class="kv-label">计算时间</span><span class="kv-value font-weight-medium">{{ detailItem.calculated_at || '-' }}</span></div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions class="dialog-actions">
          <v-spacer />
          <v-btn variant="tonal" @click="showDetailModal = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 高级设置弹窗：ED2K 链接命名模板 -->
    <v-dialog v-model="showTemplateSettings" max-width="700" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-cog-outline</v-icon>
          ED2K 链接命名模板
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showTemplateSettings = false" />
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4" style="max-height: 70vh; overflow-y: auto;">
          <!-- 说明 -->
          <div class="text-body-2 text-medium-emphasis mb-4 pa-3" style="background: rgba(var(--v-theme-on-surface), 0.03); border-radius: 8px; line-height: 1.6;">
            复制 ED2K 链接时，会根据记录的媒体类型自动选择对应模板组合识别信息生成新的文件名，替换链接中的文件名段。
            变量用 <code class="text-warning">{}</code> 包裹，好比重命名规则。不含 <code class="text-warning">{ext}</code> 时自动补后缀。
          </div>

          <!-- 剧集 / 电影 双模板切换 -->
          <v-tabs v-model="activeTemplateTab" color="primary" class="mb-3">
            <v-tab value="tv">剧集模板</v-tab>
            <v-tab value="movie">电影模板</v-tab>
          </v-tabs>

          <v-window v-model="activeTemplateTab">
            <!-- 剧集模板 -->
            <v-window-item value="tv">
              <!-- 快捷预设 -->
              <div class="text-subtitle-2 font-weight-medium text-primary mb-2">快捷预设</div>
              <div class="d-flex flex-wrap ga-2 mb-3">
                <v-btn
                  v-for="preset in ed2kTemplatePresets.tv"
                  :key="preset.template"
                  variant="tonal"
                  color="info"
                  size="small"
                  :prepend-icon="preset.icon"
                  :class="{ 'v-btn--active': templateDraft.tv === preset.template }"
                  @click="applyPreset(preset.template)"
                >
                  {{ preset.label }}
                </v-btn>
              </div>
              <v-textarea
                v-model="templateDraft.tv"
                label="剧集命名模板"
                variant="outlined"
                density="compact"
                :rows="2"
                auto-grow
                placeholder="{title} ({year}) - S{season_02}E{episode_02} - {team}"
                style="font-family: monospace;"
              />
            </v-window-item>

            <!-- 电影模板 -->
            <v-window-item value="movie">
              <div class="text-subtitle-2 font-weight-medium text-primary mb-2">快捷预设</div>
              <div class="d-flex flex-wrap ga-2 mb-3">
                <v-btn
                  v-for="preset in ed2kTemplatePresets.movie"
                  :key="preset.template"
                  variant="tonal"
                  color="info"
                  size="small"
                  :prepend-icon="preset.icon"
                  :class="{ 'v-btn--active': templateDraft.movie === preset.template }"
                  @click="applyPreset(preset.template)"
                >
                  {{ preset.label }}
                </v-btn>
              </div>
              <v-textarea
                v-model="templateDraft.movie"
                label="电影命名模板"
                variant="outlined"
                density="compact"
                :rows="2"
                auto-grow
                placeholder="{title} ({year}) - {team}"
                style="font-family: monospace;"
              />
            </v-window-item>
          </v-window>

          <!-- 恢复默认按钮 -->
          <div class="mt-2 mb-3">
            <v-btn variant="text" size="small" prepend-icon="mdi-refresh" @click="handleResetTemplate">恢复当前类型默认</v-btn>
          </div>

          <!-- 实时预览 -->
          <div class="pa-3 mb-3" style="background: rgba(var(--v-theme-on-surface), 0.03); border-radius: 8px;">
            <div class="d-flex align-center ga-2 mb-2">
              <span class="text-subtitle-2 font-weight-medium text-primary">实时预览</span>
              <v-chip size="x-small" color="primary" variant="flat">{{ activeTemplateTab === 'tv' ? '剧集' : '电影' }}</v-chip>
            </div>
            <div class="text-body-2 mb-1">
              <span class="text-medium-emphasis">渲染文件名：</span>
              <code style="font-family: monospace;">{{ previewFilename }}</code>
            </div>
            <div class="text-body-2" style="word-break: break-all;">
              <span class="text-medium-emphasis">完整 ED2K：</span>
              <code style="font-family: monospace; color: rgb(var(--v-theme-success));">{{ previewEd2kLink }}</code>
            </div>
          </div>

          <!-- 变量手册 -->
          <v-expansion-panels>
            <v-expansion-panel>
              <v-expansion-panel-title>可用变量手册</v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-for="g in ed2kVariableGroups" :key="g.title" class="mb-3">
                  <div class="text-subtitle-2 font-weight-bold text-primary mb-2 pb-1" style="border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);">{{ g.title }}</div>
                  <v-row dense>
                    <v-col v-for="(desc, v) in g.vars" :key="v" cols="12" sm="6">
                      <div class="d-flex align-center ga-2">
                        <code style="font-family: monospace; background: rgba(var(--v-theme-on-surface), 0.06); padding: 2px 6px; border-radius: 4px; font-size: 11px;">{{ v }}</code>
                        <span class="text-caption text-medium-emphasis">{{ desc }}</span>
                      </div>
                    </v-col>
                  </v-row>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showTemplateSettings = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSaveTemplate">保存模板</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 计算哈希弹窗 -->
    <v-dialog v-model="showCalculateModal" max-width="640" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="info">mdi-plus</v-icon>
          计算单文件哈希
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showCalculateModal = false" />
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4 form-section" style="max-height: 70vh; overflow-y: auto;">
          <v-text-field v-model="calculateForm.file_path" label="文件绝对路径 *" variant="outlined" density="compact" placeholder="/path/to/file.mkv" />

          <div class="section-title mb-2 mt-2">
            <v-icon size="16" color="primary">mdi-information-outline</v-icon>
            基本信息
          </div>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.tmdb_id" label="TMDB ID" variant="outlined" density="compact" /></v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="calculateForm.media_type" label="媒体类型" :items="[{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]" variant="outlined" density="compact" />
            </v-col>
          </v-row>
          <v-text-field v-model="calculateForm.title" label="标题" variant="outlined" density="compact" />
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.season" label="季号" type="number" variant="outlined" density="compact" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.episode" label="集号" variant="outlined" density="compact" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.year" label="年份" variant="outlined" density="compact" placeholder="如: 2024" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.secondary_category" label="二级分类" variant="outlined" density="compact" placeholder="如: 动画/日常" /></v-col>
          </v-row>

          <v-divider class="my-3" />
          <div class="section-title mb-2">
            <v-icon size="16" color="primary">mdi-tag-multiple-outline</v-icon>
            识别信息 (可选)
          </div>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.resolution" label="分辨率" variant="outlined" density="compact" placeholder="如: 1080P" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.team" label="制作组" variant="outlined" density="compact" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.video_encode" label="视频编码" variant="outlined" density="compact" placeholder="如: x265" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.audio_encode" label="音频编码" variant="outlined" density="compact" placeholder="如: AAC" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.video_effect" label="视频特效" variant="outlined" density="compact" placeholder="如: HDR" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.source" label="介质来源" variant="outlined" density="compact" placeholder="如: WEB-DL" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.subtitle" label="字幕语言" variant="outlined" density="compact" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.platform" label="发布平台" variant="outlined" density="compact" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.origin_country" label="原产地" variant="outlined" density="compact" placeholder="如: JP" /></v-col>
          </v-row>

          <div class="text-caption text-medium-emphasis mt-3 d-flex align-center ga-1">
            <v-icon size="14" color="warning">mdi-alert-outline</v-icon>
            需要读取整个文件，大文件或云盘文件可能耗时较长
          </div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="dialog-actions">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showCalculateModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" :loading="calculateLoading" @click="submitCalculate">开始计算</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
