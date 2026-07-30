<script setup lang="ts">
/**
 * RecognitionModal — 单文件识别弹窗
 *
 * 对标旧前端 RecognitionModalDesktop，功能：
 * - 识别策略开关（动漫优先/本地数据中心/BGM优先/BGM故障转移/强制单文件/智能记忆/合集增强），持久化到 localStorage
 * - 强制参数输入（TMDB ID / 类型 / 季 / 集）
 * - TMDB 快捷搜索（搜剧名自动填入 ID 和类型）
 * - 识别结果展示（海报 + 详细元数据 + TMDB链接）
 * - 重命名预览
 * - 哈希计算（SHA1/ED2K）
 * - 深度审计日志
 */
import { reactive, ref, watch } from 'vue'
import { tmdbApi, fileHashApi } from '@/api'
import { useNotification } from '@/composables'

const props = defineProps<{
  modelValue: boolean
  file: any
  data: any
  previewPath: string
  loading: boolean
  isRenaming: boolean
  availableRules: any[]
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  recognize: [params: any]
  rename: []
}>()

const { success, error: showError, warning } = useNotification()

// --- 策略偏好持久化 ---
const STRATEGY_KEYS = [
  'anime_priority', 'offline_priority', 'bangumi_priority',
  'bangumi_failover', 'force_filename', 'series_fingerprint', 'batch_enhancement'
] as const
const STORAGE_KEY = 'recognition_strategy_prefs'

function loadStrategyPrefs(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return {}
}

