import { reactive, ref } from 'vue'

interface FinalResult {
  filename: string; title: string; category: string; year?: string;
  season?: number; episode?: string; resolution?: string; video_encode?: string;
  audio_encode?: string; video_effect?: string; source?: string; team?: string;
  subtitle?: string; processed_name?: string; poster_path?: string;
  release_date?: string; tmdb_id?: string | number; platform?: string;
}

interface RecognizeData {
  success: boolean; logs: string[]; final_result: FinalResult;
  raw_meta: { cn_name?: string; en_name?: string; begin_season?: number; begin_episode?: string; resource_team?: string; resource_type?: string; resource_pix?: string; video_encode?: string; audio_encode?: string; tags?: string[]; };
  tmdb_match?: any;
}

// Global State
export const recognitionState = reactive({
  filename: '',
  loading: false,
  logs: [] as string[],
  data: null as RecognizeData | null,
  
  // Settings
  animePriority: true,
  offlinePriority: true,
  bangumiPriority: false,
  bangumiFailover: true,
  forceFilename: false,
  seriesFingerprint: true,
  batchEnhancement: false,

  // Debug Sandbox
  forced_tmdb_id: '',
  forced_type: null as string | null,
  forced_season: '',
  forced_episode: '',
  temp_noise: '',
  temp_groups: '',
  temp_render: ''
})

export const getLogClass = (log: any) => {
  const logStr = String(log || '')
  if (logStr.includes("深度审计启动") || logStr.includes("🏁")) return "log-header"
  if (logStr.includes("[DEBUG][STEP")) return "log-debug"
  if (logStr.includes("🎯") || logStr.includes("成功") || logStr.includes("✅")) return "log-success"
  if (logStr.includes("✂️") || logStr.includes("拦截") || logStr.includes("⚠️")) return "log-warning"
  if (logStr.includes("[最终结论汇报]") || logStr.includes("结论")) return "log-result"
  return "log-normal"
}

export const performRecognition = async (apiBase: string, message: any) => {
  if (!recognitionState.filename || recognitionState.loading) return
  
  recognitionState.loading = true
  recognitionState.logs = ["[SYSTEM] 任务初始化..."]
  recognitionState.data = null

  try {
    const payload = { 
      filename: recognitionState.filename, 
      anime_priority: recognitionState.animePriority, 
      offline_priority: recognitionState.offlinePriority,
      bangumi_priority: recognitionState.bangumiPriority,
      bangumi_failover: recognitionState.bangumiFailover,
      force_filename: recognitionState.forceFilename,
      series_fingerprint: recognitionState.seriesFingerprint,
      batch_enhancement: recognitionState.batchEnhancement,
      forced_tmdb_id: recognitionState.forced_tmdb_id || undefined, 
      forced_type: recognitionState.forced_type || undefined,
      forced_season: recognitionState.forced_season || undefined, 
      forced_episode: recognitionState.forced_episode || undefined,
      temp_noise: (recognitionState.temp_noise || '').split('\n').map(s => s.trim()).filter(s => s),
      temp_groups: (recognitionState.temp_groups || '').split('\n').map(s => s.trim()).filter(s => s),
      temp_render: (recognitionState.temp_render || '').split('\n').map(s => s.trim()).filter(s => s)
    } 
    
    const res = await fetch(`${apiBase}/api/recognize`, { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify(payload) 
    }) 
    
    const resData = await res.json()
    
    if (resData.success) {
      recognitionState.data = resData
      // Safe append
      const newLogs = Array.isArray(resData.logs) ? resData.logs : []
      recognitionState.logs = [...recognitionState.logs, ...newLogs]
      message.success("解析完成")
    } else { 
      recognitionState.logs.push("[ERROR] 解析异常")
      message.warning("解析异常") 
    } 
  } catch (e: any) { 
    recognitionState.logs.push(`[ERROR] 服务异常: ${e.message}`)
    message.error("连接失败") 
  } finally { 
    recognitionState.loading = false 
  } 
}
