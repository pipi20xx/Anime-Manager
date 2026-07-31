<script setup lang="ts">
/**
 * HomeView — 识别调试台
 *
 * 功能:
 * - 文件名识别测试
 * - 高级参数与临时调试
 * - 识别偏好设置
 * - 识别结果展示（最终识别结论 + 本地解析元数据 + TMDB原始详情 + 规则应用日志）
 * - 识别审计日志查看（全量日志流）
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRecognitionStore } from '@/stores'

defineOptions({ name: 'HomeView' })

const store = useRecognitionStore()
const activeTab = ref('dashboard')

// 加载偏好 & 保存偏好
onMounted(() => {
  store.loadPreferences()
})

watch([
  () => store.animePriority,
  () => store.offlinePriority,
  () => store.bangumiPriority,
  () => store.bangumiFailover,
  () => store.forceFilename,
  () => store.seriesFingerprint,
  () => store.batchEnhancement,
], () => {
  store.savePreferences()
})

// --- 最终识别结论 ---
const finalData = computed(() => store.data?.final_result)
const tmdbUrl = computed(() => {
  const id = finalData.value?.tmdb_id
  if (!id) return ''
  const cat = finalData.value?.category || ''
  const mediaType = cat.includes('电影') ? 'movie' : 'tv'
  return `https://www.themoviedb.org/${mediaType}/${id}`
})

// --- 本地解析元数据 ---
const rawData = computed(() => store.data?.raw_meta || {})
function safeVal(val: any, fallback = '-'): string {
  return val !== undefined && val !== null && val !== '' ? String(val) : fallback
}

// --- TMDB 原始详情 ---
const tmdbData = computed(() => store.data?.tmdb_match || null)

// --- 规则应用日志（过滤） ---
const ruleLogs = computed(() => {
  const logs = store.logs || []
  return logs.filter(log => {
    const s = String(log)
    return s.includes('[规则]') || s.includes('[Render]') || s.includes('[特权]') ||
           s.includes('🧠') || s.includes('🏷️') || s.includes('[Shield]') ||
           s.includes('[BatchHelper]') || s.includes('[Fingerprint]')
  })
})

interface ParsedRuleLog { type: string; icon: string; content: string }
const parsedRuleLogs = computed<ParsedRuleLog[]>(() => {
  return ruleLogs.value.map(log => {
    const s = String(log)
    let type = 'other'
    let icon = '⚙️'
    if (s.includes('[特权]')) { type = 'privilege'; icon = '⚡' }
    else if (s.includes('[规则][社区]')) { type = 'community'; icon = '🌐' }
    else if (s.includes('[规则][内置]') || s.includes('[规则][规范化]')) { type = 'builtin'; icon = '🔧' }
    else if (s.includes('[Render]')) { type = 'render'; icon = '🏷️' }
    else if (s.includes('🧠') || s.includes('[Fingerprint]')) { type = 'memory'; icon = '🧠' }
    else if (s.includes('[Shield]')) { type = 'shield'; icon = '🛡️' }
    else if (s.includes('[BatchHelper]')) { type = 'batch'; icon = '📦' }
    return { type, icon, content: s }
  })
})

// --- 审计日志 Tab ---
const logSearchKeyword = ref('')
const filteredLogs = computed(() => {
  if (!logSearchKeyword.value.trim()) return store.logs
  const kw = logSearchKeyword.value.toLowerCase()
  return store.logs.filter(log => String(log).toLowerCase().includes(kw))
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <div>
        <h1 class="text-h5 font-weight-bold">识别调试台</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">文件名识别测试与结果查看</div>
      </div>
    </div>

    <!-- 响应式分栏 -->
    <v-row>
      <!-- 主区域 -->
      <v-col cols="12" lg="9">
        <v-card class="glass-card">
          <v-tabs v-model="activeTab" color="primary" class="px-4">
            <v-tab value="dashboard">识别测试</v-tab>
            <v-tab value="logs">识别审计日志</v-tab>
          </v-tabs>

          <v-divider />

          <v-window v-model="activeTab">
            <!-- ============ 识别测试 Tab ============ -->
            <v-window-item value="dashboard">
              <div class="pa-4 pa-md-6">
                <!-- 搜索入口 -->
                <div class="mb-6">
                  <v-text-field
                    v-model="store.filename"
                    placeholder="粘贴文件名或完整路径进行深度解析..."
                    :loading="store.loading"
                    :disabled="store.loading"
                    prepend-inner-icon="mdi-magnify"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                    clearable
                    @keydown.enter="store.performRecognition()"
                  >
                    <template #append-inner>
                      <v-btn
                        color="primary"
                        variant="flat"
                        size="small"
                        :loading="store.loading"
                        @click="store.performRecognition()"
                      >
                        识别
                      </v-btn>
                    </template>
                  </v-text-field>
                </div>

                <!-- 高级参数折叠面板 -->
                <v-expansion-panels class="mb-6">
                  <v-expansion-panel>
                    <v-expansion-panel-title>
                      <div class="d-flex align-center ga-2">
                        <v-icon color="primary" size="20">mdi-tune-variant</v-icon>
                        <span class="font-weight-medium">高级参数与临时调试</span>
                      </div>
                    </v-expansion-panel-title>
                    <v-expansion-panel-text>
                      <!-- TMDB 搜索辅助 -->
                      <div class="mb-4">
                        <v-text-field
                          v-model="store.sandboxKeyword"
                          placeholder="搜索辅助 (TMDB)，输入剧名..."
                          :loading="store.sandboxLoading"
                          prepend-inner-icon="mdi-magnify"
                          variant="outlined"
                          density="compact"
                          hide-details
                          clearable
                          @keydown.enter="store.searchTmdbForSandbox()"
                        >
                          <template #append-inner>
                            <v-btn size="x-small" variant="text" icon="mdi-arrow-right" @click="store.searchTmdbForSandbox()" />
                          </template>
                        </v-text-field>

                        <!-- 搜索结果 -->
                        <div v-if="store.sandboxResults.length > 0" class="search-results-box mt-2">
                          <div
                            v-for="res in store.sandboxResults"
                            :key="res.id"
                            class="search-result-item"
                            @click="store.selectSandboxResult(res)"
                          >
                            <v-avatar v-if="res.poster_path" size="50" rounded="lg" class="mr-3 flex-shrink-0">
                              <v-img :src="store.getImg(res.poster_path)" cover />
                            </v-avatar>
                            <div class="flex-grow-1" style="min-width: 0">
                              <div class="font-weight-medium text-body-2 text-truncate">{{ res.title || res.name }}</div>
                              <div class="text-caption text-medium-emphasis">ID: {{ res.id }} · {{ res.media_type }} · {{ res.original_title || res.original_name || '-' }}</div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- 强制参数 -->
                      <v-row class="mb-4">
                        <v-col cols="12" sm="6" md="3">
                          <v-text-field v-model="store.forcedTmdbId" label="强制 ID" placeholder="TMDB ID" density="compact" hide-details />
                        </v-col>
                        <v-col cols="12" sm="6" md="3">
                          <v-select
                            v-model="store.forcedType"
                            label="媒体类型"
                            :items="[{ title: '自动', value: null }, { title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]"
                            density="compact"
                            hide-details
                            clearable
                          />
                        </v-col>
                        <v-col cols="12" sm="6" md="3">
                          <v-text-field v-model="store.forcedSeason" label="强制季号" placeholder="Season" density="compact" hide-details />
                        </v-col>
                        <v-col cols="12" sm="6" md="3">
                          <v-text-field v-model="store.forcedEpisode" label="强制集号" placeholder="Episode" density="compact" hide-details />
                        </v-col>
                      </v-row>

                      <v-divider class="my-4" />

                      <div class="text-caption text-medium-emphasis mb-2">临时规则注入 (仅本次生效)</div>

                      <v-row>
                        <v-col cols="12" sm="6">
                          <v-textarea v-model="store.tempNoise" label="自定义识别词" placeholder="屏蔽词 (Regex)" auto-grow rows="2" density="compact" hide-details />
                        </v-col>
                        <v-col cols="12" sm="6">
                          <v-textarea v-model="store.tempGroups" label="自定义制作组" placeholder="自定义制作组" auto-grow rows="2" density="compact" hide-details />
                        </v-col>
                        <v-col cols="12" sm="6">
                          <v-textarea v-model="store.tempRender" label="自定义渲染词" placeholder="自定义渲染词" auto-grow rows="2" density="compact" hide-details />
                        </v-col>
                        <v-col cols="12" sm="6">
                          <v-textarea v-model="store.tempPrivilege" label="自定义特权规则" placeholder="特权规则 (每行一条)" auto-grow rows="2" density="compact" hide-details />
                        </v-col>
                      </v-row>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>

                <!-- ============ 识别结果 ============ -->
                <div v-if="finalData" class="recognition-result">
                  <!-- ========== 最终识别结论 ========== -->
                  <div class="text-subtitle-1 font-weight-bold mb-3 d-flex align-center ga-2">
                    <v-icon color="primary" size="22">mdi-flag-checkered</v-icon>
                    最终识别结论
                  </div>

                  <v-card variant="outlined" class="mb-4 pa-4 recog-final-card">
                    <v-row>
                      <!-- 海报 -->
                      <v-col v-if="finalData.poster_path" cols="12" sm="3" md="2" class="d-flex justify-center">
                        <v-img
                          :src="store.getImg(finalData.poster_path)"
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
                          <div class="text-h6 font-weight-bold">{{ finalData.title || '未知标题' }}</div>
                          <v-chip v-if="finalData.category" size="x-small" variant="flat" class="meta-tag meta-tag--type">
                            {{ finalData.category === 'tv' ? '剧集' : finalData.category === 'movie' ? '电影' : finalData.category }}
                          </v-chip>
                        </div>

                        <!-- 文本信息行 -->
                        <div class="recog-text-rows mt-4">
                          <div class="recog-text-row">
                            <span class="recog-text-label">季 / 集:</span>
                            <v-chip v-if="finalData.season !== undefined && finalData.season !== null || finalData.episode" size="x-small" variant="flat" class="meta-tag meta-tag--season">
                              <template v-if="finalData.season !== undefined && finalData.season !== null">S{{ String(finalData.season).padStart(2, '0') }}</template><template v-if="finalData.episode">E{{ String(finalData.episode).padStart(2, '0') }}</template>
                            </v-chip>
                            <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">无</v-chip>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">TMDB ID:</span>
                            <a v-if="tmdbUrl" :href="tmdbUrl" target="_blank" class="meta-tag meta-tag--tmdb">{{ finalData.tmdb_id }}</a>
                            <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">N/A</v-chip>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">上映日期:</span>
                            <v-chip v-if="finalData.release_date" size="x-small" variant="flat" class="meta-tag meta-tag--time">{{ finalData.release_date }}</v-chip>
                            <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--miss">未知</v-chip>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">二级分类:</span>
                            <v-chip v-if="finalData.secondary_category && finalData.secondary_category !== '123'" size="x-small" variant="flat" class="meta-tag meta-tag--subscribed">{{ finalData.secondary_category }}</v-chip>
                            <span v-else class="recog-text-value">{{ finalData.secondary_category === '123' ? '未分类 (待修正)' : safeVal(finalData.secondary_category) }}</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">分辨率:</span>
                            <v-chip v-if="finalData.resolution" size="x-small" variant="flat" class="meta-tag meta-tag--resolution">{{ finalData.resolution }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">视频编码:</span>
                            <v-chip v-if="finalData.video_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ finalData.video_encode }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">音频编码:</span>
                            <v-chip v-if="finalData.audio_encode" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ finalData.audio_encode }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">原产地:</span>
                            <v-chip v-if="finalData.origin_country" size="x-small" variant="flat" class="meta-tag meta-tag--country">{{ finalData.origin_country }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">字幕语言:</span>
                            <v-chip v-if="finalData.subtitle" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ finalData.subtitle }}</v-chip>
                            <span v-else class="recog-text-value">无</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">制作组:</span>
                            <v-chip v-if="finalData.team" size="x-small" variant="flat" class="meta-tag meta-tag--team">{{ finalData.team }}</v-chip>
                            <v-chip v-else size="x-small" variant="flat" class="meta-tag meta-tag--team">未知制作组</v-chip>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">发布平台:</span>
                            <v-chip v-if="finalData.platform" size="x-small" variant="flat" class="meta-tag meta-tag--source">{{ finalData.platform }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">视频特效:</span>
                            <v-chip v-if="finalData.video_effect" size="x-small" variant="flat" class="meta-tag meta-tag--encode">{{ finalData.video_effect }}</v-chip>
                            <span v-else class="recog-text-value">-</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">处理后名:</span>
                            <span class="recog-text-value text-mono">{{ safeVal(finalData.processed_name) }}</span>
                          </div>
                          <div class="recog-text-row">
                            <span class="recog-text-label">原始文件:</span>
                            <span class="recog-text-value text-mono recog-filename">{{ safeVal(finalData.filename) }}</span>
                          </div>
                        </div>

                        <!-- TMDB 详情链接 -->
                        <div v-if="finalData.tmdb_id" class="mt-3">
                          <v-btn
                            size="small"
                            variant="tonal"
                            color="primary"
                            prepend-icon="mdi-open-in-new"
                            :to="`/tmdb/${finalData.category === '电影' ? 'movie' : 'tv'}/${finalData.tmdb_id}`"
                          >
                            查看 TMDB 详情
                          </v-btn>
                        </div>
                      </v-col>
                    </v-row>
                  </v-card>

                  <!-- ========== 本地解析元数据 + TMDB 原始详情 (并排) ========== -->
                  <v-row class="mb-4">
                    <!-- 本地解析元数据 -->
                    <v-col cols="12" md="6">
                      <v-card variant="outlined" class="sub-card h-100">
                        <v-card-title class="text-subtitle-2 font-weight-bold pa-3 d-flex align-center ga-2">
                          <v-icon color="primary" size="18">mdi-server</v-icon>
                          本地解析元数据
                        </v-card-title>
                        <v-divider />
                        <v-card-text class="pa-3">
                          <!-- 标题 -->
                          <div class="raw-title-main">{{ rawData.cn_name || rawData.en_name || '未识别标题' }}</div>
                          <div v-if="rawData.cn_name && rawData.en_name" class="raw-title-sub">{{ rawData.en_name }}</div>

                          <v-divider class="my-3" />

                          <!-- 规格网格 -->
                          <div class="raw-specs-list">
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">季 / 集</span>
                              <span class="raw-spec-value text-primary">S{{ rawData.begin_season || 1 }} / E{{ safeVal(rawData.begin_episode, '-') }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">制作组</span>
                              <span class="raw-spec-value text-warning">{{ safeVal(rawData.resource_team) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">介质来源</span>
                              <span class="raw-spec-value">{{ safeVal(rawData.resource_type) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">分辨率</span>
                              <span class="raw-spec-value text-success">{{ safeVal(rawData.resource_pix) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">视频编码</span>
                              <span class="raw-spec-value text-info">{{ safeVal(rawData.video_encode) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">音频编码</span>
                              <span class="raw-spec-value text-info">{{ safeVal(rawData.audio_encode) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">视频特效</span>
                              <span class="raw-spec-value">{{ safeVal(rawData.video_effect) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">字幕语言</span>
                              <span class="raw-spec-value">{{ safeVal(rawData.subtitle_lang) }}</span>
                            </div>
                            <div class="raw-spec-item">
                              <span class="raw-spec-label">发布平台</span>
                              <span class="raw-spec-value text-warning">{{ safeVal(rawData.resource_platform) }}</span>
                            </div>
                            <div v-if="rawData.is_batch" class="raw-spec-item">
                              <span class="raw-spec-label">合集范围</span>
                              <span class="raw-spec-value text-primary">E{{ rawData.begin_episode }}-E{{ rawData.end_episode }}</span>
                            </div>
                          </div>

                          <!-- 标签 -->
                          <div v-if="rawData.tags && rawData.tags.length > 0" class="mt-3">
                            <div class="text-caption text-medium-emphasis mb-1">标签</div>
                            <div class="d-flex flex-wrap ga-1">
                              <v-chip v-for="tag in rawData.tags" :key="tag" size="x-small" variant="outlined" density="compact">
                                {{ tag }}
                              </v-chip>
                            </div>
                          </div>
                        </v-card-text>
                      </v-card>
                    </v-col>

                    <!-- TMDB 原始详情 -->
                    <v-col cols="12" md="6">
                      <v-card v-if="tmdbData" variant="outlined" class="sub-card h-100">
                        <v-card-title class="text-subtitle-2 font-weight-bold pa-3 d-flex align-center ga-2">
                          <v-icon color="warning" size="18">mdi-cloud-outline</v-icon>
                          TMDB 原始详情
                        </v-card-title>
                        <v-divider />
                        <v-card-text class="pa-3">
                          <div class="d-flex ga-3">
                            <!-- 小海报 -->
                            <div class="flex-shrink-0">
                              <v-img
                                v-if="tmdbData.poster_path"
                                :src="store.getImg(String(tmdbData.poster_path))"
                                width="80"
                                rounded="lg"
                                cover
                                aspect-ratio="2/3"
                                class="tmdb-small-poster"
                              />
                              <div v-else class="tmdb-no-poster">N/A</div>
                            </div>
                            <!-- 信息 -->
                            <div class="flex-grow-1" style="min-width: 0">
                              <div class="d-flex align-start justify-space-between ga-2 mb-1">
                                <span class="tmdb-title">{{ tmdbData.title || '无标题' }}</span>
                                <v-chip v-if="tmdbData.category" size="x-small" variant="flat" density="compact" class="meta-tag meta-tag--type">
                                  {{ tmdbData.category }}
                                </v-chip>
                              </div>
                              <div class="tmdb-meta-line">
                                <span>{{ safeVal(tmdbData.release_date, '未知日期') }}</span>
                                <span class="tmdb-id-badge">ID: {{ tmdbData.id }}</span>
                                <span v-if="tmdbData.vote_average">⭐ {{ tmdbData.vote_average }}</span>
                              </div>
                              <div v-if="tmdbData.original_title" class="text-caption text-medium-emphasis mt-1 text-truncate">
                                {{ tmdbData.original_title }}
                              </div>
                            </div>
                          </div>

                          <!-- 简介 -->
                          <div class="tmdb-overview-box mt-3">
                            <div class="tmdb-overview-text">{{ tmdbData.overview || '暂无剧情简介' }}</div>
                          </div>

                          <!-- 流派 -->
                          <div v-if="tmdbData.genres && tmdbData.genres.length > 0" class="mt-3">
                            <div class="text-caption text-medium-emphasis mb-1">流派</div>
                            <div class="d-flex flex-wrap ga-1">
                              <v-chip
                                v-for="genre in tmdbData.genres"
                                :key="genre.id || genre.name"
                                size="x-small"
                                variant="outlined"
                                density="compact"
                              >
                                {{ genre.name }}
                              </v-chip>
                            </div>
                          </div>
                        </v-card-text>
                      </v-card>
                      <v-card v-else variant="outlined" class="sub-card h-100 d-flex align-center justify-center" min-height="120">
                        <div class="text-center pa-4">
                          <v-icon size="32" color="medium-emphasis" class="mb-2">mdi-cloud-off-outline</v-icon>
                          <div class="text-body-2 text-medium-emphasis">未匹配到 TMDB 数据</div>
                        </div>
                      </v-card>
                    </v-col>
                  </v-row>

                  <!-- ========== 规则应用日志 ========== -->
                  <v-card v-if="parsedRuleLogs.length > 0" variant="outlined" class="mb-4">
                    <v-card-title class="text-subtitle-2 font-weight-bold pa-3 d-flex align-center ga-2">
                      <v-icon color="primary" size="18">mdi-scale-balance</v-icon>
                      规则应用日志
                      <v-chip size="x-small" variant="tonal" density="compact" class="ml-auto">{{ parsedRuleLogs.length }} 条</v-chip>
                    </v-card-title>
                    <v-divider />
                    <v-card-text class="pa-3">
                      <div class="rules-list">
                        <div
                          v-for="(item, index) in parsedRuleLogs"
                          :key="index"
                          :class="['rule-log-item', `rule-log-item--${item.type}`]"
                        >
                          <span class="rule-log-icon">{{ item.icon }}</span>
                          <span class="rule-log-content">{{ item.content }}</span>
                        </div>
                      </div>
                    </v-card-text>
                  </v-card>

                </div>

                <!-- 空状态 -->
                <div v-else-if="!store.loading" class="text-center pa-8">
                  <v-icon size="64" color="primary" class="mb-4">mdi-head-cog-outline</v-icon>
                  <div class="text-h6 font-weight-medium">输入文件名开始识别</div>
                  <div class="text-body-2 text-medium-emphasis mt-2">支持番剧文件名、路径、或完整路径的深度解析</div>
                </div>
              </div>
            </v-window-item>

            <!-- ============ 识别审计日志 Tab ============ -->
            <v-window-item value="logs">
              <div class="pa-4 pa-md-6">
                <!-- 日志工具栏 -->
                <div class="d-flex align-center ga-3 mb-4">
                  <v-text-field
                    v-model="logSearchKeyword"
                    placeholder="搜索日志..."
                    prepend-inner-icon="mdi-magnify"
                    variant="outlined"
                    density="compact"
                    hide-details
                    clearable
                    class="flex-grow-1"
                  />
                  <v-chip variant="tonal" color="primary" density="compact">
                    {{ filteredLogs.length }} / {{ store.logs.length }} 行
                  </v-chip>
                  <v-chip
                    :variant="store.loading ? 'flat' : 'tonal'"
                    :color="store.loading ? 'warning' : 'success'"
                    density="compact"
                  >
                    {{ store.loading ? '正在执行...' : '就绪' }}
                  </v-chip>
                </div>

                <!-- 日志容器 -->
                <div v-if="filteredLogs.length > 0" class="audit-log-full">
                  <div
                    v-for="(log, i) in filteredLogs"
                    :key="i"
                    :class="['audit-log-line-full', store.getLogClass(log)]"
                  >
                    <span class="audit-log-idx-full">{{ String(i + 1).padStart(3, '0') }}</span>
                    <span class="audit-log-text-full">{{ log }}</span>
                  </div>
                </div>

                <!-- 空状态 -->
                <div v-else class="text-center pa-8">
                  <v-icon size="48" color="primary" class="mb-3">mdi-text-box-search-outline</v-icon>
                  <div class="text-body-1 font-weight-medium">识别审计日志</div>
                  <div class="text-body-2 text-medium-emphasis mt-1">
                    {{ store.logs.length === 0 ? '执行识别后，审计日志将在此显示' : '未找到匹配的日志' }}
                  </div>
                </div>
              </div>
            </v-window-item>
          </v-window>
        </v-card>
      </v-col>

      <!-- 侧栏: 识别偏好 -->
      <v-col cols="12" lg="3">
        <v-card class="glass-card preference-card">
          <v-card-title class="text-subtitle-1 font-weight-bold pa-4 pb-2">识别偏好</v-card-title>
          <v-card-text class="pa-4 pt-0">
            <div class="pref-list">
              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">动漫识别优化</div>
                  <div class="pref-desc">提升动画匹配精度，过滤同名真人剧</div>
                </div>
                <v-switch v-model="store.animePriority" density="compact" hide-details color="primary" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">本地数据中心</div>
                  <div class="pref-desc">优先碰撞本地数据库，毫秒级离线匹配</div>
                </div>
                <v-switch v-model="store.offlinePriority" density="compact" hide-details color="primary" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 数据源优先</div>
                  <div class="pref-desc">优先尝试 BGM 镜像</div>
                </div>
                <v-switch v-model="store.bangumiPriority" density="compact" hide-details color="primary" />
              </div>

              <div class="pref-item" :style="{ opacity: store.bangumiPriority ? 0.5 : 1 }">
                <div class="pref-info">
                  <div class="pref-label">Bangumi 故障转移</div>
                  <div class="pref-desc">TMDB 失败时自动使用 BGM 补全</div>
                </div>
                <v-switch v-model="store.bangumiFailover" density="compact" hide-details color="primary" :disabled="store.bangumiPriority" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">强制单文件模式</div>
                  <div class="pref-desc">将完整输入作为文件名解析</div>
                </div>
                <v-switch v-model="store.forceFilename" density="compact" hide-details color="primary" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">智能记忆</div>
                  <div class="pref-desc">自动记住系列特征，秒级拦截</div>
                </div>
                <v-switch v-model="store.seriesFingerprint" density="compact" hide-details color="primary" />
              </div>

              <div class="pref-item">
                <div class="pref-info">
                  <div class="pref-label">合集识别增强</div>
                  <div class="pref-desc">支持 01-12 等合集解析</div>
                </div>
                <v-switch v-model="store.batchEnhancement" density="compact" hide-details color="primary" />
              </div>
            </div>
          </v-card-text>
          <v-card-actions class="pa-4 pt-0">
            <div class="text-caption text-medium-emphasis mx-auto">偏好设置会自动保存至本地浏览器</div>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
/* ===== 搜索结果 ===== */
.search-results-box {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  max-height: 300px;
  overflow-y: auto;
}
.search-result-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04);
  transition: background 0.15s;
}
.search-result-item:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

