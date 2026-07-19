import { ref, onMounted, computed } from 'vue'
import { useMessage } from 'naive-ui'

export type TableCategory = 'cache' | 'config' | 'core'

export interface DbTable {
  name: string
  count: number
  size_bytes?: number
}

export function useMaintenance() {
  const message = useMessage()
  const loading = ref(false)
  const tables = ref<DbTable[]>([])
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
    'public.series_fingerprint': '智能记忆（用于加速识别和去重）',
    'public.filter_rules': 'RSS 包含/排除等过滤规则',
    'public.rules': '识别引擎正则与自定义规则',
    'public.secondary_rules': '自动分类与分库逻辑配置',
    'public.download_history': '下载器的任务执行历史',
    'public.blacklist': '识别排除黑名单关键词',
    'public.tmdb_blocklist': 'TMDB 主动屏蔽列表（命中后跳过下载/追剧订阅）',
    'public.subscription_templates': '订阅预设模板',
    'public.discover_cache': '系统发现页（趋势/热门/搜索）的临时数据缓存',
    'public.remote_rules': '从远程 URL 同步下来的社区识别与清理规则',
    'public.calendar_subjects': '番剧放送时刻表数据',
    'public.quality_profiles': '下载质量优先偏好设置',
    'public.strm_tasks': '虚拟链接 (STRM) 生成任务记录',
    'public.health_check_configs': '系统健康检查监控配置',
    'public.users': '系统用户账户与认证信息',
    'public.sessions': '用户登录会话与设备管理',
    'public.task_records': '任务中心执行记录（整理/STRM/RSS等任务的日志）',
    'public.file_hashes': '文件哈希记录（SHA1、ED2K 及识别信息缓存）',
    'public.rss_detect_tasks': 'RSS探测订阅任务（自动发现并订阅新番）',
    'public.bangumi_data_item': 'Bangumi 数据条目（Bangumi ID 到 TMDB/MAL/AniList/AniDB 的映射，含完整原始数据）',
    'public.bangumi_raw_cache': 'Bangumi 原始 API 响应缓存（完结番剧的 Subject/Episodes/Characters 原始响应，永久缓存）',
    'public.emby_media_index': 'Emby 库索引（TMDB ID + 类型 + Emby 标题的快速查找表）'
  }

  /**
   * 表的语义分类：
   * - cache: 缓存类，可放心清空（清了会自动重建/重新拉取）
   * - config: 用户配置类，清空后需要重新配置
   * - core: 核心数据类，清空后不可逆，需格外谨慎
   */
  const tableCategories: Record<string, TableCategory> = {
    // ===== 缓存类（可放心清空） =====
    'metadata.media_title_index': 'cache',
    'metadata.bgm_archive': 'cache',
    'metadata.ref_genres': 'cache',
    'metadata.ref_companies': 'cache',
    'metadata.ref_keywords': 'cache',
    'public.discover_cache': 'cache',
    'public.calendar_subjects': 'cache',
    'public.emby_media_index': 'cache',
    'public.system_logs': 'cache',
    'public.feed_items': 'cache',
    'public.download_history': 'cache',
    'public.task_records': 'cache',
    'public.organize_history': 'cache',
    'public.bangumi_data_item': 'cache',
    'public.subscribed_episodes': 'cache',

    // ===== 配置类（清空需重新配置） =====
    'metadata.recognition_corrections': 'config',
    'metadata.user_genre_mapping': 'config',
    'metadata.user_company_mapping': 'config',
    'metadata.user_keyword_mapping': 'config',
    'metadata.user_language_mapping': 'config',
    'metadata.user_country_mapping': 'config',
    'public.feeds': 'config',
    'public.filter_rules': 'config',
    'public.rules': 'config',
    'public.secondary_rules': 'config',
    'public.quality_profiles': 'config',
    'public.subscription_templates': 'config',
    'public.blacklist': 'config',
    'public.tmdb_blocklist': 'config',
    'public.remote_rules': 'config',
    'public.health_check_configs': 'config',
    'public.rss_detect_tasks': 'config',
    'public.strm_tasks': 'config',
    'public.subscriptions': 'config',

    // ===== 核心数据类（不可逆，危险） =====
    'metadata.tmdb_deep_meta': 'core',
    'public.bangumi_raw_cache': 'core',
    'public.series_fingerprint': 'core',
    'public.file_hashes': 'core',
    'public.users': 'core',
    'public.sessions': 'core'
  }

  /** 分类元信息：标签、颜色、文案 */
  const categoryMeta: Record<TableCategory, { label: string; color: string; bg: string; desc: string }> = {
    cache: {
      label: '缓存',
      color: '#2e7d32',
      bg: 'rgba(46, 125, 50, 0.12)',
      desc: '可放心清空，清空后会自动重建或重新拉取'
    },
    config: {
      label: '配置',
      color: '#f57c00',
      bg: 'rgba(245, 124, 0, 0.12)',
      desc: '清空后需要重新配置，请谨慎操作'
    },
    core: {
      label: '核心',
      color: '#c62828',
      bg: 'rgba(198, 40, 40, 0.12)',
      desc: '核心数据，清空后不可恢复，极度危险'
    }
  }

  /** 获取表的分类，默认为 core（未知表按危险处理） */
  const getCategory = (tableName: string): TableCategory => {
    return tableCategories[tableName] || 'core'
  }

  /** 格式化磁盘占用大小 */
  const formatSize = (bytes: number | undefined): string => {
    if (!bytes || bytes <= 0) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
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

  /** 按语义分类分组（缓存 → 配置 → 核心），同组内按空间降序 */
  const groupedTables = computed(() => {
    const groups: Record<string, DbTable[]> = {
      '缓存（可清空）': [],
      '配置（需谨慎）': [],
      '核心数据（危险）': []
    }
    const groupKey: Record<TableCategory, string> = {
      cache: '缓存（可清空）',
      config: '配置（需谨慎）',
      core: '核心数据（危险）'
    }
    tables.value.forEach(t => {
      const cat = getCategory(t.name)
      groups[groupKey[cat]].push(t)
    })
    // 每组内按空间降序
    Object.values(groups).forEach(g => g.sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0)))
    return groups
  })

  /** 分组顺序 */
  const groupOrder = ['缓存（可清空）', '配置（需谨慎）', '核心数据（危险）']

  onMounted(fetchTables)

  return {
    loading,
    maintenanceLoading,
    groupedTables,
    groupOrder,
    tableDescriptions,
    categoryMeta,
    getCategory,
    formatSize,
    fetchTables,
    handleTruncate
  }
}
