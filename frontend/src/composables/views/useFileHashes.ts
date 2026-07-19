import { ref, reactive, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'

/** 文件哈希记录字段（与后端 FileHashResponse 对应） */
export interface FileHashRecord {
  id: number
  sha1: string
  ed2k: string
  ed2k_link: string
  original_filename: string
  file_size: number | null
  tmdb_id: string | null
  title: string | null
  season: number | null
  episode: string | null
  media_type: string | null
  resolution: string | null
  team: string | null
  video_encode: string | null
  audio_encode: string | null
  video_effect: string | null
  source: string | null
  subtitle: string | null
  platform: string | null
  year: string | null
  secondary_category: string | null
  origin_country: string | null
  release_date: string | null
  source_path: string
  target_path: string | null
  calculated_at: string
}

/** 可排序字段白名单（与后端 FileHash 模型字段对应） */
const SORTABLE_FIELDS: Record<string, string> = {
  id: 'id',
  sha1: 'sha1',
  ed2k: 'ed2k',
  original_filename: 'original_filename',
  file_size: 'file_size',
  tmdb_id: 'tmdb_id',
  title: 'title',
  season: 'season',
  media_type: 'media_type',
  resolution: 'resolution',
  source_path: 'source_path',
  calculated_at: 'calculated_at',
}

export function useFileHashes() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const loading = ref(false)
  const data = ref<FileHashRecord[]>([])

  // 筛选条件
  const filters = reactive({
    q: '',
    tmdb_id: '',
    media_type: null as string | null,
    season: null as number | null,
    team: '',
  })

  // 排序
  const sort = reactive({
    sortBy: 'calculated_at',
    sortOrder: 'desc' as 'asc' | 'desc',
  })

  // 分页（后端使用 offset/limit，前端 NDataTable 使用 page/pageSize）
  const pagination = reactive({
    page: 1,
    pageSize: 50,
    showSizePicker: true,
    pageSizes: [20, 50, 100, 200, 500],
    itemCount: 0,
    prefix({ itemCount }: any) {
      return `共 ${itemCount} 条`
    },
  })

  // 详情弹框
  const showDetail = ref(false)
  const selectedRecord = ref<FileHashRecord | null>(null)

  /** 拉取列表数据 */
  const fetchData = async () => {
    loading.value = true
    try {
      const params = new URLSearchParams({
        limit: pagination.pageSize.toString(),
        offset: ((pagination.page - 1) * pagination.pageSize).toString(),
        sort_by: sort.sortBy,
        sort_order: sort.sortOrder,
      })
      if (filters.q) params.append('q', filters.q)
      if (filters.tmdb_id) params.append('tmdb_id', filters.tmdb_id)
      if (filters.media_type) params.append('media_type', filters.media_type)
      if (filters.season !== null && filters.season !== undefined && !Number.isNaN(filters.season)) {
        params.append('season', String(filters.season))
      }
      if (filters.team) params.append('team', filters.team)

      const res = await fetch(`${API_BASE}/api/file_hashes?${params.toString()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      data.value = json.data || []
      pagination.itemCount = json.total || 0
    } catch (e) {
      message.error('加载文件哈希记录失败')
      data.value = []
      pagination.itemCount = 0
    } finally {
      loading.value = false
    }
  }

  /** 重置筛选并回到第一页 */
  const resetFilters = () => {
    filters.q = ''
    filters.tmdb_id = ''
    filters.media_type = null
    filters.season = null
    filters.team = ''
    sort.sortBy = 'calculated_at'
    sort.sortOrder = 'desc'
    pagination.page = 1
    fetchData()
  }

  /** 处理表格排序变化 */
  const handleSorterChange = (sorter: any) => {
    if (sorter && sorter.columnKey && SORTABLE_FIELDS[sorter.columnKey]) {
      sort.sortBy = SORTABLE_FIELDS[sorter.columnKey]
      sort.sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc'
    } else {
      sort.sortBy = 'calculated_at'
      sort.sortOrder = 'desc'
    }
    fetchData()
  }

  /** 打开详情弹框 */
  const openDetail = (row: FileHashRecord) => {
    selectedRecord.value = row
    showDetail.value = true
  }

  /** 兼容性复制到剪贴板 */
  const fallbackCopy = (text: string) => {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.top = '-9999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    try {
      const successful = document.execCommand('copy')
      if (successful) {
        message.success('已复制到剪贴板 (兼容模式)')
      } else {
        message.error('浏览器不支持自动复制')
      }
    } catch (e) {
      message.error('复制失败')
    }
    document.body.removeChild(textArea)
  }

  const copyToClipboard = (text: string) => {
    if (!text) {
      message.warning('内容为空，无法复制')
      return
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        message.success('已复制到剪贴板')
      }).catch(() => {
        fallbackCopy(text)
      })
    } else {
      fallbackCopy(text)
    }
  }

  /** 格式化文件大小 */
  const formatFileSize = (bytes: number | null): string => {
    if (bytes === null || bytes === undefined) return '-'
    if (bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    const size = bytes / Math.pow(1024, i)
    return `${size.toFixed(i === 0 ? 0 : 2)} ${units[i]}`
  }

  /** 格式化时间 */
  const formatTime = (timeStr: string): string => {
    if (!timeStr) return '-'
    return timeStr.replace('T', ' ').split('.')[0]
  }

  /** 哈希截断显示 */
  const truncateHash = (hash: string | null, head = 8, tail = 6): string => {
    if (!hash) return '-'
    if (hash.length <= head + tail + 3) return hash
    return `${hash.slice(0, head)}…${hash.slice(-tail)}`
  }

  // ========== ED2K 链接模板渲染 ==========
  // ED2K 链接格式: ed2k://|file|文件名|文件大小|哈希|/
  // 文件名段（第2段）可以根据识别信息组合生成，好比重命名

  /** 默认 ED2K 命名模板（区分剧集 / 电影） */
  const defaultEd2kTemplates = {
    tv: '{original_filename}.{ext}',
    movie: '{original_filename}.{ext}',
  }

  /** 预设方案：点击即可填充到输入框 */
  const ed2kTemplatePresets = {
    /** 剧集预设（含季集） */
    tv: [
      { label: '原始文件名', desc: '保持原文件名', template: '{original_filename}.{ext}' },
      { label: '标题+季集+制作组', desc: '标题年份+季集+制作组', template: '{title} ({year}) - S{season_02}E{episode_02} - {team}' },
      { label: '标题+季集', desc: '标题年份+季集', template: '{title} ({year}) - S{season_02}E{episode_02}' },
    ],
    /** 电影预设（无季集） */
    movie: [
      { label: '原始文件名', desc: '保持原文件名', template: '{original_filename}.{ext}' },
      { label: '标题+年份+制作组', desc: '标题年份+制作组', template: '{title} ({year}) - {team}' },
      { label: '标题+年份', desc: '标题年份', template: '{title} ({year})' },
    ],
  }

  /** localStorage 存储 key（剧集 / 电影分别存储） */
  const ED2K_TEMPLATE_KEY_TV = 'file_hashes_ed2k_template_tv'
  const ED2K_TEMPLATE_KEY_MOVIE = 'file_hashes_ed2k_template_movie'

  /** 模板设置弹框 */
  const showTemplateSettings = ref(false)

  /** 当前模板（从 localStorage 读取，没有则用默认值） */
  const ed2kTemplates = ref({
    tv: localStorage.getItem(ED2K_TEMPLATE_KEY_TV) || defaultEd2kTemplates.tv,
    movie: localStorage.getItem(ED2K_TEMPLATE_KEY_MOVIE) || defaultEd2kTemplates.movie,
  })

  /** 持久化模板到 localStorage */
  const saveEd2kTemplates = (val: { tv: string; movie: string }) => {
    ed2kTemplates.value = { ...val }
    localStorage.setItem(ED2K_TEMPLATE_KEY_TV, val.tv)
    localStorage.setItem(ED2K_TEMPLATE_KEY_MOVIE, val.movie)
    message.success('ED2K 命名模板已保存到浏览器记忆')
  }

  /** 判断记录是否为电影类型 */
  const isMovieRecord = (record: FileHashRecord): boolean => {
    const raw = (record.media_type || '').toLowerCase()
    return raw === 'movie' || raw === '电影'
  }

  /** 根据记录的媒体类型选择对应模板 */
  const getTemplateForRecord = (record: FileHashRecord): string => {
    return isMovieRecord(record) ? ed2kTemplates.value.movie : ed2kTemplates.value.tv
  }

  /** 从文件名提取后缀名（不含点），如 "xxx.mkv" → "mkv" */
  const extractExt = (filename: string): string => {
    const idx = filename.lastIndexOf('.')
    if (idx < 0 || idx === filename.length - 1) return ''
    return filename.slice(idx + 1)
  }

  /**
   * 根据识别信息和模板渲染出新的文件名（不含后缀）
   * 变量体系与项目重命名规则一致
   */
  const renderEd2kFilename = (record: FileHashRecord, template: string): string => {
    // 季号补零
    const season02 = (record.season !== null && record.season !== undefined)
      ? String(record.season).padStart(2, '0')
      : ''
    // 集号补零
    const episode02 = (() => {
      const ep = record.episode
      if (!ep) return ''
      // 如果是范围型 (如 "01-12") 不补零
      if (String(ep).includes('-')) return String(ep)
      const n = Number(ep)
      return Number.isNaN(n) ? String(ep) : String(n).padStart(2, '0')
    })()

    const ext = extractExt(record.original_filename)

    // 构建变量映射表
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
      '{original_filename}': record.original_filename.replace(/\.[^.]+$/, ''),
      '{name}': record.original_filename.replace(/\.[^.]+$/, ''),
    }

    let result = template
    for (const [key, val] of Object.entries(vars)) {
      result = result.replaceAll(key, val)
    }

    // 清洗：去掉空的 () [] 和多余空格
    result = result.replace(/\(\s*\)/g, '').replace(/\[\s*\]/g, '')
    result = result.replace(/\s{2,}/g, ' ').trim()
    // 清理首尾的连字符/空格
    result = result.replace(/^[-\s]+|[-\s]+$/g, '')

    // 如果模板中没有 {ext}，自动补后缀
    if (!template.includes('{ext}') && ext) {
      result = `${result}.${ext}`
    }

    return result || record.original_filename
  }

  /**
   * 解析 ED2K 链接并替换文件名段
   * 格式: ed2k://|file|文件名|文件大小|哈希|/
   */
  const rebuildEd2kLink = (ed2kLink: string, newFilename: string): string => {
    if (!ed2kLink) return ed2kLink
    const parts = ed2kLink.split('|')
    // 标准格式至少 6 段: ed2k://, file, 文件名, 大小, 哈希, /
    if (parts.length >= 5 && parts[0] === 'ed2k://' && parts[1] === 'file') {
      parts[2] = newFilename
      return parts.join('|')
    }
    return ed2kLink
  }

  /** 根据记录类型自动选择模板渲染出完整的新 ED2K 链接 */
  const renderEd2kLink = (record: FileHashRecord): string => {
    if (!record.ed2k_link) return ''
    const newFilename = renderEd2kFilename(record, getTemplateForRecord(record))
    return rebuildEd2kLink(record.ed2k_link, newFilename)
  }

  /** 按模板渲染并复制 ED2K 链接 */
  const copyEd2kWithTemplate = (record: FileHashRecord) => {
    const link = renderEd2kLink(record)
    if (!link) {
      message.warning('该记录没有 ED2K 链接')
      return
    }
    copyToClipboard(link)
  }

  /** ED2K 模板可用变量手册 */
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

  // ========== 批量导出 / 复制全部 ==========
  // 后端 limit 上限 500，需循环分页拉取当前筛选条件下的全部数据

  /** 导出进行中状态（用于按钮 loading） */
  const exporting = ref(false)

  /** 构建当前筛选条件的 URLSearchParams（复用 fetchData 的筛选逻辑） */
  const buildFilterParams = (limit: number, offset: number) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      sort_by: sort.sortBy,
      sort_order: sort.sortOrder,
    })
    if (filters.q) params.append('q', filters.q)
    if (filters.tmdb_id) params.append('tmdb_id', filters.tmdb_id)
    if (filters.media_type) params.append('media_type', filters.media_type)
    if (filters.season !== null && filters.season !== undefined && !Number.isNaN(filters.season)) {
      params.append('season', String(filters.season))
    }
    if (filters.team) params.append('team', filters.team)
    return params
  }

  /**
   * 循环分页拉取当前筛选条件下的全部记录
   * 每页 500 条，直到拉完或达到上限
   */
  const fetchAllFiltered = async (): Promise<FileHashRecord[]> => {
    const PAGE = 500
    const all: FileHashRecord[] = []
    let offset = 0
    // 安全上限：最多拉 10 万条，避免极端情况死循环
    const MAX = 100000
    while (offset < MAX) {
      const params = buildFilterParams(PAGE, offset)
      const res = await fetch(`${API_BASE}/api/file_hashes?${params.toString()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      const batch: FileHashRecord[] = json.data || []
      all.push(...batch)
      const total: number = json.total || 0
      offset += batch.length
      // 拉完或本页不足一页，结束
      if (batch.length < PAGE || all.length >= total) break
    }
    return all
  }

  /** 生成时间戳文件名 */
  const timestamp = (): string => {
    const d = new Date()
    const p = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
  }

  /** 下载文本为文件 */
  const downloadText = (content: string, filename: string) => {
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

  /** 生成筛选条件描述（用于导出文件头） */
  const filterDescription = (): string => {
    const parts: string[] = []
    if (filters.q) parts.push(`关键词="${filters.q}"`)
    if (filters.tmdb_id) parts.push(`TMDB ID=${filters.tmdb_id}`)
    if (filters.media_type) parts.push(`类型=${filters.media_type}`)
    if (filters.season !== null && filters.season !== undefined) parts.push(`季号=${filters.season}`)
    if (filters.team) parts.push(`制作组=${filters.team}`)
    return parts.length ? parts.join(', ') : '无（全部记录）'
  }

  /**
   * 导出全部 ED2K 链接为 txt（每行一条，按模板渲染）
   */
  const exportEd2kLinks = async () => {
    if (pagination.itemCount === 0) {
      message.warning('当前没有可导出的数据')
      return
    }
    exporting.value = true
    try {
      const all = await fetchAllFiltered()
      const lines = all.map(r => renderEd2kLink(r)).filter(Boolean)
      const header = `# 文件哈希 ED2K 链接导出\n# 导出时间: ${new Date().toLocaleString()}\n# 筛选条件: ${filterDescription()}\n# 共 ${lines.length} 条 (剧集模板: ${ed2kTemplates.value.tv} | 电影模板: ${ed2kTemplates.value.movie})\n\n`
      const content = header + lines.join('\n') + '\n'
      downloadText(content, `ed2k_links_${timestamp()}.txt`)
      message.success(`已导出 ${lines.length} 条 ED2K 链接`)
    } catch (e) {
      message.error('导出失败，请重试')
    } finally {
      exporting.value = false
    }
  }

  /**
   * 复制全部 ED2K 链接到剪贴板（按模板渲染，每行一条）
   */
  const copyAllEd2kLinks = async () => {
    if (pagination.itemCount === 0) {
      message.warning('当前没有可复制的数据')
      return
    }
    exporting.value = true
    try {
      const all = await fetchAllFiltered()
      const lines = all.map(r => renderEd2kLink(r)).filter(Boolean)
      if (lines.length === 0) {
        message.warning('没有有效的 ED2K 链接')
        return
      }
      const text = lines.join('\n')
      copyToClipboard(text)
      message.success(`已复制 ${lines.length} 条 ED2K 链接`)
    } catch (e) {
      message.error('复制失败，请尝试导出 txt')
    } finally {
      exporting.value = false
    }
  }

  /**
   * 导出完整信息为 txt（带标题、季集、文件名、大小、ED2K 等）
   */
  const exportFullInfo = async () => {
    if (pagination.itemCount === 0) {
      message.warning('当前没有可导出的数据')
      return
    }
    exporting.value = true
    try {
      const all = await fetchAllFiltered()
      const header = `# 文件哈希记录完整导出\n# 导出时间: ${new Date().toLocaleString()}\n# 筛选条件: ${filterDescription()}\n# 共 ${all.length} 条\n\n`
      const body = all.map((r, i) => {
        const se = (r.season !== null && r.season !== undefined)
          ? `S${String(r.season).padStart(2, '0')}`
          : ''
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
      const content = header + body
      downloadText(content, `file_hashes_${timestamp()}.txt`)
      message.success(`已导出 ${all.length} 条完整记录`)
    } catch (e) {
      message.error('导出失败，请重试')
    } finally {
      exporting.value = false
    }
  }

  // 筛选条件变化 → 回到第一页并重新拉取
  watch(
    () => [filters.media_type, filters.season, filters.tmdb_id, filters.team],
    () => {
      pagination.page = 1
      fetchData()
    }
  )

  onMounted(fetchData)

  return {
    loading,
    data,
    filters,
    sort,
    pagination,
    showDetail,
    selectedRecord,
    fetchData,
    resetFilters,
    handleSorterChange,
    openDetail,
    copyToClipboard,
    formatFileSize,
    formatTime,
    truncateHash,
    SORTABLE_FIELDS,
    // ED2K 模板渲染（剧集 / 电影双模板）
    ed2kTemplates,
    showTemplateSettings,
    defaultEd2kTemplates,
    saveEd2kTemplates,
    isMovieRecord,
    getTemplateForRecord,
    renderEd2kFilename,
    rebuildEd2kLink,
    renderEd2kLink,
    copyEd2kWithTemplate,
    ed2kVariableGroups,
    ed2kTemplatePresets,
    // 批量导出 / 复制全部
    exporting,
    exportEd2kLinks,
    copyAllEd2kLinks,
    exportFullInfo,
  }
}
