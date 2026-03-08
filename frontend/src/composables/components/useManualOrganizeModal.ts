import { reactive, watch, h } from 'vue'
import { useDialog, NButton } from 'naive-ui'
import { getButtonStyle } from '../useButtonStyles'

export function useManualOrganizeModal(props: any, emit: any) {
  const dialog = useDialog()

  const manualTask = reactive<any>({
    id: '',
    rule_id: '',
    target_dir: '',
    action_type: 'move',
    overwrite_mode: false,
    anime_priority: true,
    monitor_mode: 'none',
    monitor_interval: 3600,
    process_interval: 0,
    ignore_file_regex: [],
    ignore_dir_regex: [],
    trigger_strm: false,
    forced_tmdb_id: '',
    forced_type: 'tv',
    forced_season: null,
    ignore_history: true
  })

  const manualSearch = reactive({ keyword: '', loading: false, results: [] as any[] })

  const getImg = (path: string) => {
    if (!path) return ''
    if (path.includes('/api/system/img')) return path
    if (path.includes('image.tmdb.org')) {
      const parts = path.split('/')
      return `${props.apiBase}/api/system/img?path=/${parts[parts.length - 1]}`
    }
    if (!path.startsWith('http')) return `${props.apiBase}/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
    return path
  }

  // When modal opens, merge default config
  watch(() => props.show, (newVal) => {
    if (newVal) {
      if (props.defaultTask) {
        Object.assign(manualTask, JSON.parse(JSON.stringify(props.defaultTask)))
      }
      // Fallback rule selection
      if (!manualTask.rule_id && props.availableRules.length > 0) {
        manualTask.rule_id = props.availableRules[0].id
      }
      manualSearch.results = []
      manualSearch.keyword = ''
    }
  })

  const searchTmdb = async () => {
    if (!manualSearch.keyword) return
    manualSearch.loading = true
    try {
      const res = await fetch(`${props.apiBase}/api/tmdb/search?query=${encodeURIComponent(manualSearch.keyword)}&type=${manualTask.forced_type}`)
      const data = await res.json()
      manualSearch.results = data.results || []
    } finally { manualSearch.loading = false }
  }

  const handleRun = () => {
    emit('run', { ...manualTask })
  }

  const handleRunBackground = () => {
    emit('run-background', { ...manualTask })
  }

  const handleConfirm = () => {
    dialog.info({
      title: '启动整理任务',
      content: '您希望如何运行此临时整理任务？',
      action: () => h('div', { style: 'display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px;' }, [
        h(NButton, { ...getButtonStyle('dialogCancel'), onClick: () => { handleRunBackground(); dialog.destroyAll() } }, { default: () => '后台静默执行' }),
        h(NButton, { ...getButtonStyle('dialogConfirm'), onClick: () => { handleRun(); dialog.destroyAll() } }, { default: () => '预览并手动执行' })
      ])
    })
  }

  return {
    manualTask,
    manualSearch,
    getImg,
    searchTmdb,
    handleRun,
    handleRunBackground,
    handleConfirm
  }
}