/* ===== 最终识别结论卡片 ===== */
.recog-final-card {
  border: 1px solid rgba(var(--v-theme-primary), 0.2);
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
.recog-filename {
  font-size: 11px;
  opacity: 0.7;
}

/* ===== 子卡片通用 ===== */
.sub-card {
  border-radius: 12px;
}

/* ===== 本地解析元数据 ===== */
.raw-title-main {
  font-weight: bold;
  font-size: 15px;
  color: rgba(var(--v-theme-on-surface), 0.87);
}
.raw-title-sub {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.4);
  font-style: italic;
  font-family: monospace;
  margin-top: 2px;
}
.raw-specs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.raw-spec-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
.raw-spec-label {
  color: rgba(var(--v-theme-on-surface), 0.4);
}
.raw-spec-value {
  font-weight: bold;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

/* ===== TMDB 原始详情 ===== */
.tmdb-small-poster {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.tmdb-no-poster {
  width: 80px;
  height: 120px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.3);
  border-radius: 8px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.1);
}
.tmdb-title {
  font-weight: bold;
  font-size: 15px;
  color: rgb(var(--v-theme-warning));
  line-height: 1.2;
  word-break: break-all;
}
.tmdb-meta-line {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.4);
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.tmdb-id-badge {
  font-family: monospace;
}
.tmdb-overview-box {
  background: rgba(var(--v-theme-on-surface), 0.03);
  padding: 8px;
  border-radius: 6px;
}
.tmdb-overview-text {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-style: italic;
}

