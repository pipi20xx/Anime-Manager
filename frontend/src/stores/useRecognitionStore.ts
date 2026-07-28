/**
 * 识别 Store — 管理识别测试状态、偏好、临时参数
 *
 * 迁移自旧版 recognitionStore.ts (reactive → Pinia defineStore)
 * 逻辑完全保留，仅改写为 Pinia 规范
 */
import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { api } from '@/api/client'
import { useNotification } from '@/composables'
import { getImg as _getImg } from '@/composables/useDataCenter'

export interface FinalResult {
  filename: string
  title: string
  category: string
  year?: string
  season?: number
  episode?: string
  resolution?: string
  video_encode?: string
  audio_encode?: string
  video_effect?: string
  source?: string
  team?: string
  subtitle?: string
  processed_name?: string
  poster_path?: string
  release_date?: string
  tmdb_id?: string | number
  platform?: string
}

export interface RecognizeData {
  success: boolean
  logs: string[]
  final_result: FinalResult
  raw_meta: {
    cn_name?: string
    en_name?: string
    begin_season?: number
    begin_episode?: string
    resource_team?: string
    resource_type?: string
    resource_pix?: string
    video_encode?: string
    audio_encode?: string
    tags?: string[]
  }
  tmdb_match?: any
}

export const useRecognitionStore = defineStore('recognition', () => {
  // --- 识别输入 & 状态 ---
  const filename = ref('')
  const loading = ref(false)
  const logs = ref<string[]>([])
  const data = ref<RecognizeData | null>(null)

  // --- 识别偏好 ---
  const animePriority = ref(true)
  const offlinePriority = ref(true)
  const bangumiPriority = ref(false)
  const bangumiFailover = ref(true)
  const forceFilename = ref(false)
  const seriesFingerprint = ref(true)
  const batchEnhancement = ref(false)

  // --- 高级参数（沙盒调试） ---
  const forcedTmdbId = ref('')
  const forcedType = ref<string | null>(null)
  const forcedSeason = ref('')
  const forcedEpisode = ref('')
  const tempNoise = ref('')
  const tempGroups = ref('')
  const tempRender = ref('')
  const tempPrivilege = ref('')

  // --- TMDB 搜索辅助 ---
  const sandboxKeyword = ref('')
  const sandboxLoading = ref(false)
  const sandboxResults = ref<any[]>([])

  // --- 方法 ---
  function loadPreferences() {
    const getters: [string, (v: string) => any][] = [
      ['anime_priority', (v) => (animePriority.value = v === 'true')],
      ['offline_priority', (v) => (offlinePriority.value = v === 'true')],
      ['bangumi_priority', (v) => (bangumiPriority.value = v === 'true')],
      ['bangumi_failover', (v) => (bangumiFailover.value = v === 'true')],
      ['force_filename', (v) => (forceFilename.value = v === 'true')],
      ['series_fingerprint', (v) => (seriesFingerprint.value = v === 'true')],
      ['batch_enhancement', (v) => (batchEnhancement.value = v === 'true')],
    ]
    for (const [key, setter] of getters) {
      const saved = localStorage.getItem(key)
      if (saved !== null) setter(saved)
    }
  }

  function savePreferences() {
    localStorage.setItem('anime_priority', String(animePriority.value))
    localStorage.setItem('offline_priority', String(offlinePriority.value))
    localStorage.setItem('bangumi_priority', String(bangumiPriority.value))
    localStorage.setItem('bangumi_failover', String(bangumiFailover.value))
    localStorage.setItem('force_filename', String(forceFilename.value))
    localStorage.setItem('series_fingerprint', String(seriesFingerprint.value))
    localStorage.setItem('batch_enhancement', String(batchEnhancement.value))
  }

  async function performRecognition() {
    if (!filename.value || loading.value) return

    const { success, error: showError } = useNotification()
    loading.value = true
    logs.value = ['[SYSTEM] 任务初始化...']
    data.value = null

    try {
      const payload = {
        filename: filename.value,
        anime_priority: animePriority.value,
        offline_priority: offlinePriority.value,
        bangumi_priority: bangumiPriority.value,
        bangumi_failover: bangumiFailover.value,
        force_filename: forceFilename.value,
        series_fingerprint: seriesFingerprint.value,
        batch_enhancement: batchEnhancement.value,
        forced_tmdb_id: forcedTmdbId.value || undefined,
        forced_type: forcedType.value || undefined,
        forced_season: forcedSeason.value || undefined,
        forced_episode: forcedEpisode.value || undefined,
        temp_noise: (tempNoise.value || '').split('\n').map((s: string) => s.trim()).filter((s: string) => s),
        temp_groups: (tempGroups.value || '').split('\n').map((s: string) => s.trim()).filter((s: string) => s),
        temp_render: (tempRender.value || '').split('\n').map((s: string) => s.trim()).filter((s: string) => s),
        temp_privilege: (tempPrivilege.value || '').split('\n').map((s: string) => s.trim()).filter((s: string) => s),
      }

      const resData = await api.post<RecognizeData>('/api/recognize', payload)

      if (resData.success) {
        data.value = resData
        const newLogs = Array.isArray(resData.logs) ? resData.logs : []
        logs.value = [...logs.value, ...newLogs]
        success('解析完成')
      } else {
        logs.value.push('[ERROR] 解析异常')
        showError('解析异常')
      }
    } catch (e: any) {
      logs.value.push(`[ERROR] 服务异常: ${e.message}`)
      showError('连接失败')
    } finally {
      loading.value = false
    }
  }

  async function searchTmdbForSandbox() {
    if (!sandboxKeyword.value) return
    sandboxLoading.value = true
    try {
      const typeParam = forcedType.value || 'multi'
      const resData = await api.get<any>('/api/tmdb/search', {
        params: { query: sandboxKeyword.value, type: typeParam },
      })
      sandboxResults.value = resData.results || []
    } catch (e) {
      console.error('TMDB 搜索失败', e)
    } finally {
      sandboxLoading.value = false
    }
  }

  function selectSandboxResult(res: any) {
    forcedTmdbId.value = String(res.id)
    forcedType.value = res.media_type || forcedType.value
    sandboxResults.value = []
  }

  // 使用统一的 getImg 函数（自动附加 token 和处理代理路径）
  const getImg = _getImg

  function getLogClass(log: string): string {
    const logStr = String(log || '')
    if (logStr.includes('深度审计启动') || logStr.includes('🏁')) return 'log-header'
    if (logStr.includes('[DEBUG][STEP')) return 'log-debug'
    if (logStr.includes('🎯') || logStr.includes('成功') || logStr.includes('✅')) return 'log-success'
    if (logStr.includes('✂️') || logStr.includes('拦截') || logStr.includes('⚠️')) return 'log-warning'
    if (logStr.includes('[最终结论汇报]') || logStr.includes('结论')) return 'log-result'
    return 'log-normal'
  }

  return {
    filename,
    loading,
    logs,
    data,
    animePriority,
    offlinePriority,
    bangumiPriority,
    bangumiFailover,
    forceFilename,
    seriesFingerprint,
    batchEnhancement,
    forcedTmdbId,
    forcedType,
    forcedSeason,
    forcedEpisode,
    tempNoise,
    tempGroups,
    tempRender,
    tempPrivilege,
    sandboxKeyword,
    sandboxLoading,
    sandboxResults,
    loadPreferences,
    savePreferences,
    performRecognition,
    searchTmdbForSandbox,
    selectSandboxResult,
    getImg,
    getLogClass,
  }
})
