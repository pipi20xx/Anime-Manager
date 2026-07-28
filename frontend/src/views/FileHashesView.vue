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
 * - 分页加载 + 加载更多
 */
import { ref, computed, onMounted } from 'vue'
import { fileHashApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import AppGlassCard from '@/components/common/AppGlassCard.vue'

defineOptions({ name: 'FileHashesView' })

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()

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

const hasMore = computed(() => hashList.value.length < hashTotal.value)

const currentPage = computed(() => Math.floor(offset.value / limit.value) + 1)
const totalPages = computed(() => Math.ceil(hashTotal.value / limit.value))

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
    // 后端返回 { status, total, limit, offset, data: [...] }
    // apiFetch 已解析 JSON，data 直接就是后端返回的对象
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

function filterByMediaType(type?: string) {
  filterMediaType.value = type
  searchHashes()
}

function toggleSortOrder() {
  sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  searchHashes()
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
      // 后端单条记录直接返回对象（response_model=FileHashResponse）
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
    // 只传有值的字段
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

onMounted(() => {
  fetchHashList()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <div>
        <h1 class="text-h5 font-weight-bold">文件哈希记录</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">共 {{ hashTotal }} 条 · SHA1 与 ED2K 哈希管理</div>
      </div>
      <div class="d-flex ga-2">
        <v-btn variant="tonal" color="info" prepend-icon="mdi-plus-outline" @click="openCalculateModal">计算哈希</v-btn>
      </div>
    </div>

    <!-- 搜索与筛选 -->
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="searchQuery"
        label="搜索文件名、标题、哈希、路径..."
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        class="hash-search-field"
        @keyup.enter="searchHashes"
        @click:clear="searchQuery = ''; searchHashes()"
      />
      <v-btn-toggle v-model="filterMediaType" mandatory density="compact" variant="outlined" divided>
        <v-btn size="small" :value="undefined" @click="filterByMediaType()">全部</v-btn>
        <v-btn size="small" value="tv" @click="filterByMediaType('tv')">剧集</v-btn>
        <v-btn size="small" value="movie" @click="filterByMediaType('movie')">电影</v-btn>
      </v-btn-toggle>
      <v-btn
        variant="tonal"
        size="small"
        :prepend-icon="sortOrder === 'desc' ? 'mdi-sort-descending' : 'mdi-sort-ascending'"
        @click="toggleSortOrder"
      >
        {{ sortOrder === 'desc' ? '最新' : '最早' }}
      </v-btn>
      <v-btn
        variant="tonal"
        size="small"
        :prepend-icon="showAdvancedFilter ? 'mdi-filter-remove-outline' : 'mdi-filter-outline'"
        @click="showAdvancedFilter = !showAdvancedFilter"
      >
        {{ showAdvancedFilter ? '收起筛选' : '高级筛选' }}
      </v-btn>
    </div>

    <!-- 高级筛选 -->
    <v-expand-transition>
      <div v-if="showAdvancedFilter" class="mb-4">
        <v-card class="glass-card pa-4">
          <v-row dense>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterTmdbId" label="TMDB ID" density="compact" variant="outlined" hide-details clearable />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterTeam" label="制作组" density="compact" variant="outlined" hide-details clearable />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-text-field v-model="filterSeason" label="季号" type="number" density="compact" variant="outlined" hide-details clearable />
            </v-col>
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
          </v-row>
          <div class="d-flex justify-end mt-3 ga-2">
            <v-btn variant="tonal" size="small" prepend-icon="mdi-refresh" @click="filterTmdbId = ''; filterTeam = ''; filterSeason = undefined; sortBy = 'calculated_at'">重置</v-btn>
            <v-btn color="primary" variant="flat" size="small" @click="searchHashes">应用筛选</v-btn>
          </div>
        </v-card>
      </div>
    </v-expand-transition>

    <!-- 分页信息 -->
    <div v-if="hashTotal > 0" class="text-caption text-medium-emphasis mb-3">
      显示 {{ offset + 1 }}-{{ Math.min(offset + limit, hashTotal) }} / 共 {{ hashTotal }} 条
    </div>

    <!-- 列表 -->
    <v-skeleton-loader v-if="loading && hashList.length === 0" type="list-item@8" />

    <div v-else-if="hashList.length > 0">
      <div class="hash-item-card mb-2" v-for="item in hashList" :key="item.id" @click="openDetail(item)" style="cursor: pointer">
        <div class="d-flex align-start justify-space-between">
          <div class="flex-grow-1 mr-2" style="min-width: 0">
            <!-- 标题行 -->
            <div class="d-flex align-center ga-2 mb-1">
              <v-chip v-if="item.media_type" size="x-small" variant="tonal" :color="item.media_type === 'tv' ? 'primary' : 'accent'">
                {{ formatMediaType(item.media_type) }}
              </v-chip>
              <span class="text-body-2 font-weight-medium text-truncate">{{ item.title || item.original_filename || '-' }}</span>
            </div>
            <!-- 文件名 -->
            <div v-if="item.original_filename && item.title" class="text-caption text-medium-emphasis text-truncate mb-1">
              {{ item.original_filename }}
            </div>
            <!-- 哈希值 -->
            <div class="d-flex ga-4 mt-1 text-caption text-medium-emphasis flex-wrap">
              <span v-if="item.sha1" class="hash-value" :title="item.sha1">
                <v-icon size="12" class="mr-1">mdi-fingerprint</v-icon>SHA1: {{ truncateHash(item.sha1) }}
              </span>
              <span v-if="item.ed2k" class="hash-value" :title="item.ed2k">
                <v-icon size="12" class="mr-1">mdi-link-variant</v-icon>ED2K: {{ truncateHash(item.ed2k) }}
              </span>
            </div>
            <!-- 信息行 -->
            <div class="d-flex ga-3 mt-1 text-caption text-medium-emphasis flex-wrap">
              <span v-if="item.file_size">
                <v-icon size="12" class="mr-1">mdi-file-outline</v-icon>{{ formatFileSize(item.file_size) }}
              </span>
              <span v-if="item.season">
                <v-icon size="12" class="mr-1">mdi-television-classic</v-icon>S{{ item.season }}{{ item.episode ? 'E' + item.episode : '' }}
              </span>
              <span v-if="item.team">
                <v-icon size="12" class="mr-1">mdi-account-group-outline</v-icon>{{ item.team }}
              </span>
              <span v-if="item.resolution">
                <v-icon size="12" class="mr-1">mdi-quality-high</v-icon>{{ item.resolution }}
              </span>
              <span v-if="item.video_encode">
                <v-icon size="12" class="mr-1">mdi-video-outline</v-icon>{{ item.video_encode }}
              </span>
              <span v-if="item.source">
                <v-icon size="12" class="mr-1">mdi-source-branch</v-icon>{{ item.source }}
              </span>
              <span v-if="item.calculated_at">
                <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>{{ formatDate(item.calculated_at) }}
              </span>
            </div>
            <!-- 源路径 -->
            <div v-if="item.source_path" class="text-caption text-medium-emphasis mt-1 hash-path text-truncate" :title="item.source_path">
              <v-icon size="12" class="mr-1">mdi-folder-outline</v-icon>{{ item.source_path }}
            </div>
          </div>
          <div class="d-flex flex-column align-end ga-1 flex-shrink-0">
            <v-chip v-if="item.tmdb_id" size="x-small" variant="outlined">TMDB: {{ item.tmdb_id }}</v-chip>
            <v-chip v-if="item.secondary_category" size="x-small" variant="tonal" color="primary">{{ item.secondary_category }}</v-chip>
          </div>
        </div>
      </div>

      <div v-if="hasMore" class="text-center pa-4">
        <v-btn variant="tonal" :loading="loading" @click="loadMore">
          加载更多 ({{ hashList.length }}/{{ hashTotal }})
        </v-btn>
      </div>
    </div>

    <div v-else class="text-center pa-8">
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

        <v-card-text class="pa-4">
          <v-skeleton-loader v-if="detailLoading" type="list-item@6" />

          <template v-else-if="detailItem">
            <!-- 基本信息 -->
            <div class="text-subtitle-2 font-weight-bold mb-2">基本信息</div>
            <div class="dc-detail-row"><span>标题</span><span class="font-weight-medium">{{ detailItem.title || '-' }}</span></div>
            <div class="dc-detail-row"><span>文件名</span><span class="font-weight-medium">{{ detailItem.original_filename || '-' }}</span></div>
            <div class="dc-detail-row"><span>媒体类型</span><span class="font-weight-medium">{{ formatMediaType(detailItem.media_type) }}</span></div>
            <div class="dc-detail-row"><span>文件大小</span><span class="font-weight-medium">{{ formatFileSize(detailItem.file_size) }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.tmdb_id"><span>TMDB ID</span><span class="font-weight-medium">{{ detailItem.tmdb_id }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.season"><span>季集</span><span class="font-weight-medium">S{{ detailItem.season }}E{{ detailItem.episode || '-' }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.year"><span>年份</span><span class="font-weight-medium">{{ detailItem.year }}</span></div>

            <v-divider class="my-3" />

            <!-- 识别信息 -->
            <div class="text-subtitle-2 font-weight-bold mb-2">识别信息</div>
            <div class="dc-detail-row" v-if="detailItem.team"><span>制作组</span><span class="font-weight-medium">{{ detailItem.team }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.resolution"><span>分辨率</span><span class="font-weight-medium">{{ detailItem.resolution }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.video_encode"><span>视频编码</span><span class="font-weight-medium">{{ detailItem.video_encode }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.audio_encode"><span>音频编码</span><span class="font-weight-medium">{{ detailItem.audio_encode }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.video_effect"><span>视频特效</span><span class="font-weight-medium">{{ detailItem.video_effect }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.source"><span>介质来源</span><span class="font-weight-medium">{{ detailItem.source }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.subtitle"><span>字幕</span><span class="font-weight-medium">{{ detailItem.subtitle }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.platform"><span>发布平台</span><span class="font-weight-medium">{{ detailItem.platform }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.secondary_category"><span>二级分类</span><span class="font-weight-medium text-primary">{{ detailItem.secondary_category }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.origin_country"><span>原产地</span><span class="font-weight-medium">{{ detailItem.origin_country }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.release_date"><span>发布日期</span><span class="font-weight-medium">{{ detailItem.release_date }}</span></div>

            <v-divider class="my-3" />

            <!-- 哈希值 -->
            <div class="text-subtitle-2 font-weight-bold mb-2">哈希值</div>
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
            <div class="text-subtitle-2 font-weight-bold mb-2">路径信息</div>
            <div class="dc-detail-row"><span>源路径</span><span class="font-weight-medium hash-path">{{ detailItem.source_path || '-' }}</span></div>
            <div class="dc-detail-row" v-if="detailItem.target_path"><span>目标路径</span><span class="font-weight-medium hash-path">{{ detailItem.target_path }}</span></div>
            <div class="dc-detail-row"><span>计算时间</span><span class="font-weight-medium">{{ detailItem.calculated_at || '-' }}</span></div>
          </template>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" @click="showDetailModal = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 计算哈希弹窗 -->
    <v-dialog v-model="showCalculateModal" max-width="640" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="info">mdi-plus-outline</v-icon>
          计算单文件哈希
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4">
          <v-text-field v-model="calculateForm.file_path" label="文件绝对路径 *" variant="outlined" density="compact" class="mb-3" placeholder="/path/to/file.mkv" />

          <div class="text-subtitle-2 font-weight-bold mb-2">基本信息</div>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.tmdb_id" label="TMDB ID" variant="outlined" density="compact" /></v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="calculateForm.media_type" label="媒体类型" :items="[{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]" variant="outlined" density="compact" />
            </v-col>
          </v-row>
          <v-text-field v-model="calculateForm.title" label="标题" variant="outlined" density="compact" class="mb-3" />
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.season" label="季号" type="number" variant="outlined" density="compact" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.episode" label="集号" variant="outlined" density="compact" /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.year" label="年份" variant="outlined" density="compact" placeholder="如: 2024" /></v-col>
            <v-col cols="12" sm="6"><v-text-field v-model="calculateForm.secondary_category" label="二级分类" variant="outlined" density="compact" placeholder="如: 动画/日常" /></v-col>
          </v-row>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">识别信息 (可选)</div>
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

          <div class="text-caption text-medium-emphasis mt-2">⚠️ 需要读取整个文件，大文件或云盘文件可能耗时较长</div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showCalculateModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" :loading="calculateLoading" @click="submitCalculate">开始计算</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