/* ===== 规则应用日志 ===== */
.rules-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rule-log-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 8px;
  background: rgba(var(--v-theme-on-surface), 0.02);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.4;
}
.rule-log-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}
.rule-log-content {
  color: rgba(var(--v-theme-on-surface), 0.6);
  word-break: break-all;
}
.rule-log-item--privilege {
  background: rgba(255, 152, 0, 0.08);
  border-left: 2px solid #ff9800;
}
.rule-log-item--community {
  background: rgba(33, 150, 243, 0.08);
  border-left: 2px solid #2196f3;
}
.rule-log-item--builtin {
  background: rgba(76, 175, 80, 0.08);
  border-left: 2px solid #4caf50;
}
.rule-log-item--render {
  background: rgba(156, 39, 176, 0.08);
  border-left: 2px solid #9c27b0;
}
.rule-log-item--memory {
  background: rgba(0, 188, 212, 0.08);
  border-left: 2px solid #00bcd4;
}
.rule-log-item--shield {
  background: rgba(255, 193, 7, 0.06);
  border-left: 2px solid #ffc107;
}
.rule-log-item--batch {
  background: rgba(0, 150, 136, 0.08);
  border-left: 2px solid #009688;
}

/* ===== 深度审计日志 (折叠面板内) ===== */
.audit-log-box {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
}
.audit-log-line {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04);
  padding: 2px 0;
}
.audit-log-idx {
  color: rgba(var(--v-theme-on-surface), 0.3);
  font-size: 10px;
  width: 24px;
  flex-shrink: 0;
  text-align: right;
}
.audit-log-text {
  color: rgba(var(--v-theme-on-surface), 0.6);
  white-space: pre-wrap;
  word-break: break-all;
}

