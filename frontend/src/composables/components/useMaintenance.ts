import { ref, onMounted, computed } from 'vue'
import { useMessage } from 'naive-ui'

export function useMaintenance() {
  const message = useMessage()
  const loading = ref(false)
  const tables = ref<{name: string, count: number}[]>([])
  const maintenanceLoading = ref<Record<string, boolean>>({})
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const tableDescriptions: Record<string, string> = {
    'metadata.tmdb_deep_meta': 'TMDB 深度元数据（海报、剧情、演员等）',
    'metadata.media_title_index': '媒体标题加速索引（用于快速匹配 ID）',
    'metadata.ref_genres': '番剧类型字典',
    'metadata.ref_companies': '动画制作/发行公司资料',
    'metadata.ref_keywords': '番剧特征关键词库',
    'metadata.bgm_archive': 'Bangumi 归档数据',
    'metadata.recognition_corrections': '用户手动指定的识别修正映射',
    'metadata.user_genre_mapping': '用户自定义流派 ID 中文映射',
    'metadata.user_company_mapping': '用户自定义公司 ID 中文映射',
    'metadata.user_keyword_mapping': '用户自定义关键词 ID 中文映射',
    'metadata.user_language_mapping': '用户自定义语言代码中文映射',
    'metadata.user_country_mapping': '用户自定义国家代码中文映射',
    'public.system_logs': '系统操作审计日志',
    'public.feeds': 'RSS 订阅源地址与连接配置',
    'public.feed_items': 'RSS 抓取到的下载条目记录',
    'public.subscriptions': '番剧追剧任务配置',
    'public.subscribed_episodes': '已执行下载的剧集记录（防重）',
    'public.organize_history': '文件整理重命名的历史记录',
    'public.series_fingerprint': '剧集指纹数据（用于智能识别和去重）',
    'public.filter_rules': 'RSS 包含/排除等过滤规则',
    'public.rules': '识别引擎正则与自定义规则',
    'public.secondary_rules': '自动分类与分库逻辑配置',
    'public.download_history': '下载器的任务执行历史',
    'public.blacklist': '识别排除黑名单关键词',
    'public.subscription_templates': '订阅预设模板',
    'public.discover_cache': '系统发现页（趋势/热门/搜索）的临时数据缓存',
    'public.remote_rules': '从远程 URL 同步下来的社区识别与清理规则',
    'public.calendar_subjects': '番剧放送时刻表数据',
    'public.quality_profiles': '下载质量优先偏好设置',
    'public.strm_tasks': '虚拟链接 (STRM) 生成任务记录',
    'public.health_check_configs': '系统健康检查监控配置',
    'public.users': '系统用户账户与认证信息',
    'public.task_records': '任务中心执行记录（整理/STRM/RSS等任务的日志）'
  }

  const fetchTables = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/system/db/tables`)
      const data = await res.json()
      if (data.status === 'success') {
        tables.value = data.tables
      }
    } catch (e) {
      message.error('获取表列表失败')
    } finally {
      loading.value = false
    }
  }

  const handleTruncate = async (tableName: string) => {
    maintenanceLoading.value[tableName] = true
    try {
      const res = await fetch(`${API_BASE}/api/system/db/truncate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table: tableName })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success(data.message || '清理成功')
        await fetchTables()
      } else {
        message.error('清理失败: ' + data.message)
      }
    } catch (e) {
      message.error('请求失败')
    } finally {
      maintenanceLoading.value[tableName] = false
    }
  }

  const groupedTables = computed(() => {
    const groups: Record<string, typeof tables.value> = {
      'metadata': [],
      'public': []
    }
    tables.value.forEach(t => {
      const prefix = t.name.split('.')[0]
      if (groups[prefix]) groups[prefix].push(t)
      else groups['public'].push(t)
    })
    return groups
  })

  onMounted(fetchTables)

  return {
    loading,
    maintenanceLoading,
    groupedTables,
    tableDescriptions,
    fetchTables,
    handleTruncate
  }
}
