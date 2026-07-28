<script setup lang="ts">
/**
 * HomeView — 识别调试台
 *
 * 功能:
 * - 文件名识别测试
 * - 高级参数与临时调试
 * - 识别偏好设置
 * - 识别审计日志查看
 */
import { ref, onMounted, watch } from 'vue'
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
            <!-- 识别测试 Tab -->
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

                <!-- 识别结果 -->
                <div v-if="store.data?.final_result" class="recognition-result">
                  <div class="text-subtitle-1 font-weight-bold mb-4">识别结果</div>

                  <!-- 基本信息卡片 -->
                  <v-card variant="tonal" class="mb-4 pa-4">
                    <v-row>
                      <v-col v-if="store.data.final_result.poster_path" cols="12" sm="3" md="2">
                        <v-img
                          :src="store.getImg(store.data.final_result.poster_path)"
                          cover
                          rounded="xl"
                          aspect-ratio="2/3"
                          max-height="200"
                        />
                      </v-col>
                      <v-col cols="12" sm="9" md="10">
                        <div class="text-h6 font-weight-bold">{{ store.data.final_result.title }}</div>
                        <div class="text-body-2 text-medium-emphasis mt-1">{{ store.data.final_result.filename }}</div>

                        <v-chip-group class="mt-3">
                          <v-chip v-if="store.data.final_result.category" size="small" color="primary" variant="tonal">
                            {{ store.data.final_result.category === 'tv' ? '剧集' : '电影' }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.season" size="small" variant="tonal">
                            S{{ String(store.data.final_result.season).padStart(2, '0') }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.episode" size="small" variant="tonal">
                            E{{ store.data.final_result.episode }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.resolution" size="small" variant="tonal">
                            {{ store.data.final_result.resolution }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.team" size="small" variant="tonal" color="accent">
                            {{ store.data.final_result.team }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.year" size="small" variant="tonal">
                            {{ store.data.final_result.year }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.video_encode" size="small" variant="outlined">
                            {{ store.data.final_result.video_encode }}
                          </v-chip>
                          <v-chip v-if="store.data.final_result.audio_encode" size="small" variant="outlined">
                            {{ store.data.final_result.audio_encode }}
                          </v-chip>
                        </v-chip-group>

                        <div v-if="store.data.final_result.tmdb_id" class="mt-3">
                          <v-btn
                            size="small"
                            variant="tonal"
                            color="primary"
                            prepend-icon="mdi-open-in-new"
                            :to="`/tmdb/${store.data.final_result.category || 'tv'}/${store.data.final_result.tmdb_id}`"
                          >
                            查看 TMDB 详情
                          </v-btn>
                        </div>
                      </v-col>
                    </v-row>
                  </v-card>

                  <!-- 识别日志 -->
                  <div v-if="store.logs.length > 1" class="mt-4">
                    <div class="text-subtitle-2 font-weight-medium mb-2">识别日志</div>
                    <div class="recognition-logs pa-3">
                      <div
                        v-for="(log, idx) in store.logs"
                        :key="idx"
                        class="log-line"
                        :class="store.getLogClass(log)"
                      >
                        {{ log }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 空状态 -->
                <div v-else-if="!store.loading" class="text-center pa-8">
                  <v-icon size="64" color="primary" class="mb-4">mdi-head-cog-outline</v-icon>
                  <div class="text-h6 font-weight-medium">输入文件名开始识别</div>
                  <div class="text-body-2 text-medium-emphasis mt-2">支持番剧文件名、路径、或完整路径的深度解析</div>
                </div>
              </div>
            </v-window-item>

            <!-- 识别审计日志 Tab -->
            <v-window-item value="logs">
              <div class="pa-4 pa-md-6">
                <div class="text-center pa-8">
                  <v-icon size="48" color="primary" class="mb-3">mdi-text-box-search-outline</v-icon>
                  <div class="text-body-1 font-weight-medium">识别审计日志</div>
                  <div class="text-body-2 text-medium-emphasis mt-1">此功能正在重写中...</div>
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