function saveStrategyPrefs(params: Record<string, any>) {
  const prefs: Record<string, boolean> = {}
  for (const key of STRATEGY_KEYS) {
    prefs[key] = params[key]
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
}

// --- 强制参数 ---
const savedPrefs = loadStrategyPrefs()
const forcedParams = reactive({
  tmdb_id: '' as string,
  type: null as string | null,
  season: '' as string,
  episode: '' as string,
  anime_priority: savedPrefs.anime_priority ?? false,
  offline_priority: savedPrefs.offline_priority ?? false,
  bangumi_priority: savedPrefs.bangumi_priority ?? false,
  bangumi_failover: savedPrefs.bangumi_failover ?? false,
  force_filename: savedPrefs.force_filename ?? false,
  series_fingerprint: savedPrefs.series_fingerprint ?? false,
  batch_enhancement: savedPrefs.batch_enhancement ?? false,
})

// 策略开关变化时自动保存
for (const key of STRATEGY_KEYS) {
  watch(() => forcedParams[key], () => {
    saveStrategyPrefs(forcedParams)
  })
}

// --- TMDB 搜索 ---
const testSearch = reactive({ keyword: '', loading: false, results: [] as any[] })

async function searchTmdbForTest() {
  if (!testSearch.keyword) return
  testSearch.loading = true
  try {
    const data = await tmdbApi.search({
      query: testSearch.keyword,
      type: forcedParams.type || 'multi',
    })
    testSearch.results = data?.results || []
  } catch {
    showError('搜索失败')
  } finally {
    testSearch.loading = false
  }
}

function selectSearchResult(res: any) {
  forcedParams.tmdb_id = String(res.id)
  forcedParams.type = res.media_type || forcedParams.type
  testSearch.results = []
}

// --- 哈希计算 ---
const isHashing = ref(false)
const hashResult = ref<any>(null)

async function calculateHash() {
  if (!props.file?.path || !props.data?.final_result) {
    warning('缺少文件路径或识别结果')
    return
  }
  isHashing.value = true
  hashResult.value = null
  try {
    const fr = props.data.final_result
    const data = await fileHashApi.calculate({
      file_path: props.file.path,
      tmdb_id: fr.tmdb_id && fr.tmdb_id !== 'N/A' ? String(fr.tmdb_id) : undefined,
      title: fr.title || undefined,
      season: fr.season !== undefined ? Number(fr.season) : undefined,
      episode: fr.episode !== undefined ? String(fr.episode) : undefined,
      media_type: fr.category || undefined,
      resolution: fr.resolution || undefined,
      team: fr.team || undefined,
      video_encode: fr.video_encode || undefined,
    })
    if (data?.status === 'success') {
      hashResult.value = data.data
      success(data.message || '哈希计算完成，已写入数据库')
    } else {
      showError(data?.detail || '哈希计算失败')
    }
  } catch (e: any) {
    showError(e?.message || '哈希计算请求失败')
  } finally {
    isHashing.value = false
  }
}

// --- 图片 URL ---
function getImg(path: string): string {
  if (!path) return ''
  if (path.includes('/api/system/img')) return path
  if (path.startsWith('http')) return path
  return `/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
}

// --- 审计日志分类 ---
function getLogClass(log: string): string {
  if (log.includes('深度审计启动') || log.includes('🚀')) return 'log-p'
  if (log.includes('[DEBUG]')) return 'log-d'
  if (log.includes('🎯') || log.includes('成功')) return 'log-s'
  if (log.includes('✂️') || log.includes('拦截')) return 'log-w'
  if (log.includes('📢') || log.includes('结论')) return 'log-i'
  return ''
}

// --- 识别 ---
function handleRecognize() {
  emit('recognize', { ...forcedParams })
}

// --- 弹窗打开时重置非策略字段 ---
watch(() => props.modelValue, (newVal) => {
  if (newVal && !props.loading) {
    Object.assign(forcedParams, {
      tmdb_id: '', type: null, season: '', episode: ''
    })
    testSearch.keyword = ''
    testSearch.results = []
    hashResult.value = null
  }
})
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="850" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-head-cog-outline</v-icon>
        单文件识别
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="emit('update:modelValue', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4" style="max-height: 70vh; overflow-y: auto">
        <v-skeleton-loader v-if="loading" type="paragraph, paragraph" />

        <template v-else>
          <!-- 识别参数配置 -->
          <div class="config-section mb-4">
            <div class="section-title mb-3">
              <v-icon size="18" color="info">mdi-wrench-outline</v-icon>
              识别参数配置 (仅本次生效)
            </div>

            <!-- 策略开关 -->
            <div class="strategy-grid mb-4">
              <div
                v-for="item in [
                  { key: 'anime_priority', title: '动漫识别优化', desc: '开启后提升动画匹配精度，过滤同名真人剧' },
                  { key: 'offline_priority', title: '本地数据中心', desc: '优先碰撞本地数据库，实现毫秒级离线匹配' },
                  { key: 'bangumi_priority', title: 'Bangumi 数据源优先', desc: '针对新番或缺失条目，优先尝试 BGM 镜像' },
                  { key: 'bangumi_failover', title: 'Bangumi 故障转移', desc: '当 TMDB 搜索失败时，自动使用 BGM 补全' },
                  { key: 'force_filename', title: '强制单文件模式', desc: '将完整输入作为文件名解析，无视路径干扰' },
                  { key: 'series_fingerprint', title: '智能记忆', desc: '自动记住系列特征，后续文件实现秒级拦截' },
                  { key: 'batch_enhancement', title: '合集识别增强', desc: '支持解析 01-12 等合集，自动计算集数区间' },
                ]"
                :key="item.key"
                class="strategy-row"
              >
                <div class="strategy-info">
                  <div class="strategy-label">{{ item.title }}</div>
                  <div class="strategy-desc">{{ item.desc }}</div>
                </div>
                <v-switch v-model="forcedParams[item.key]" density="compact" color="primary" hide-details />
              </div>
            </div>

            <!-- 强制参数 -->
            <v-row dense class="mb-2">
              <v-col cols="3">
                <v-text-field v-model="forcedParams.tmdb_id" label="TMDB ID" placeholder="TMDB ID" density="compact" hide-details variant="outlined" />
              </v-col>
              <v-col cols="3">
                <v-select
                  v-model="forcedParams.type"
                  label="资源类型"
                  :items="[{ title: '自动', value: null }, { title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]"
                  density="compact" hide-details variant="outlined" clearable
                />
              </v-col>
              <v-col cols="3">
                <v-text-field v-model="forcedParams.season" label="指定季" placeholder="指定季" density="compact" hide-details variant="outlined" />
              </v-col>
              <v-col cols="3">
                <v-text-field v-model="forcedParams.episode" label="指定集" placeholder="指定集" density="compact" hide-details variant="outlined" />
              </v-col>
            </v-row>

            <!-- TMDB 快捷搜索 -->
            <v-text-field
              v-model="testSearch.keyword"
              placeholder="快捷搜索剧名找 ID..."
              density="compact"
              hide-details
              variant="outlined"
              prepend-inner-icon="mdi-magnify"
              @keydown.enter="searchTmdbForTest"
              class="mb-2"
            >
              <template #append-inner>
                <v-btn color="primary" variant="flat" size="small" :loading="testSearch.loading" @click="searchTmdbForTest">
                  搜索
                </v-btn>
              </template>
            </v-text-field>

            <!-- 搜索结果 -->
            <div v-if="testSearch.results.length > 0" class="search-results-list">
              <div
                v-for="res in testSearch.results"
                :key="res.id"
                class="search-result-item"
                @click="selectSearchResult(res)"
              >
                <v-img v-if="res.poster_path" :src="getImg(res.poster_path)" width="50" height="75" cover class="rounded" />
                <div v-else class="poster-placeholder-sm">无</div>
                <div class="search-result-info">
                  <div class="search-result-title">{{ res.title }} ({{ res.year }})</div>
                  <div class="search-result-sub">ID: {{ res.id }} · {{ res.category }} · {{ res.original_title || '-' }}</div>
                  <div v-if="res.genres?.length" class="search-result-sub">流派：{{ res.genres.join(' / ') }}</div>
                </div>
              </div>
            </div>

            <!-- 开始识别按钮 -->
            <v-btn color="primary" variant="flat" block size="small" class="mt-3" :loading="loading" prepend-icon="mdi-play-circle-outline" @click="handleRecognize">
              开始识别
            </v-btn>
          </div>

          <!-- 识别结果 -->
          <div v-if="data" class="result-section">
            <!-- 海报 + 详情 -->
            <div class="result-main-layout">
              <div class="poster-box">
                <v-img v-if="data.final_result?.poster_path" :src="getImg(data.final_result.poster_path)" width="120" class="poster-img rounded" cover />
                <div v-else class="poster-placeholder">无海报</div>
              </div>
              <div class="details-box">
                <div class="result-title">{{ data.final_result?.title }}</div>

                <!-- 标签行 -->
                <div class="tags-row">
                  <v-chip v-if="data.final_result?.category" size="small" variant="tonal" color="primary">
                    {{ data.final_result.category }}
                  </v-chip>
                  <v-chip v-if="data.final_result?.secondary_category" size="small" variant="tonal" color="info">
                    🏷️ {{ data.final_result.secondary_category }}
                  </v-chip>
                  <a
                    v-if="data.final_result?.tmdb_id && data.final_result.tmdb_id !== 'N/A'"
                    :href="`https://www.themoviedb.org/${data.final_result.category?.includes('电影') ? 'movie' : 'tv'}/${data.final_result.tmdb_id}`"
                    target="_blank"
                    class="tmdb-link"
                  >
                    TMDB: {{ data.final_result.tmdb_id }}
                  </a>
                  <span v-else class="tmdb-text">TMDB: {{ data.final_result?.tmdb_id || 'N/A' }}</span>
                  <span v-if="data.final_result?.release_date" class="date-text">📅 {{ data.final_result.release_date }}</span>
                </div>

                <!-- 规格标签 -->
                <div class="specs-row">
                  <span v-if="data.final_result?.resolution" class="spec-badge">{{ data.final_result.resolution }}</span>
                  <span v-if="data.final_result?.video_encode" class="spec-badge blue">{{ data.final_result.video_encode }}</span>
                  <span v-if="data.final_result?.audio_encode" class="spec-badge blue">{{ data.final_result.audio_encode }}</span>
                </div>

                <!-- 信息网格 -->
                <div class="info-grid">
                  <div class="info-item">
                    <div class="info-label">年份</div>
                    <div class="info-value">{{ data.final_result?.year || '-' }}</div>
                  </div>
                  <div class="info-item">
                    <div class="info-label">季号</div>
                    <div class="info-value">{{ data.final_result?.season !== undefined ? 'S' + data.final_result.season : '-' }}</div>
                  </div>
                  <div class="info-item">
                    <div class="info-label">集数</div>
                    <div class="info-value">{{ data.final_result?.episode !== undefined ? 'E' + data.final_result.episode : '-' }}</div>
                  </div>
                  <div class="info-item">
                    <div class="info-label">介质来源</div>
                    <div class="info-value">{{ data.final_result?.source || '-' }}</div>
                  </div>
                </div>

                <!-- 文本信息 -->
                <div class="text-rows">
                  <div class="text-row"><span class="text-label">原产地</span><span class="text-value">{{ data.final_result?.origin_country || '-' }}</span></div>
                  <div class="text-row"><span class="text-label">字幕语言</span><span class="text-value">{{ data.final_result?.subtitle || '无' }}</span></div>
                  <div class="text-row"><span class="text-label">制作组</span><span class="text-value team-value">{{ data.final_result?.team || '未知' }}</span></div>
                  <div class="text-row"><span class="text-label">发布平台</span><span class="text-value">{{ data.final_result?.platform || '-' }}</span></div>
                  <div class="text-row"><span class="text-label">视频特效</span><span class="text-value">{{ data.final_result?.video_effect || '-' }}</span></div>
                  <div class="text-row"><span class="text-label">处理后名</span><span class="text-value mono-value">{{ data.final_result?.processed_name }}</span></div>
                </div>
              </div>
            </div>

            <!-- 重命名预览 -->
            <div class="preview-section">
              <div class="section-title">
                <v-icon size="16" color="info">mdi-folder-sync-outline</v-icon>
                重命名路径预览
              </div>
              <div class="preview-path">{{ previewPath || (loading ? '正在计算...' : '无法生成预览') }}</div>
            </div>

            <!-- 哈希结果 -->
            <div v-if="hashResult" class="hash-section">
              <div class="section-title" style="color: rgb(var(--v-theme-success))">
                <v-icon size="16" color="success">mdi-check-circle-outline</v-icon>
                哈希已计算并入库
              </div>
              <div class="hash-info">
                <div class="hash-row"><span class="hash-label">SHA1</span><span class="hash-value mono">{{ hashResult.sha1 }}</span></div>
                <div class="hash-row"><span class="hash-label">ED2K</span><span class="hash-value mono">{{ hashResult.ed2k }}</span></div>
                <div class="hash-row"><span class="hash-label">ED2K链接</span><span class="hash-value mono" style="font-size: 11px">{{ hashResult.ed2k_link }}</span></div>
              </div>
            </div>

            <!-- 审计日志 -->
            <v-expansion-panels v-if="data.logs?.length" class="mt-3">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <div class="d-flex align-center ga-2">
                    <v-icon size="16">mdi-magnify</v-icon>
                    查看深度识别审计日志
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <div class="audit-log-box">
                    <div v-for="(log, i) in data.logs" :key="i" :class="['recog-log-line', getLogClass(log)]">
                      <span class="log-idx">{{ String(Number(i) + 1).padStart(2, '0') }}</span>
                      <span class="log-text">{{ log }}</span>
                    </div>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn v-if="data" color="info" variant="tonal" :loading="isHashing" prepend-icon="mdi-calculator" @click="calculateHash">
          计算哈希
        </v-btn>
        <v-btn v-if="data" color="primary" variant="flat" :loading="isRenaming" prepend-icon="mdi-rename-box" @click="emit('rename')">
          确认重命名
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 策略网格 */
.strategy-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strategy-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(var(--v-theme-surface), 0.6);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.strategy-info { min-width: 0; }
.strategy-label { font-size: 14px; font-weight: 600; color: rgba(var(--v-theme-on-surface), 0.87); margin-bottom: 2px; }
.strategy-desc { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.5); line-height: 1.4; }

/* 识别结果 */
.result-main-layout { display: flex; gap: 20px; align-items: flex-start; margin-bottom: 16px; }
.poster-box { flex-shrink: 0; }
.poster-img { border-radius: 8px; }
.poster-placeholder {
  width: 120px; height: 180px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.3);
}
.details-box { flex-grow: 1; min-width: 0; }
.result-title { font-size: 20px; font-weight: bold; color: rgba(var(--v-theme-on-surface), 0.87); line-height: 1.3; margin-bottom: 8px; }