/* ===== 审计日志 Tab (全屏) ===== */
.audit-log-full {
  background: rgba(var(--v-theme-on-surface), 0.02);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  padding: 12px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: calc(100vh - 280px);
  min-height: 400px;
  overflow-y: auto;
}
.audit-log-line-full {
  display: flex;
  gap: 10px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.04);
  padding: 2px 0;
}
.audit-log-idx-full {
  color: rgba(var(--v-theme-on-surface), 0.3);
  font-size: 10px;
  width: 32px;
  flex-shrink: 0;
  text-align: right;
}
.audit-log-text-full {
  color: rgba(var(--v-theme-on-surface), 0.6);
  white-space: pre-wrap;
  word-break: break-all;
}

/* 日志分类着色 */
:deep(.log-header), :deep(.log-p) {
  color: rgb(var(--v-theme-primary));
  font-weight: bold;
}
:deep(.log-debug), :deep(.log-d) {
  color: rgb(var(--v-theme-info));
}
:deep(.log-success), :deep(.log-s) {
  color: rgb(var(--v-theme-success));
}
:deep(.log-warning), :deep(.log-w) {
  color: rgb(var(--v-theme-warning));
}
:deep(.log-result), :deep(.log-i) {
  color: rgb(var(--v-theme-warning));
  font-weight: bold;
}
:deep(.log-normal) {
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* ===== 偏好设置 ===== */
.pref-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pref-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: rgba(var(--v-theme-surface), 0.6);
  border-radius: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  transition: all 0.2s;
}
.pref-item:hover {
  border-color: rgba(var(--v-theme-primary), 0.3);
}
.pref-info {
  flex: 1;
  margin-right: 12px;
}
.pref-label {
  font-size: 14px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.87);
}
.pref-desc {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  line-height: 1.4;
  margin-top: 2px;
}

/* ===== 移动端适配 ===== */
@media (max-width: 600px) {
  .recog-text-label {
    width: 70px;
    font-size: 12px;
  }
  .raw-specs-list {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .pref-desc {
    display: none;
  }
}
</style>
