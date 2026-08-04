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
  repreview: [ruleId: string]
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

// --- 重命名规则选择 ---
const selectedRuleId = ref('')

// 弹窗打开时默认选中第一条规则
watch(() => props.modelValue, (newVal) => {
  if (newVal && props.availableRules.length > 0) {
    selectedRuleId.value = props.availableRules[0].id
  }
})

// 切换规则时通知父组件重新预览
watch(selectedRuleId, (newId) => {
  if (newId && props.data) {
    emit('repreview', newId)
  }
})

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
            <div class="text-subtitle-1 font-weight-bold mb-3 d-flex align-center ga-2">
              <v-icon color="primary" size="22">mdi-flag-checkered</v-icon>
              最终识别结论
            </div>

            <v-card variant="outlined" class="mb-4 pa-4 recog-final-card">
              <v-row>
                <!-- 海报 -->
                <v-col v-if="data.final_result?.poster_path" cols="12" sm="3" md="2" class="d-flex justify-center">
                  <v-img
                    :src="getImg(data.final_result.poster_path)"
                    cover
                    rounded="xl"
                    aspect-ratio="2/3"
                    max-height="220"
                    class="recog-poster"
                  />
                </v-col>
                <!-- 详情 -->
                <v-col cols="12" sm="9" md="10">
                  <div class="d-flex align-center ga-2 flex-wrap">
                    <div class="text-h6 font-weight-bold">{{ data.final_result?.title || '未知标题' }}</div>
                    <v-chip v-if="data.final_result?.category" size="x-small" variant="flat" class="meta-tag meta-tag--type">
                      {{ data.final_result.category === 'tv' ? '剧集' : data.final_result.category === 'movie' ? '电影' : data.final_result.category }}
                    </v-chip>
                  </div>

                  <!-- 文本信息行 -->
                  <div class="recog-text-rows mt-4">
                    <div class="recog-text-row">
                      <span class="recog-text-label">季 / 集:</span>
                      <v-chip v-if="data.final_result?.season !== undefined && data.final_result.season !== null || data.final_result?.episode" size="x-small" variant="flat" class="meta-tag meta-tag--season">
                        <template v-if="data.final_result?.season !== undefined && data.final_result.season !== null">S{{ String(data.final_result.season).padStart(2, '0') }}</template><template v-if="data.final_result?.episode">E{{ String(data.final_result.episode).padStart(2, '0') }}</template>
                      </v-chip>
                      <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">无</v-chip>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">TMDB ID:</span>
                      <v-chip v-if="data.final_result?.tmdb_id && data.final_result.tmdb_id !== 'N/A'" :href="`https://www.themoviedb.org/${data.final_result.category?.includes('电影') ? 'movie' : 'tv'}/${data.final_result.tmdb_id}`" target="_blank" size="x-small" variant="flat" class="meta-tag meta-tag--tmdb">{{ data.final_result.tmdb_id }}</v-chip>
                      <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">N/A</v-chip>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">上映日期:</span>
                      <v-chip v-if="data.final_result?.release_date" size="x-small" variant="flat" class="meta-tag meta-tag--time">{{ data.final_result.release_date }}</v-chip>
                      <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">未知</v-chip>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">二级分类:</span>
                      <v-chip v-if="data.final_result?.secondary_category && data.final_result.secondary_category !== '123'" size="x-small" variant="flat" class="meta-tag meta-tag--subscribed">{{ data.final_result.secondary_category }}</v-chip>
                      <span v-else class="recog-text-value">{{ data.final_result?.secondary_category === '123' ? '未分类 (待修正)' : (data.final_result?.secondary_category || '-') }}</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">分辨率:</span>
                      <v-chip v-if="data.final_result?.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">{{ data.final_result.resolution }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">视频编码:</span>
                      <v-chip v-if="data.final_result?.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ data.final_result.video_encode }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">音频编码:</span>
                      <v-chip v-if="data.final_result?.audio_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ data.final_result.audio_encode }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">原产地:</span>
                      <v-chip v-if="data.final_result?.origin_country" size="x-small" variant="flat" class="meta-tag meta-tag--country">{{ data.final_result.origin_country }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">字幕语言:</span>
                      <v-chip v-if="data.final_result?.subtitle" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ data.final_result.subtitle }}</v-chip>
                      <span v-else class="recog-text-value">无</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">制作组:</span>
                      <v-chip v-if="data.final_result?.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">{{ data.final_result.team }}</v-chip>
                      <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--team">未知制作组</v-chip>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">发布平台:</span>
                      <v-chip v-if="data.final_result?.platform" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ data.final_result.platform }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">视频特效:</span>
                      <v-chip v-if="data.final_result?.video_effect" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ data.final_result.video_effect }}</v-chip>
                      <span v-else class="recog-text-value">-</span>
                    </div>
                    <div class="recog-text-row">
                      <span class="recog-text-label">处理后名:</span>
                      <span class="recog-text-value text-mono">{{ data.final_result?.processed_name || '-' }}</span>
                    </div>
                  </div>
                </v-col>
              </v-row>
            </v-card>

            <!-- 重命名预览 -->
            <div class="preview-section">
              <div class="d-flex align-center mb-2 ga-2">
                <v-icon size="16" color="info">mdi-folder-sync-outline</v-icon>
                <span class="text-subtitle-2 font-weight-bold">重命名路径预览</span>
                <v-spacer />
                <v-select
                  v-model="selectedRuleId"
                  :items="availableRules.map((r: any) => ({ title: r.name, value: r.id }))"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 220px"
                  label="重命名规则"
                />
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

/* 最终识别结论卡片 */
.recog-final-card {
  border: 1px solid rgba(var(--v-theme-primary), 0.2);
  background: transparent !important;
}
.recog-poster {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}
/* 文本信息行 */
.recog-text-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.recog-text-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
}
.recog-text-label {
  color: rgba(var(--v-theme-on-surface), 0.4);
  width: 80px;
  flex-shrink: 0;
  text-align: right;
}
.recog-text-value {
  color: rgba(var(--v-theme-on-surface), 0.7);
  word-break: break-all;
}
.text-mono {
  font-family: monospace;
  color: rgb(var(--v-theme-warning));
}

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