.tags-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.tmdb-link { font-family: monospace; color: rgb(var(--v-theme-primary)); font-size: 11px; text-decoration: none; }
.tmdb-link:hover { text-decoration: underline; }
.tmdb-text { font-family: monospace; color: rgba(var(--v-theme-on-surface), 0.4); font-size: 11px; }
.date-text { color: rgb(var(--v-theme-primary)); font-size: 12px; }

.specs-row { display: flex; gap: 6px; margin-bottom: 12px; }
.spec-badge {
  padding: 1px 6px; border-radius: 4px; font-size: 10px;
  background: rgba(var(--v-theme-surface), 0.8);
  color: rgba(var(--v-theme-on-surface), 0.5);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}
.spec-badge.blue { color: rgb(var(--v-theme-info)); border-color: rgba(var(--v-theme-info), 0.3); }

.info-grid {
  display: flex; border-radius: 6px; margin-bottom: 16px;
  overflow: hidden; border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.info-item {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  padding: 8px 4px;
}
.info-item:not(:last-child) { border-right: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.info-label { font-size: 10px; color: rgba(var(--v-theme-on-surface), 0.4); text-transform: uppercase; font-weight: bold; margin-bottom: 2px; }
.info-value { font-weight: bold; font-size: 14px; color: rgb(var(--v-theme-primary)); }

.text-rows { font-size: 12px; display: flex; flex-direction: column; gap: 4px; font-family: monospace; }
.text-row { display: flex; gap: 12px; align-items: baseline; padding: 2px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04); }
.text-row:last-child { border-bottom: none; }
.text-label { color: rgba(var(--v-theme-on-surface), 0.4); width: 70px; flex-shrink: 0; text-align: right; font-size: 11px; text-transform: uppercase; }
.text-value { color: rgba(var(--v-theme-on-surface), 0.75); word-break: break-all; }
.team-value { color: rgb(var(--v-theme-success)); font-weight: bold; }
.mono-value { font-family: monospace; color: rgb(var(--v-theme-warning)); }

/* 预览 */
.preview-section {
  background: rgba(var(--v-theme-surface), 0.5);
  padding: 14px; border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.preview-path {
  font-family: monospace; font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.87);
  word-break: break-all; padding: 8px 0;
}

/* 哈希 */
.hash-section {
  background: rgba(var(--v-theme-surface), 0.5);
  padding: 14px; border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-success), 0.3);
  margin-top: 12px;
}
.hash-info { display: flex; flex-direction: column; gap: 4px; }
.hash-row { display: flex; gap: 8px; align-items: baseline; }
.hash-label { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.4); width: 60px; flex-shrink: 0; text-align: right; }
.hash-value { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); word-break: break-all; }
.mono { font-family: monospace; }

/* 审计日志 */
.audit-log-box {
  padding: 12px; border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  font-family: monospace; font-size: 12px; line-height: 1.6;
}
.recog-log-line { display: flex; gap: 8px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04); padding: 2px 0; }
.log-idx { color: rgba(var(--v-theme-on-surface), 0.3); font-size: 10px; width: 20px; flex-shrink: 0; }
.log-text { color: rgba(var(--v-theme-on-surface), 0.6); }

.log-p { color: rgb(var(--v-theme-primary)); font-weight: bold; }
.log-d { color: rgb(var(--v-theme-info)); }
.log-s { color: rgb(var(--v-theme-primary)); }
.log-w { color: rgb(var(--v-theme-warning)); }
.log-i { color: rgb(var(--v-theme-warning)); font-weight: bold; }
</style>
